"""Trusted evaluation controller. Source preparation is separate from the restricted worker."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from external_eval.contracts import ContractPacket, DocilePacket, Hypothesis
from external_eval.source import (
    contract_packets,
    docile_packet,
    load_json,
    load_plan,
    read_packets,
    sha256,
    write_json,
    write_packets,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
PLAN_HASH = "a83dc857f3f4ee8d0f6468fd945358504b59173e4ad55f53845bec3c7d00589d"


def key() -> str:
    for name in ("CLEARLEDGER_EVAL_GEMINI_API_KEY", "EVALUATION_GEMINI_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    for file in (ROOT / ".env.external-evaluation", ROOT / ".env"):
        if file.exists():
            data = dotenv_values(file, interpolate=False)
            for name in (
                "CLEARLEDGER_EVAL_GEMINI_API_KEY",
                "EVALUATION_GEMINI_API_KEY",
                "GEMINI_API_KEY",
            ):
                if data.get(name):
                    return str(data[name])
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    raise ValueError("NO_CONFIGURED_EVALUATION_KEY")


def prepare(source: Path, runs: Path) -> None:
    root = runs / "phase2-v1"
    plan_path = runs / "evaluation-plan-v1.json"
    plan = load_plan(plan_path)
    if sha256(plan_path) != PLAN_HASH:
        raise ValueError("WRONG_FROZEN_PLAN")
    inventory = load_json(runs / "inventory" / "complete-v1" / "inventory.json")
    if sha256(runs / "inventory" / "complete-v1" / "inventory.json") != plan["inventory_sha256"]:
        raise ValueError("INVENTORY_CHANGED")
    manifest: dict[str, Any] = {}
    old = load_json(runs / "phase1-v1" / "projection-manifest.json")
    for phase, tier, split in (("smoke", "adapter", "dev"), ("final", "scored", "test")):
        nspec = plan["datasets"]["contract-nli"]
        if (
            sha256(source / "contract-nli" / f"{split}.json")
            != inventory["datasets"]["contract-nli"]["inspection"]["splits"][split]["sha256"]
        ):
            raise ValueError("CONTRACT_SOURCE_CHANGED")
        if phase == "smoke":
            existing = read_packets(
                runs / "contractnli-v1" / "inputs" / "adapter",
                old["packets"]["contract-nli"],
                "contract-nli",
            )
            packets = [existing[k] for k in nspec["ids"][tier]]
        else:
            packets = contract_packets(
                source / "contract-nli" / "test.json", nspec["ids"][tier], nspec["hypothesis_ids"]
            )
        directory = root / "inputs" / f"contract_{phase}"
        manifest[f"contract_{phase}"] = {
            "dataset": "contract-nli",
            "ids": nspec["ids"][tier],
            "input_directory": str(directory),
            "packet_hashes": write_packets(directory, packets),
        }
        ds = plan["datasets"]["docile"]
        valid: list[DocilePacket] = []
        failures = {}
        original = {
            x["path"]: x["sha256"]
            for x in inventory["datasets"]["docile"]["inspection"]["selected_file_sha256"]
        }
        for identifier in ds["ids"][tier]:
            path = source / "docile" / "ocr" / f"{identifier}.json"
            if sha256(path) != original[f"ocr/{identifier}.json"]:
                raise ValueError("OCR_SOURCE_CHANGED")
            try:
                valid.append(docile_packet(path, identifier))
            except ValidationError:
                failures[identifier] = "FROZEN_SCHEMA_REJECTED"
            except ValueError as exc:
                if str(exc) not in {"EMPTY_OCR_PAGE", "INVALID_OCR_WORD", "INVALID_OCR_PAGE"}:
                    raise
                failures[identifier] = str(exc)
        directory = root / "inputs" / f"docile_{phase}"
        manifest[f"docile_{phase}"] = {
            "dataset": "docile",
            "ids": ds["ids"][tier],
            "input_directory": str(directory),
            "packet_hashes": write_packets(directory, valid),
            "input_failures": failures,
        }
    # Independently approved tiny synthetic admission inputs, never evaluation data.
    synthetic = ContractPacket(
        document_id="synthetic-control",
        text=(
            "This synthetic agreement permits disclosure to employees. "
            "Public disclosure is prohibited."
        ),
        hypotheses=[
            Hypothesis(hypothesis_id="synthetic-h1", text="Disclosure to employees is permitted.")
        ],
    )
    directory = root / "inputs" / "preflight_contract"
    manifest["preflight_contract"] = {
        "dataset": "contract-nli",
        "ids": [synthetic.document_id],
        "input_directory": str(directory),
        "packet_hashes": write_packets(directory, [synthetic]),
    }
    from external_eval.contracts import Box, Page, Word

    text = "Invoice INV-UNIT-1"
    synthetic_doc = DocilePacket(
        document_id="synthetic-invoice",
        pages=[
            Page(
                page=0,
                text=text,
                words=[
                    Word(start=0, end=7, box=Box(left=0.1, top=0.1, right=0.2, bottom=0.2)),
                    Word(start=8, end=len(text), box=Box(left=0.3, top=0.1, right=0.5, bottom=0.2)),
                ],
            )
        ],
    )
    directory = root / "inputs" / "preflight_docile"
    manifest["preflight_docile"] = {
        "dataset": "docile",
        "ids": [synthetic_doc.document_id],
        "input_directory": str(directory),
        "packet_hashes": write_packets(directory, [synthetic_doc]),
    }
    for part in ("config", "attempts", "predictions", "seals", "scoring", "smoke", "logs/metadata"):
        (root / part).mkdir(parents=True, exist_ok=True)
    write_json(root / "config" / "source-manifest.json", manifest)
    print("Frozen source-only inputs prepared; no annotations read and no model calls.")


def configuration(runs: Path, *, final: bool, admission_revision: int = 1) -> Path:
    root = runs / "phase2-v1"
    spec = load_json(runs / "phase1-5-v1" / "request-cost-specification.json")
    manifest = load_json(root / "config" / "source-manifest.json")
    code_files = [
        ROOT / "scripts" / "external_gemini_worker.py",
        ROOT / "scripts" / "external_phase2_score.py",
        Path(__file__),
        *sorted((ROOT / "scripts" / "external_eval").glob("*.py")),
    ]
    admission_name = (
        "config.json" if admission_revision == 1 else f"config-v{admission_revision}.json"
    )
    path = root / "inference-config.json" if final else root / "preflight" / admission_name
    if final:
        for phase in ("preflight_contract", "preflight_docile"):
            report = load_json(root / "logs" / "metadata" / f"{phase}-summary.json")
            if set(report["statuses"]) - {"SUCCESS", "plan:SUCCESS", "MISSING_ANSWERS"}:
                raise ValueError("SYNTHETIC_ADMISSION_NOT_PASSED")
            if report["statuses"].get("MISSING_ANSWERS", 0):
                raise ValueError("SYNTHETIC_ADMISSION_NOT_PASSED")
    value = {
        "protocol": "clearledger-external-evaluation-v1",
        "frozen_plan_sha256": PLAN_HASH,
        "run_root": str(root),
        "created_utc": datetime.now(UTC).isoformat(),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "model": "gemini-3.5-flash-lite",
        "request_spec": spec,
        "spec_sha256": sha256(runs / "phase1-5-v1" / "request-cost-specification.json"),
        "prompt_schema_hashes": {
            k: hashlib.sha256(
                (v if isinstance(v, str) else json.dumps(v, sort_keys=True)).encode("utf8")
            ).hexdigest()
            for k, v in spec.items()
            if k.endswith(("_prompt", "_schema"))
        },
        "authentication_model_metadata_sha256": sha256(root / "preflight" / "auth-model.json"),
        "account": {
            "tier": "Free",
            "verification": "operator-current-AI-Studio-confirmation",
            "rpm": 15,
            "input_tpm": 250000,
            "rpd": 500,
            "displayed_usage": {"rpm": 3, "input_tpm": 2350, "rpd": 30},
            "usage_semantics": "UI display, not asserted exact daily consumption or470 remaining",
        },
        "pacing": {
            "http_interval_seconds": 10,
            "http_operations_per_minute": 6,
            "callers": 1,
            "authorization": "explicit operator pacing-only amendment2026-10-28",
            "reason": (
                "Below current 15 RPM; no extra generations/retries; reduces unnecessary runtime"
            ),
        },
        "limits": {"generations": 88, "input_tokens": 1458176, "output_tokens": 182272},
        "retry_policy": "NONE",
        "sdk_used": False,
        "httpx_retries": 0,
        "follow_redirects": False,
        "code_hashes": {str(p): sha256(p) for p in code_files},
        "source_manifest_sha256": sha256(root / "config" / "source-manifest.json"),
        "phases": manifest
        if final
        else {k: v for k, v in manifest.items() if k.startswith("preflight")},
        "thinking": "MINIMAL",
        "sampling_parameters": "OMITTED_PER_CURRENT_OFFICIAL_DOCS",
        "max_input_tokens": {"contract": 32768, "docile": 8192},
        "max_output_tokens": {"contract": 4096, "docile": 1024},
    }
    import importlib.metadata

    value["environment_versions"] = {
        n: importlib.metadata.version(n) for n in ("httpx", "pydantic")
    }
    write_json(path, value)
    with path.with_suffix(".sha256").open("x", encoding="ascii") as stream:
        stream.write(sha256(path) + "\n")
    print(
        "Final inference configuration frozen." if final else "Synthetic-only configuration frozen."
    )
    return path


def launch(runs: Path, phase: str, admission_revision: int = 1) -> None:
    root = runs / "phase2-v1"
    path = (
        root
        / "preflight"
        / ("config.json" if admission_revision == 1 else f"config-v{admission_revision}.json")
        if phase == "preflight"
        else root / "inference-config.json"
    )
    config = load_json(path)
    for file, digest in config["code_hashes"].items():
        if sha256(Path(file)) != digest:
            raise ValueError("CODE_CHANGED_AFTER_FREEZE")
    if phase == "preflight":
        phases = ["preflight_contract", "preflight_docile"]
    elif phase == "smoke":
        phases = ["contract_smoke", "docile_smoke"]
    else:
        for name in ("contract_smoke", "docile_smoke"):
            if not (root / "predictions" / f"{name}.jsonl").exists():
                raise ValueError("SMOKE_NOT_COMPLETE")
        phases = ["contract_final", "docile_final"]
    payload = {"key": key(), "config_path": str(path), "phases": phases}
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    child = subprocess.Popen(
        [sys.executable, "-I", "-B", str(ROOT / "scripts" / "external_gemini_worker.py")],
        stdin=subprocess.PIPE,
        stdout=None,
        stderr=subprocess.DEVNULL,
        env=environment,
        text=True,
        encoding="utf8",
    )
    assert child.stdin is not None
    child.stdin.write(json.dumps(payload))
    child.stdin.close()
    if child.wait():
        raise ValueError("WORKER_STOPPED_SEE_SAFE_METADATA")


def seal(runs: Path) -> None:
    root = runs / "phase2-v1"
    config_path = root / "inference-config.json"
    config = load_json(config_path)
    for name in ("contract_final", "docile_final"):
        path = root / "predictions" / f"{name}.jsonl"
        lines = path.read_text(encoding="utf8").splitlines()
        ids = [json.loads(line)["document_id"] for line in lines]
        if ids != config["phases"][name]["ids"]:
            raise ValueError("FINAL_COVERAGE_MISMATCH")
        write_json(
            root / "seals" / f"{name}.json",
            {
                "status": "SEALED",
                "predictions_sha256": sha256(path),
                "inference_config_sha256": sha256(config_path),
                "source_manifest_sha256": config["source_manifest_sha256"],
                "code_hashes": config["code_hashes"],
                "git_commit": config["git_commit"],
            },
        )
    print("Both final prediction artifacts SEALED before any gold access.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["prepare", "preflight-config", "preflight", "freeze", "smoke", "final", "seal"],
    )
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--admission-revision", type=int, default=1)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.source is None:
            raise ValueError("SOURCE_REQUIRED_FOR_TRUSTED_PROJECTION")
        prepare(args.source, args.runs)
    elif args.action in {"preflight-config", "freeze"}:
        configuration(
            args.runs, final=args.action == "freeze", admission_revision=args.admission_revision
        )
    elif args.action == "seal":
        seal(args.runs)
    else:
        launch(args.runs, args.action, admission_revision=args.admission_revision)


if __name__ == "__main__":
    main()
