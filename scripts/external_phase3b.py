"""Phase 3B source projection, frozen plan, isolated launch and pre-gold sealing."""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accuracy_worker import INVOICE_PROMPT
from external_eval.accuracy_nli import (
    SELECTION_INSTRUCTION,
    exact_label_provider_schema,
    provider_shape,
)
from external_eval.contracts import ContractPacket
from external_eval.gemini_http import MODEL
from external_eval.phase3 import InvoiceSelection
from external_eval.source import load_json, no_links, sha256, write_json
from external_phase2 import key

from clearledger.source_ocr import from_ocr
from clearledger.source_spans import Fallback, GroundingError, build, digest

ROOT = Path(__file__).resolve().parents[1]
SEED = "clearledger-final-external-phase3b-v1"
PLAN0 = "a83dc857f3f4ee8d0f6468fd945358504b59173e4ad55f53845bec3c7d00589d"
PLAN3 = "73fd2a85c27c2c7708d9a61590089a8c4e43385f28d6a72f5625a375894a1057"
DOC_ID = re.compile(r'^      "id": ([0-9]+),\s*$')
TEXT_FIELD = '      "text": '
SAFE_DOCILE_ID = re.compile(r"[a-z0-9]{24}")


def source_ids(path: Path) -> list[str]:
    """Pinned public JSON layout. Only document-level ID lines are decoded here."""
    no_links(path)
    with path.open(encoding="utf8") as stream:
        if stream.readline().strip() != "{" or stream.readline().strip() != '"documents": [':
            raise ValueError("UNRECOGNIZED_CONTRACT_SOURCE_LAYOUT")
        ids = [m[1] for line in stream if (m := DOC_ID.fullmatch(line))]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("INVALID_CONTRACT_SOURCE_IDS")
    return ids


def contract_texts(path: Path, selected: set[str]) -> dict[str, str]:
    no_links(path)
    results: dict[str, str] = {}
    current = ""
    with path.open(encoding="utf8") as stream:
        for line in stream:
            if match := DOC_ID.fullmatch(line):
                current = match[1]
            elif current in selected and line.startswith(TEXT_FIELD):
                if current in results:
                    raise ValueError("DUPLICATE_SOURCE_TEXT")
                value = json.loads(line.removeprefix(TEXT_FIELD).rstrip().removesuffix(","))
                if not isinstance(value, str):
                    raise ValueError("INVALID_SOURCE_TEXT")
                results[current] = value
    if set(results) != selected:
        raise ValueError("MISSING_SOURCE_TEXT")
    return results


def select_ids(dataset: str, ids: list[str], excluded: set[str], count: int) -> list[str]:
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_SOURCE_IDS")
    selected = sorted(set(ids) - excluded, key=lambda i: digest([SEED, dataset, i]))[:count]
    if len(selected) != count:
        raise ValueError("INSUFFICIENT_UNUSED_SOURCE_IDS")
    return selected


def write_sealed(path: Path, value: Any) -> str:
    write_json(path, value)
    checksum = sha256(path)
    with path.with_suffix(".sha256").open("x", encoding="ascii") as stream:
        stream.write(checksum + "\n")
    return checksum


def verified(path: Path) -> dict[str, Any]:
    no_links(path.with_suffix(".sha256"))
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("FROZEN_HASH_CHANGED")
    result: dict[str, Any] = load_json(path)
    return result


def choose(runs: Path, source: Path, reference: Path, root: Path) -> None:
    old_path, phase3_path = (
        runs / "evaluation-plan-v1.json",
        runs / "phase3-v1/evaluation-plan.json",
    )
    if (sha256(old_path), sha256(phase3_path)) != (PLAN0, PLAN3):
        raise ValueError("HISTORICAL_PLAN_CHANGED")
    old, phase3 = load_json(old_path), load_json(phase3_path)
    development = load_json(runs / "accuracy-development-v2/development-manifest.json")
    ref = load_json(reference / "baseline/config/campaign.json")
    ref_seal = load_json(reference / "development-seal.json")
    sealed = {Path(name): value for name, value in ref_seal["files"].items()}
    if (
        sha256(reference / "baseline/config/campaign.json")
        != sealed[Path("baseline/config/campaign.json")]
    ):
        raise ValueError("SELECTED_REFERENCE_CHANGED")
    source_sets = {
        "contract-nli": (source / "contract-nli/test.json", 24),
        "docile": (source / "docile/val.json", 100),
    }
    exclusions = {
        "contract-nli": set(development["contract_dev_ids"])
        | set(development["contract_train_ids"]),
        "docile": set(development["docile_train_ids"]) | set(development["docile_live_ids"]),
    }
    examples = ROOT / "local-data/contradiction-v2/scorer-only/predeclared.json"
    exclusions["contract-nli"].update(x["document_id"] for x in load_json(examples)["examples"])
    datasets = {}
    for dataset, (path, count) in source_sets.items():
        if sha256(path) != phase3["datasets"][dataset]["source_split_sha256"]:
            raise ValueError("KNOWN_PUBLIC_SPLIT_CHANGED")
        ids = source_ids(path) if dataset == "contract-nli" else load_json(path)
        if dataset == "docile" and (
            not isinstance(ids, list)
            or any(not isinstance(i, str) or not SAFE_DOCILE_ID.fullmatch(i) for i in ids)
        ):
            raise ValueError("INVALID_DOCILE_SPLIT")
        excluded = (
            exclusions[dataset]
            | set(old["datasets"][dataset]["ids"]["scored"])
            | set(old["datasets"][dataset]["ids"]["adapter"])
            | set(phase3["datasets"][dataset]["ids"])
            | set(phase3["datasets"][dataset]["adapter_ids"])
        )
        datasets[dataset] = {
            "ids": select_ids(dataset, ids, excluded, count),
            "source_split_sha256": sha256(path),
            "excluded_ids": sorted(excluded),
            "split": "TEST" if dataset == "contract-nli" else "VALIDATION",
            "eligible_count": len(set(ids) - excluded),
        }
    root.mkdir(parents=True, exist_ok=False)
    selection = {
        "seed": SEED,
        "selection": "ascending SHA256 canonical JSON [seed, dataset, ID]",
        "frozen_utc": datetime.now(UTC).isoformat(),
        "datasets": datasets,
        "prior_plan_sha256": {"phase0": PLAN0, "phase3": PLAN3},
        "reference_prompt_sha256": ref["prompt_sha256"],
        "reference_schema_sha256": ref["schema_sha256"],
    }
    print("Source ID selection sealed:", write_sealed(root / "source-selection.json", selection))


def prepare(runs: Path, source: Path, reference: Path, root: Path) -> None:
    from accuracy_completion import pdf_text

    selection = verified(root / "source-selection.json")
    tasks = selection["datasets"]
    test_path = source / "contract-nli/test.json"
    if (
        sha256(test_path) != tasks["contract-nli"]["source_split_sha256"]
        or sha256(source / "docile/val.json") != tasks["docile"]["source_split_sha256"]
    ):
        raise ValueError("FROZEN_SPLIT_CHANGED")
    if (digest(SELECTION_INSTRUCTION), digest(exact_label_provider_schema())) != (
        selection["reference_prompt_sha256"],
        selection["reference_schema_sha256"],
    ):
        raise ValueError("SELECTED_CONTRACT_REFERENCE_CHANGED")
    baseline = reference / "baseline"
    ref_config = load_json(baseline / "config/campaign.json")
    j = next(j for j in ref_config["jobs"] if j["variant"] == "nli-global-minimal-dev")
    if sha256(baseline / j["input"]) != j["input_sha256"]:
        raise ValueError("PUBLIC_HYPOTHESES_CHANGED")
    hypotheses = ContractPacket.model_validate(load_json(baseline / j["input"])).hypotheses
    if len(hypotheses) != 17:
        raise ValueError("HYPOTHESIS_BATCH_CHANGED")
    jobs: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    inputs: dict[str, str] = {}

    def add(identifier: str, kind: str, raw: dict[str, Any], *, control: bool = False) -> None:
        phase = ("control-" if control else "") + kind
        relative = f"inputs/{phase}/{identifier}.json"
        write_json(root / relative, raw)
        inputs[relative] = sha256(root / relative)
        job = {
            "job_id": phase + "-" + identifier,
            "variant": phase,
            "kind": kind,
            "mode": "direct",
            "thinking": "MINIMAL",
            "strategy": "global",
            "k": 20,
            "input": relative,
            "input_sha256": inputs[relative],
            "hypotheses": [h["hypothesis_id"] for h in raw.get("hypotheses", [])],
            "source_unavailable": raw.get("source_unavailable", False),
        }
        (controls if control else jobs).append(job)

    texts = contract_texts(test_path, set(tasks["contract-nli"]["ids"]))
    for identifier in tasks["contract-nli"]["ids"]:
        contract = ContractPacket(
            document_id=identifier, text=texts[identifier], hypotheses=hypotheses
        )
        add(identifier, "contract", contract.model_dump(mode="json"))
    source_files = {}
    for identifier in tasks["docile"]["ids"]:
        ocr = source / "docile/ocr" / f"{identifier}.json"
        no_links(ocr)
        ocr_hash = sha256(ocr) if ocr.is_file() else None
        if ocr_hash:
            source_files[f"docile/ocr/{identifier}.json"] = ocr_hash
        try:
            if ocr_hash is None:
                raise GroundingError("OCR_MISSING")
            primary = from_ocr(identifier, load_json(ocr), source_hash=ocr_hash)
        except (GroundingError, ValueError, TypeError, KeyError, AttributeError, IndexError):
            fallback_hash = ocr_hash or digest([identifier, "OCR_MISSING"])
            primary = build(
                identifier,
                (),
                source_hash=fallback_hash,
                kind="OCR",
                fallbacks=(Fallback("UNAVAILABLE", fallback_hash, 1, "MISSING_OR_INVALID_OCR"),),
            )
        alternate = pdf_text(source / "docile/pdfs" / f"{identifier}.pdf", identifier)
        raw = {
            "document_id": identifier,
            "canonical_source": asdict(primary),
            "source_unavailable": not any(
                p.text.strip() for p in (*primary.pages, *(alternate.pages if alternate else ()))
            ),
        }
        if alternate:
            raw["pdf_text_source"] = asdict(alternate)
            source_files[f"docile/pdfs/{identifier}.pdf"] = alternate.source_hash
        add(identifier, "invoice", raw)
    old_control = ROOT / "local-data/contract-selection-v1/baseline/inputs/control/legal.json"
    for kind, raw in (
        ("contract", load_json(old_control)),
        ("invoice", load_json(runs / "phase3-v1/inputs/preflight_docile/synthetic-invoice.json")),
    ):
        add(raw["document_id"], kind, raw, control=True)
    source_manifest = write_sealed(
        root / "source-manifest.json", {"packets": inputs, "source_files": source_files}
    )
    code = {
        *map(Path, ref_config["code_hashes"]),
        ROOT / "scripts/external_phase3b_worker.py",
        ROOT / "scripts/external_phase3b_score.py",
        Path(__file__),
        ROOT / "scripts/external_eval/scorers.py",
        ROOT / "scripts/external_eval/gold.py",
        ROOT / "scripts/external_eval/contracts.py",
        ROOT / "scripts/external_eval/source.py",
        ROOT / "scripts/accuracy_development.py",
        ROOT / "scripts/external_phase2_score.py",
        ROOT / "src/clearledger/document_runtime.py",
        ROOT / "src/clearledger/document_parse.py",
        ROOT / "uv.lock",
    }
    code_hashes = {str(p): sha256(p) for p in sorted(code)}
    plan = {
        **selection,
        "selection_sha256": sha256(root / "source-selection.json"),
        "source_manifest_sha256": source_manifest,
        "protocol": "phase3b-v1",
        "model": MODEL,
        "thinking": "MINIMAL",
        "retry_policy": "NONE",
        "pacing": {"callers": 1, "http_interval_seconds": 10},
        "contract": {
            "k": 20,
            "adjacent": 1,
            "strategy": "global",
            "batch": 17,
            "prompt_sha256": digest(SELECTION_INSTRUCTION),
            "schema_sha256": digest(exact_label_provider_schema()),
            "input": 32768,
            "output": 4096,
            "validation": "strict per item",
        },
        "invoice": {
            "prompt_sha256": digest(INVOICE_PROMPT),
            "schema_sha256": digest(provider_shape(InvoiceSelection.model_json_schema())),
            "input": 8192,
            "output": 1024,
            "candidate_limit": 64,
            "pdf_candidate_limit": 8,
        },
        "failure_handling": "retain all IDs; no replacements; no-call empty candidate pools",
        "scorers": {
            "contract": "score_contract unchanged",
            "invoice": "value and localized ID sets",
            "official_docile": "docile-benchmark 0.3.5 conditional document_id KILE",
        },
        "code_hashes": code_hashes,
        "gold": "SCORER_ONLY_AFTER_BOTH_PREDICTION_SEALS",
    }
    plan_hash = write_sealed(root / "evaluation-plan.json", plan)
    config = {
        "protocol": "phase3b-v1",
        "model": MODEL,
        "run_root": str(root),
        "simple_provider_shape": True,
        "request_spec": {},
        "retry_policy": "NONE",
        "pacing": plan["pacing"],
        "limits": {"generations": 126, "input_tokens": 1_700_000, "output_tokens": 210_000},
        "jobs": jobs,
        "controls": controls,
        "plan_sha256": plan_hash,
        "code_hashes": code_hashes,
        "source_manifest_sha256": source_manifest,
    }
    print(
        "Phase 3B plan:",
        plan_hash,
        "configuration:",
        write_sealed(root / "inference-config.json", config),
    )


def frozen(root: Path) -> dict[str, Any]:
    config = verified(root / "inference-config.json")
    plan = verified(root / "evaluation-plan.json")
    verified(root / "source-selection.json")
    manifest = verified(root / "source-manifest.json")
    for path, value in (
        ("evaluation-plan.json", config["plan_sha256"]),
        ("source-selection.json", plan["selection_sha256"]),
        ("source-manifest.json", config["source_manifest_sha256"]),
    ):
        if sha256(root / path) != value:
            raise ValueError("FROZEN_ARTIFACT_CHANGED")
    for paths, location in ((config["code_hashes"], Path()), (manifest["packets"], root)):
        if any(sha256(location / path) != value for path, value in paths.items()):
            raise ValueError("FROZEN_CODE_OR_PACKET_CHANGED")
    return config


def launch(root: Path, stage: str) -> None:
    config = frozen(root)
    identity = sha256(root / "inference-config.json")
    if stage == "jobs" and load_json(root / "config/admission.json") != {
        "sha256": identity,
        "status": "PASS",
    }:
        raise ValueError("SYNTHETIC_ADMISSION_REQUIRED")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "scripts/external_phase3b_worker.py")],
        input=json.dumps(
            {"stage": stage, "key": key(), "config_path": str(root / "inference-config.json")}
        ),
        text=True,
        encoding="utf8",
        env=env,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ValueError("ISOLATED_WORKER_STOPPED")
    if stage == "controls":
        for job in config["controls"]:
            row = load_json(root / "predictions" / f"{job['job_id']}.json")
            if row["metadata"]["status"] != "SUCCESS":
                raise ValueError("SYNTHETIC_PROVIDER_ADMISSION_FAILED")
            if job["kind"] == "contract" and (
                len(row["diagnostics"]["items"]) != len(job["hypotheses"])
                or any(not i["status"].startswith("VALID_") for i in row["diagnostics"]["items"])
            ):
                raise ValueError("SYNTHETIC_CONTRACT_ADMISSION_FAILED")
            if job["kind"] == "invoice" and (
                not row["output"]["invoice_references"] or row["diagnostics"]["invalid_aliases"]
            ):
                raise ValueError("SYNTHETIC_INVOICE_ADMISSION_FAILED")
        write_json(root / "config/admission.json", {"sha256": identity, "status": "PASS"})


def seal(root: Path) -> None:
    config = frozen(root)
    plan = verified(root / "evaluation-plan.json")
    for kind, dataset in (("contract", "contract-nli"), ("invoice", "docile")):
        rows, files = [], {}
        for job in config["jobs"]:
            if job["kind"] != kind:
                continue
            path = root / "predictions" / f"{job['job_id']}.json"
            row = load_json(path)
            if row["job_id"] != job["job_id"] or row["financial_authority"] is not False:
                raise ValueError("PREDICTION_JOB_OR_AUTHORITY_MISMATCH")
            rows.append(row)
            files[str(path.relative_to(root))] = sha256(path)
            if kind == "invoice":
                offer = root / "predictions/offers" / path.name
                files[str(offer.relative_to(root))] = sha256(offer)
        if [row["source_id"] for row in rows] != plan["datasets"][dataset]["ids"]:
            raise ValueError("FROZEN_DENOMINATOR_CHANGED")
        aggregate = root / "predictions" / f"{kind}-final.jsonl"
        with aggregate.open("x", encoding="utf8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        files[str(aggregate.relative_to(root))] = sha256(aggregate)
        record = {
            "status": "SEALED",
            "files": files,
            "plan_sha256": config["plan_sha256"],
            "config_sha256": sha256(root / "inference-config.json"),
            "source_manifest_sha256": config["source_manifest_sha256"],
        }
        print(
            kind,
            "predictions SEALED:",
            sha256(aggregate),
            write_sealed(root / "seals" / f"{kind}.json", record),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("choose", "prepare", "controls", "jobs", "seal"))
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=ROOT / "local-data/contract-selection-v1")
    args = parser.parse_args()
    root = args.runs.resolve() / "phase3b-v1"
    if args.action in {"choose", "prepare"}:
        action = choose if args.action == "choose" else prepare
        action(args.runs.resolve(), args.source.resolve(), args.reference.resolve(), root)
    elif args.action == "seal":
        seal(root)
    else:
        launch(root, args.action)
