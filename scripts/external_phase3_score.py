"""Fresh held-out scoring after both seals; v1 scorers/artifacts remain immutable."""

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from external_eval.contracts import ContractOutput, DocileOutput
from external_eval.gold import contract_gold, docile_gold, docile_scorer_view
from external_eval.phase3 import read_source
from external_eval.scorers import GoldInvoice, prf, ratio, score_contract
from external_eval.source import load_json, normalized, read_packets, sha256, write_json
from external_phase2_score import performance

from clearledger.source_candidates import discover


def verify(root: Path) -> dict[str, Any]:
    c: dict[str, Any] = load_json(root / "inference-config.json")
    if (
        sha256(root / "evaluation-plan.json") != c["frozen_plan_sha256"]
        or sha256(root / "config/source-manifest.json") != c["source_manifest_sha256"]
        or sha256(root / "baseline-v1-hashes.json") != c["baseline_inventory_sha256"]
    ):
        raise ValueError("FROZEN_PLAN_OR_MANIFEST_CHANGED")
    if (
        sha256(root / "inference-config.json")
        != (root / "inference-config.sha256").read_text().strip()
    ):
        raise ValueError("CONFIG_CHANGED")
    for phase in ("contract_final", "docile_final"):
        seal = load_json(root / "seals" / f"{phase}.json")
        if (
            seal["predictions_sha256"] != sha256(root / "predictions" / f"{phase}.jsonl")
            or seal["grounding_sha256"]
            != sha256(root / "logs/metadata" / f"{phase}-grounding.json")
            or seal["config_sha256"] != sha256(root / "inference-config.json")
        ):
            raise ValueError("SEAL_CHANGED")
    for file, digest in c["code_hashes"].items():
        if sha256(Path(file)) != digest:
            raise ValueError("FROZEN_CODE_CHANGED")
    baseline = load_json(root / "baseline-v1-hashes.json")
    actual = {
        str(p.relative_to(root.parent / "phase2-v1"))
        for p in (root.parent / "phase2-v1").rglob("*")
        if p.is_file()
    }
    if actual != set(baseline["file_metadata"]):
        raise ValueError("V1_ARTIFACT_SET_CHANGED")
    for name, expected in baseline["file_metadata"].items():
        stat = (root.parent / "phase2-v1" / name).stat()
        if [stat.st_size, stat.st_mtime_ns] != expected:
            raise ValueError("V1_ARTIFACT_METADATA_CHANGED")
    for name, digest in baseline["sealed_sha256"].items():
        if sha256(root.parent / "phase2-v1" / name) != digest:
            raise ValueError("V1_ARTIFACT_CHANGED")
    return c


def score_docile_canonical(
    gold: list[GoldInvoice],
    outputs: list[DocileOutput],
    diagnostics: list[dict[str, Any]],
    packets: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    counts: Counter[str] = Counter()
    quote: Counter[str] = Counter()
    native: dict[str, list[dict[str, Any]]] = {g.document_id: [] for g in gold if g.is_invoice}
    docs = {o.document_id: o for o in outputs}
    diag = {row["document_id"]: row for row in diagnostics}
    for g in gold:
        o = docs[g.document_id]
        details = diag[g.document_id]
        source = read_source(packets[g.document_id]["canonical_source"])
        candidates = discover(source)
        emitted = {normalized(r.value) for r in o.invoice_references}
        supported = set()
        seen = set()
        for chosen in details.get("selected_spans", []):
            span = candidates.source.resolve(
                chosen["span_id"],
                expected_hash=source.source_hash,
                expected_version=source.source_version,
            )
            if (
                span.text != chosen["text"]
                or span.bbox != tuple(chosen["bbox"] or ())
                and span.bbox is not None
            ):
                raise ValueError("SOURCE_SELECTION_CHANGED")
            value = normalized(span.text)
            if value in seen:
                counts["duplicate_fields"] += 1
                continue
            seen.add(value)
            quote["VALID"] += 1
            if span.bbox is not None:
                supported.add(value)
                counts["localized"] += 1
                if g.is_invoice:
                    native[g.document_id].append(
                        {
                            "fieldtype": "document_id",
                            "text": value,
                            "page": span.page - 1,
                            "bbox": list(span.bbox),
                            "score": 0.0,
                        }
                    )
            else:
                counts["missing_coordinates"] += 1
        if emitted != seen:
            raise ValueError("OUTPUT_SELECTION_MISMATCH")
        expected = {normalized(v) for v in g.references} if g.is_invoice else set()
        correct = expected & supported
        counts.update(tp=len(correct), fp=len(emitted - correct), fn=len(expected - correct))
        failed = details.get("status") == "ADAPTER_INPUT_FAILURE"
        counts["exact_set_match"] += not failed and emitted == expected and supported == emitted
        counts["covered_documents"] += bool(emitted)
        counts["abstained_documents"] += not emitted
        counts["adapter_input_failures"] += failed
        counts["partial_or_fallback_documents"] += bool(details.get("fallbacks"))
        counts["non_invoice_false_emissions"] += len(emitted) if not g.is_invoice else 0
        counts["non_invoice_documents"] += not g.is_invoice
        counts["unsupported_fields"] += len(emitted - correct)
        counts["emitted_fields"] += len(emitted)
        counts["failed_model_outputs"] += o.metadata.failure != "NONE" and not failed
    return {
        "documents": len(gold),
        "invoice_id": prf(counts["tp"], counts["fp"], counts["fn"]),
        "counts": counts,
        "exact_set_match": ratio(counts["exact_set_match"], len(gold)),
        "coverage": ratio(counts["covered_documents"], len(gold)),
        "quote_validity": ratio(quote["VALID"], counts["emitted_fields"]),
        "localization_validity": ratio(counts["localized"], counts["emitted_fields"]),
        "unsupported_field_rate": ratio(counts["unsupported_fields"], counts["emitted_fields"]),
    }, native


def score(runs: Path, source: Path) -> None:
    root = runs / "phase3-v1"
    config = verify(root)
    plan = load_json(root / "evaluation-plan.json")
    results = {}
    for name, dataset in (("contract_final", "contract-nli"), ("docile_final", "docile")):
        spec = config["phases"][name]
        outputs = [
            json.loads(s)
            for s in (root / "predictions" / f"{name}.jsonl")
            .read_text(encoding="utf8")
            .splitlines()
        ]
        if [o["document_id"] for o in outputs] != spec["ids"]:
            raise ValueError("FROZEN_DENOMINATOR_CHANGED")
        diagnostics = load_json(root / "logs/metadata" / f"{name}-grounding.json")
        if dataset == "contract-nli":
            if (
                sha256(source / dataset / "test.json")
                != plan["datasets"][dataset]["source_split_sha256"]
            ):
                raise ValueError("GOLD_SOURCE_CHANGED")
            packets = read_packets(Path(spec["input_directory"]), spec["packet_hashes"], dataset)
            ids = [h.hypothesis_id for h in next(iter(packets.values())).hypotheses]
            gold = contract_gold(source / dataset / "test.json", spec["ids"], ids)
            result = score_contract(
                packets, [ContractOutput.model_validate(o) for o in outputs], gold
            )
            checks = [c for row in diagnostics for c in row.get("checks", [])]
            result["policy_downgrades"] = sum(
                c["raw_label"] != c["effective_label"] for c in checks
            )
            result["accepted_span_references"] = sum(len(c["span_ids"]) for c in checks)
            result["span_id_integrity_failures"] = 0
            # Original quote/character scoring retains ambiguous-string rules.
        else:
            packets = {}
            for identifier in spec["ids"]:
                p = Path(spec["input_directory"]) / f"{identifier}.json"
                if sha256(p) != spec["packet_hashes"][p.name]:
                    raise ValueError("SOURCE_PACKET_CHANGED")
                packets[identifier] = load_json(p)
                original = source / dataset / "ocr" / p.name
                if sha256(original) != packets[identifier]["canonical_source"]["source_hash"]:
                    raise ValueError("ORIGINAL_OCR_CHANGED")
            gold_docs = docile_gold(source / dataset, spec["ids"])
            result, native = score_docile_canonical(
                gold_docs, [DocileOutput.model_validate(o) for o in outputs], diagnostics, packets
            )
            native_path = root / "scoring/docile-conditional.kile.json"
            write_json(native_path, native)
            view = root / "scoring/docile-native-view"
            scope = docile_scorer_view(
                source / dataset, spec["ids"], view, "clearledger_phase3_val"
            )
            result["native_scope"] = scope
            if any(native.values()):
                command = [
                    str(runs / "phase1-v1/venv/Scripts/docile_evaluate.exe"),
                    "--task",
                    "KILE",
                    "--dataset-path",
                    str(view),
                    "--split",
                    "clearledger_phase3_val",
                    "--predictions",
                    str(native_path),
                    "--evaluate-x-shot-subsets",
                    "",
                    "--evaluate-fieldtypes",
                    "--evaluate-also-text",
                    "--store-evaluation-result",
                    str(root / "scoring/docile-official.json"),
                ]
                completed = subprocess.run(command, capture_output=True, timeout=180, check=False)
                (root / "scoring/docile-official.log").write_bytes(
                    completed.stdout + completed.stderr
                )
                result["official_status"] = (
                    "COMPUTED" if completed.returncode == 0 else "NOT COMPUTABLE"
                )
            else:
                result["official_status"] = "NOT COMPUTABLE: ALL EMPTY"
        result["performance"] = performance(root, name)
        write_json(root / "scoring" / f"{name}-metrics.json", result)
        results[dataset] = result
    write_json(
        root / "scoring/aggregate.json",
        {
            "results": results,
            "all_phase_performance": {name: performance(root, name) for name in config["phases"]},
            "v1_preserved": True,
            "financial_mutations": 0,
            "source_span_authority": False,
        },
    )
    print("Fresh Phase 3 scoring complete; no model calls or v1 changes.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    args = p.parse_args()
    score(args.runs, args.source)
