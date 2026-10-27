"""Trusted Phase 3 source projection/config/sealing; never imports a gold reader."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from external_eval.phase3 import (
    INVOICE_PROMPT,
    PLAN_PROMPT,
    SYNTHESIS_PROMPT,
    Decisions,
    InvoiceSelection,
    Plan,
)
from external_eval.source import contract_packets, load_json, sha256, write_json, write_packets
from external_phase2 import key

from clearledger.source_ocr import from_ocr
from clearledger.source_spans import Fallback, GroundingError, build

ROOT = Path(__file__).resolve().parents[1]


def check_plan(runs: Path) -> dict[str, Any]:
    path = runs / "phase3-v1/evaluation-plan.json"
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("FROZEN_PLAN_CHANGED")
    value: dict[str, Any] = load_json(path)
    return value


def prepare(runs: Path, source: Path) -> None:
    root = runs / "phase3-v1"
    plan = check_plan(runs)
    baseline = runs / "phase2-v1"
    write_json(
        root / "baseline-v1-hashes.json",
        {
            "file_metadata": {
                str(p.relative_to(baseline)): [p.stat().st_size, p.stat().st_mtime_ns]
                for p in sorted(baseline.rglob("*"))
                if p.is_file()
            },
            "sealed_sha256": load_json(baseline / "scoring/completion-metadata.json")[
                "artifact_sha256"
            ],
        },
    )
    # Only metadata and existing seal hashes above: no v1 annotation contents read.
    manifest = {}
    for phase, tier, split in (("smoke", "adapter_ids", "dev"), ("final", "ids", "test")):
        cspec = plan["datasets"]["contract-nli"]
        packets = contract_packets(
            source / "contract-nli" / f"{split}.json",
            cspec[tier],
            load_json(runs / "evaluation-plan-v1.json")["datasets"]["contract-nli"][
                "hypothesis_ids"
            ],
        )
        directory = root / "inputs" / f"contract_{phase}"
        manifest[f"contract_{phase}"] = {
            "dataset": "contract-nli",
            "ids": cspec[tier],
            "input_directory": str(directory),
            "packet_hashes": write_packets(directory, packets),
        }
        ds = plan["datasets"]["docile"]
        directory = root / "inputs" / f"docile_{phase}"
        hashes = {}
        for identifier in ds[tier]:
            path = source / "docile/ocr" / f"{identifier}.json"
            raw = load_json(path)
            try:
                canonical = from_ocr(identifier, raw, source_hash=sha256(path))
            except (GroundingError, TypeError, KeyError, IndexError):
                canonical = build(
                    identifier,
                    (),
                    source_hash=sha256(path),
                    kind="OCR",
                    fallbacks=(
                        Fallback("UNAVAILABLE", sha256(path), 1, "MALFORMED_OR_LIMITED_OCR"),
                    ),
                )
            alternative_hash = None
            if any(
                f.method == "UNAVAILABLE" or f.reason == "INVALID_OCR_WORD"
                for f in canonical.fallbacks
            ):
                pdf = source / "docile/pdfs" / f"{identifier}.pdf"
                if pdf.is_file() and pdf.stat().st_size <= 2_097_152:
                    from clearledger.document_contract import ExtractionError
                    from clearledger.document_runtime import parse_bounded

                    try:
                        parsed = parse_bounded(pdf.read_bytes(), "application/pdf")
                        alternatives = {
                            f.page: parsed["pages"][f.page - 1]
                            for f in canonical.fallbacks
                            if f.page <= len(parsed.get("pages", []))
                            and parsed["pages"][f.page - 1].strip()
                        }
                        if alternatives:
                            canonical = from_ocr(
                                identifier, raw, source_hash=sha256(path), alternatives=alternatives
                            )
                            alternative_hash = sha256(pdf)
                    except (ExtractionError, ValueError, KeyError):
                        pass  # Retain original fallback/abstention; never invent coordinates.
            out = directory / f"{identifier}.json"
            write_json(
                out,
                {
                    "document_id": identifier,
                    "canonical_source": asdict(canonical),
                    "alternative_pdf_sha256": alternative_hash,
                },
            )
            hashes[out.name] = sha256(out)
        manifest[f"docile_{phase}"] = {
            "dataset": "docile",
            "ids": ds[tier],
            "input_directory": str(directory),
            "packet_hashes": hashes,
        }
    # Synthetic-only admission controls use the same schemas and bounded paths.
    from external_eval.contracts import ContractPacket, Hypothesis

    packet = ContractPacket(
        document_id="synthetic-control",
        text="Disclosure to employees is permitted.",
        hypotheses=[Hypothesis(hypothesis_id="h1", text="Disclosure to employees is permitted.")],
    )
    directory = root / "inputs/preflight_contract"
    manifest["preflight_contract"] = {
        "dataset": "contract-nli",
        "ids": [packet.document_id],
        "input_directory": str(directory),
        "packet_hashes": write_packets(directory, [packet]),
    }
    raw = {
        "pages": [
            {
                "blocks": [
                    {
                        "lines": [
                            {
                                "words": [
                                    {"value": "Tax invoice", "geometry": [[0.1, 0.1], [0.4, 0.2]]},
                                    {"value": "INV-UNIT-1", "geometry": [[0.5, 0.1], [0.8, 0.2]]},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    canonical = from_ocr("synthetic-invoice", raw, source_hash="1" * 64)
    directory = root / "inputs/preflight_docile"
    out = directory / "synthetic-invoice.json"
    write_json(out, {"document_id": "synthetic-invoice", "canonical_source": asdict(canonical)})
    manifest["preflight_docile"] = {
        "dataset": "docile",
        "ids": ["synthetic-invoice"],
        "input_directory": str(directory),
        "packet_hashes": {out.name: sha256(out)},
    }
    for folder in ("config", "attempts", "predictions", "seals", "scoring", "logs/metadata"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    write_json(root / "config/source-manifest.json", manifest)
    print("Phase 3 source-only projection complete; no new annotations interpreted.")


def freeze(runs: Path) -> None:
    root = runs / "phase3-v1"
    plan = check_plan(runs)
    code = [
        ROOT / "scripts/external_phase3.py",
        ROOT / "scripts/external_phase3_worker.py",
        ROOT / "scripts/external_phase3_score.py",
        ROOT / "scripts/external_gemini_worker.py",
        *sorted((ROOT / "scripts/external_eval").glob("*.py")),
        *sorted((ROOT / "src/clearledger").glob("source_*.py")),
    ]
    value = {
        "protocol": plan["protocol"],
        "frozen_plan_sha256": sha256(root / "evaluation-plan.json"),
        "run_root": str(root),
        "model": plan["model"],
        "created_utc": datetime.now(UTC).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "request_spec": {
            "plan_prompt": PLAN_PROMPT,
            "synthesis_prompt": SYNTHESIS_PROMPT,
            "extraction_prompt": INVOICE_PROMPT,
            "plan_schema": Plan.model_json_schema(),
            "synthesis_schema": Decisions.model_json_schema(),
            "extraction_schema": InvoiceSelection.model_json_schema(),
        },
        "pacing": {"http_interval_seconds": 10, "http_operations_per_minute": 6, "callers": 1},
        "limits": {"generations": 165, "input_tokens": 3_000_000, "output_tokens": 350_000},
        "retry_policy": "NONE",
        "thinking": "MINIMAL",
        "httpx_retries": 0,
        "sdk_used": False,
        "account_tier": "Free; operator-confirmed current project; billing not changed",
        "code_hashes": {str(p): sha256(p) for p in code},
        "source_manifest_sha256": sha256(root / "config/source-manifest.json"),
        "baseline_inventory_sha256": sha256(root / "baseline-v1-hashes.json"),
        "environment_versions": {
            n: importlib.metadata.version(n) for n in ("httpx", "pydantic", "clearledger")
        },
        "effective_limits": {
            "contract_input": 32768,
            "contract_output": 4096,
            "docile_input": 8192,
            "docile_output": 1024,
            "invoice_candidates": 64,
            "retrieval_top_k": 6,
            "adjacent_context": 1,
        },
        "phases": load_json(root / "config/source-manifest.json"),
    }
    path = root / "inference-config.json"
    value["prompt_schema_hashes"] = {
        k: hashlib.sha256(
            (v if isinstance(v, str) else json.dumps(v, sort_keys=True)).encode()
        ).hexdigest()
        for k, v in value["request_spec"].items()
    }
    write_json(path, value)
    path.with_suffix(".sha256").write_text(sha256(path) + "\n", encoding="ascii")
    print("Phase 3 inference frozen:", sha256(path))


def launch(runs: Path, stage: str) -> None:
    root = runs / "phase3-v1"
    path = root / "inference-config.json"
    config = load_json(path)
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("CONFIG_CHANGED")
    for file, digest in config["code_hashes"].items():
        if sha256(Path(file)) != digest:
            raise ValueError("CODE_CHANGED")
    phases = (
        [f"{p}_{stage}" for p in ("contract", "docile")]
        if stage != "preflight"
        else ["preflight_contract", "preflight_docile"]
    )
    if stage != "preflight":
        needed = (
            ["preflight_contract", "preflight_docile"]
            if stage == "smoke"
            else ["contract_smoke", "docile_smoke"]
        )
        if any(not (root / "predictions" / f"{name}.jsonl").is_file() for name in needed):
            raise ValueError("PRECEDING_STAGE_INCOMPLETE")
        if stage == "smoke":
            for name in needed:
                rows = [
                    json.loads(line)
                    for line in (root / "predictions" / f"{name}.jsonl")
                    .read_text(encoding="utf8")
                    .splitlines()
                ]
                if any(row["metadata"]["failure"] != "NONE" for row in rows):
                    raise ValueError("SYNTHETIC_SCHEMA_ADMISSION_FAILED")
                if name == "preflight_contract" and any(len(row["answers"]) != 1 for row in rows):
                    raise ValueError("SYNTHETIC_ANSWER_ADMISSION_FAILED")
                diagnostics = load_json(root / "logs/metadata" / f"{name}-grounding.json")
                if any(row.get("plan_status", "SUCCESS") != "SUCCESS" for row in diagnostics):
                    raise ValueError("SYNTHETIC_PLAN_ADMISSION_FAILED")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    payload = {"key": key(), "config_path": str(path), "phases": phases}
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "scripts/external_phase3_worker.py")],
        input=json.dumps(payload),
        text=True,
        encoding="utf8",
        env=env,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ValueError("WORKER_STOPPED_NO_RETRY")


def seal(runs: Path) -> None:
    root = runs / "phase3-v1"
    config = load_json(root / "inference-config.json")
    for name in ("contract_final", "docile_final"):
        p = root / "predictions" / f"{name}.jsonl"
        rows = [json.loads(line) for line in p.read_text(encoding="utf8").splitlines()]
        if [r["document_id"] for r in rows] != config["phases"][name]["ids"]:
            raise ValueError("FINAL_COVERAGE_MISMATCH")
        diagnostic = root / "logs/metadata" / f"{name}-grounding.json"
        write_json(
            root / "seals" / f"{name}.json",
            {
                "status": "SEALED",
                "predictions_sha256": sha256(p),
                "grounding_sha256": sha256(diagnostic),
                "config_sha256": sha256(root / "inference-config.json"),
            },
        )
    print("Both Phase 3 predictions and grounding selections sealed before gold.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["prepare", "freeze", "preflight", "smoke", "final", "seal"]
    )
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.source is None:
            raise ValueError("SOURCE_REQUIRED")
        prepare(args.runs, args.source)
    elif args.action == "freeze":
        freeze(args.runs)
    elif args.action == "seal":
        seal(args.runs)
    else:
        launch(args.runs, args.action)
