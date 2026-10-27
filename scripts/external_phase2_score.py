"""Post-seal scorer process. Never imported by the inference worker."""

import argparse
import json
import math
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from external_eval.contracts import ContractOutput, DocileOutput
from external_eval.failure_denominator import score_with_input_failures
from external_eval.gold import contract_gold, docile_gold, docile_scorer_view, verify_gold_sources
from external_eval.scorers import kile_predictions, score_contract
from external_eval.source import load_json, load_plan, read_packets, sha256, write_json


def verified_seals(root: Path) -> dict[str, Any]:
    path = root / "inference-config.json"
    config = load_json(path)
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("CONFIG_CHECKSUM_CHANGED")
    for phase in ("contract_final", "docile_final"):
        seal = load_json(root / "seals" / f"{phase}.json")
        if (
            seal["status"] != "SEALED"
            or seal["predictions_sha256"] != sha256(root / "predictions" / f"{phase}.jsonl")
            or seal["inference_config_sha256"] != sha256(path)
            or seal["code_hashes"] != config["code_hashes"]
        ):
            raise ValueError("SEALED_ARTIFACT_CHANGED")
    for file, digest in config["code_hashes"].items():
        if sha256(Path(file)) != digest:
            raise ValueError("FROZEN_CODE_CHANGED")
    if sha256(root / "config" / "source-manifest.json") != config["source_manifest_sha256"]:
        raise ValueError("SOURCE_MANIFEST_CHANGED")
    return cast(dict[str, Any], config)


def performance(root: Path, phase: str) -> dict[str, Any]:
    attempts = [
        load_json(p)["metadata"]
        for p in (root / "attempts" / phase).glob("*/*.json")
        if not p.name.endswith(".started.json")
    ]
    generations = [m for m in attempts if m["generation_called"]]
    latencies = sorted(
        m["provider_latency_ms"] for m in generations if m["provider_latency_ms"] is not None
    )
    doc_times: Counter[str] = Counter()
    for item in attempts:
        doc_times[item["source_id"]] += item["wall_latency_ms"]
    token_fields = (
        "promptTokenCount",
        "candidatesTokenCount",
        "thoughtsTokenCount",
        "totalTokenCount",
        "cachedContentTokenCount",
    )
    return {
        "generation_attempts": len(generations),
        "attempt_statuses": Counter(m["status"] for m in attempts),
        "token_usage": {
            key: {
                "observed_sum": sum(m["usage"][key] or 0 for m in generations),
                "available_attempts": sum(m["usage"][key] is not None for m in generations),
                "unavailable_attempts": sum(m["usage"][key] is None for m in generations),
            }
            for key in token_fields
        },
        "generation_latency_ms": {
            "median": statistics.median(latencies) if latencies else None,
            "p95_nearest_rank": latencies[math.ceil(len(latencies) * 0.95) - 1]
            if latencies
            else None,
            "max": max(latencies) if latencies else None,
        },
        "document_latency_including_pacing_ms": dict(doc_times),
        "model_versions": sorted({m["model_version"] for m in generations if m["model_version"]}),
        "billing": (
            "Operator-confirmed Free tier; responses do not expose billed USD/account invoice"
        ),
    }


def score(runs: Path, source: Path) -> None:
    root = runs / "phase2-v1"
    config = verified_seals(root)  # Both datasets sealed BEFORE any gold interpretation.
    plan = load_plan(runs / "evaluation-plan-v1.json")
    if sha256(runs / "evaluation-plan-v1.json") != config["frozen_plan_sha256"]:
        raise ValueError("FROZEN_PLAN_CHANGED")
    inventory = runs / "inventory" / "complete-v1" / "inventory.json"
    results = {}
    for phase, dataset in (("contract_final", "contract-nli"), ("docile_final", "docile")):
        spec = config["phases"][phase]
        packets = read_packets(Path(spec["input_directory"]), spec["packet_hashes"], dataset)
        raw = [
            json.loads(line)
            for line in (root / "predictions" / f"{phase}.jsonl")
            .read_text(encoding="utf8")
            .splitlines()
        ]
        if [r["document_id"] for r in raw] != spec["ids"]:
            raise ValueError("DENOMINATOR_CHANGED")
        verify_gold_sources(inventory, plan, dataset, source / dataset, "scored")
        if dataset == "contract-nli":
            gold = contract_gold(
                source / dataset / "test.json",
                spec["ids"],
                plan["datasets"][dataset]["hypothesis_ids"],
            )
            result = score_contract(packets, [ContractOutput.model_validate(r) for r in raw], gold)
        else:
            doc_gold = docile_gold(source / dataset, spec["ids"])
            outputs = [DocileOutput.model_validate(r) for r in raw]
            result = score_with_input_failures(
                packets, outputs, doc_gold, set(spec.get("input_failures", {}))
            )
            native: dict[str, list[dict[str, Any]]] = {
                g.document_id: [] for g in doc_gold if g.is_invoice
            }
            for output in outputs:
                if output.document_id in native and output.document_id in packets:
                    native[output.document_id] = kile_predictions(
                        packets[output.document_id], output
                    )[0]
            native_path = root / "scoring" / "docile-conditional.kile.json"
            write_json(native_path, native)
            scope = docile_scorer_view(
                source / dataset,
                spec["ids"],
                root / "scoring" / "docile-native-view",
                "clearledger_val_v1",
            )
            result["native_scope"] = scope
            if not any(native.values()):
                result["official_status"] = (
                    "NOT COMPUTABLE: official 0.3.5 rejects all-empty predictions"
                )
            else:
                command = [
                    str(runs / "phase1-v1" / "venv" / "Scripts" / "docile_evaluate.exe"),
                    "--task",
                    "KILE",
                    "--dataset-path",
                    str(root / "scoring" / "docile-native-view"),
                    "--split",
                    "clearledger_val_v1",
                    "--predictions",
                    str(native_path),
                    "--evaluate-x-shot-subsets",
                    "",
                    "--evaluate-fieldtypes",
                    "--evaluate-also-text",
                    "--store-evaluation-result",
                    str(root / "scoring" / "docile-official.json"),
                ]
                completed = subprocess.run(command, capture_output=True, timeout=180, check=False)
                (root / "scoring" / "docile-official.log").write_bytes(
                    completed.stdout + completed.stderr
                )
                result["official_status"] = (
                    "COMPUTED" if completed.returncode == 0 else "NOT COMPUTABLE"
                )
                result["official_return_code"] = completed.returncode
                result["official_command"] = command
        result["performance"] = performance(root, phase)
        result["prediction_sha256"] = sha256(root / "predictions" / f"{phase}.jsonl")
        write_json(root / "scoring" / f"{phase}-metrics.json", result)
        results[dataset] = result
    write_json(
        root / "scoring" / "aggregate.json",
        {
            "results": results,
            "performance_all_phases": {name: performance(root, name) for name in config["phases"]},
            "config_sha256": sha256(root / "inference-config.json"),
            "financial_mutations": 0,
            "financial_safety_basis": (
                "Isolated worker has no application imports, DB credentials or finance APIs"
            ),
            "gold_read_only_after_both_seals": True,
        },
    )
    print("Post-seal scoring completed; aggregate metadata written, no model calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    score(args.runs, args.source)
