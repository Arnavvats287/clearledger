"""Offline evaluation preparation/scoring CLI. No model or production application access."""

import argparse
import subprocess
from pathlib import Path
from typing import Any

from external_eval.contracts import (
    ContractOutput,
    DocileOutput,
    Edge,
    ProviderMetadata,
)
from external_eval.gold import (
    check_seal,
    contract_gold,
    docile_gold,
    docile_scorer_view,
    ledger_processor_gold,
    seal_predictions,
    verify_gold_sources,
)
from external_eval.scorers import kile_predictions, score_contract, score_docile, score_edges
from external_eval.source import (
    contract_packets,
    docile_packet,
    load_json,
    load_plan,
    no_links,
    project_recbench_sources,
    read_packets,
    sha256,
    verify_source_tables,
    write_json,
    write_packets,
)
from pydantic import ValidationError


def load_outputs(path: Path, model: Any) -> list[Any]:
    no_links(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("OUTPUT_TOO_LARGE")
    with path.open(encoding="utf8") as stream:
        return [model.model_validate_json(line) for line in stream if line.strip()]


def prepare(source: Path, runs: Path, plan_path: Path, tier: str = "adapter") -> dict[str, Any]:
    if tier not in {"adapter", "scored"}:
        raise ValueError("UNKNOWN_TIER")
    plan = load_plan(plan_path)
    no_links(source)
    no_links(runs)
    if source.resolve() == runs.resolve() or source.resolve() in runs.resolve().parents:
        raise ValueError("OUTPUT_INSIDE_SOURCE")
    result: dict[str, Any] = {"plan_sha256": sha256(plan_path), "inference": False, "packets": {}}
    nli = plan["datasets"]["contract-nli"]
    split = "dev" if tier == "adapter" else "test"
    packets = contract_packets(
        source / "contract-nli" / f"{split}.json", nli["ids"][tier], nli["hypothesis_ids"]
    )
    result["packets"]["contract-nli"] = write_packets(
        runs / "contractnli-v1" / "inputs" / tier, packets
    )
    doc_packets = [
        docile_packet(source / "docile" / "ocr" / f"{key}.json", key)
        for key in plan["datasets"]["docile"]["ids"][tier]
    ]
    result["packets"]["docile"] = write_packets(runs / "docile-v1" / "inputs" / tier, doc_packets)
    for name in ("contractnli-v1", "docile-v1", "recbench-v1"):
        for directory in ("inputs", "adapter", "scored"):
            path = runs / name / directory
            no_links(path)
            path.mkdir(parents=True, exist_ok=True)
    if tier == "adapter":
        result["packets"]["recbench-small"] = project_recbench_sources(
            source / "recbench-small", runs / "recbench-v1" / "inputs" / "sources"
        )
    result["recbench"] = "Four original source CSVs only, no application adapter or predictions"
    result["source_hashes"] = {
        f"contract_{split}": sha256(source / "contract-nli" / f"{split}.json")
    }
    result["packet_document_counts"] = {k: len(v) for k, v in result["packets"].items()}
    manifest_name = (
        "projection-manifest.json" if tier == "adapter" else "projection-scored-manifest.json"
    )
    write_json(runs / "phase1-v1" / manifest_name, result)
    return result


def packet_set(runs: Path, name: str) -> dict[str, Any]:
    manifest = load_json(runs / "phase1-v1" / "projection-manifest.json")
    folder = "contractnli-v1" if name == "contract-nli" else "docile-v1"
    return read_packets(runs / folder / "inputs" / "adapter", manifest["packets"][name], name)


def validate_contract_dev(source: Path, runs: Path, plan_path: Path) -> dict[str, Any]:
    plan = load_plan(plan_path)
    packets = packet_set(runs, "contract-nli")
    # Empty offline format probes, not model predictions or an accuracy experiment.
    outputs = [
        ContractOutput(
            document_id=p.document_id,
            answers=[],
            metadata=ProviderMetadata(provider="offline-format-probe", failure="MISSING_OUTPUT"),
        )
        for p in packets.values()
    ]
    nli = plan["datasets"]["contract-nli"]
    gold = contract_gold(
        source / "contract-nli" / "dev.json", nli["ids"]["adapter"], nli["hypothesis_ids"]
    )
    result = score_contract(packets, outputs, gold)
    if result["pairs"] != 51 or result["counts"]["abstentions"] != 51:
        raise ValueError("DEV_SCORER_SELFTEST_FAILED")
    report = {
        "status": "PASS",
        "documents": len(packets),
        "pairs": result["pairs"],
        "mode": "Empty offline format probes; no model predictions or model accuracy",
        "gold_split_accessed": "dev only; selected three documents only",
        "metrics_implemented": sorted(result),
        "inference": False,
    }
    write_json(runs / "phase1-v1" / "contract-dev-validation.json", report)
    return report


def validate_docile_dev(
    source: Path, runs: Path, plan_path: Path, evaluator: Path
) -> dict[str, Any]:
    plan = load_plan(plan_path)
    packets = packet_set(runs, "docile")
    # No inferred fields: validate a real source-only roundtrip separately from KILE scoring.
    aligned = 0
    geometry_probes = {}
    from external_eval.contracts import InvoiceReference, Quote

    for packet in packets.values():
        found = False
        for page in packet.pages:
            for word in page.words:
                quote = Quote(text=page.text[word.start : word.end], start=word.start, end=word.end)
                probe = DocileOutput(
                    document_id=packet.document_id,
                    invoice_references=[
                        InvoiceReference(value=quote.text[:200], quote=quote, page=page.page)
                    ],
                    metadata=ProviderMetadata(provider="offline-geometry-probe"),
                )
                native, _ = kile_predictions(packet, probe)
                if native:
                    found = True
                    geometry_probes[packet.document_id] = native
                    if native[0]["bbox"] != [
                        word.box.left,
                        word.box.top,
                        word.box.right,
                        word.box.bottom,
                    ]:
                        raise ValueError("GEOMETRY_ROUNDTRIP_FAILED")
                    break
            if found:
                break
        aligned += found
    if aligned != len(packets):
        raise ValueError("NO_UNIQUE_SOURCE_QUOTE")
    outputs = [
        DocileOutput(
            document_id=k,
            invoice_references=[],
            metadata=ProviderMetadata(provider="offline-format-probe"),
        )
        for k in packets
    ]
    custom = score_docile(
        packets,
        outputs,
        docile_gold(source / "docile", plan["datasets"]["docile"]["ids"]["adapter"]),
    )
    view = runs / "phase1-v1" / "docile-scorer-only" / "adapter-format-v1"
    scope = docile_scorer_view(
        source / "docile", list(packets), view, "clearledger_train_adapter_v1"
    )
    predictions = runs / "docile-v1" / "adapter" / "source-geometry-format-fixture.json"
    # Official 0.3.5 rejects an entirely empty prediction set. These are explicitly
    # source-word geometry fixtures, NOT inferred invoice IDs or model predictions.
    write_json(
        predictions,
        {k: geometry_probes[k] for k in load_json(view / "clearledger_train_adapter_v1.json")},
    )
    official_result = runs / "docile-v1" / "adapter" / "source-geometry-format-result.json"
    command = [
        str(evaluator),
        "--task",
        "KILE",
        "--dataset-path",
        str(view),
        "--split",
        scope["split"],
        "--predictions",
        str(predictions),
        "--evaluate-x-shot-subsets",
        "",
        "--evaluate-fieldtypes",
        "--evaluate-also-text",
        "--store-evaluation-result",
        str(official_result),
    ]
    # No shell, no model transport. Output is scorer-only and never fed to prediction.
    completed = subprocess.run(command, capture_output=True, timeout=120, check=False)
    log = runs / "phase1-v1" / "docile-native-source-geometry-check.log"
    no_links(log)
    with log.open("xb") as stream:
        stream.write(completed.stdout + completed.stderr)
    if completed.returncode:
        raise ValueError("OFFICIAL_EVALUATOR_FAILED_SEE_LOCAL_LOG")
    report = {
        "status": "PASS",
        "source_documents": len(packets),
        "geometry_roundtrips": aligned,
        "secondary_metric_documents": custom["documents"],
        "official_scope": scope,
        "native_command": command,
        "mode": "Source-word geometry format fixtures, NOT model predictions or performance",
        "inference": False,
    }
    write_json(runs / "phase1-v1" / "docile-dev-validation.json", report)
    return report


def score_future(args: argparse.Namespace) -> None:
    # Not invoked in Phase1. Gold access only after prediction/source/plan seals verified.
    plan = load_plan(args.plan)
    dataset = plan["datasets"][args.dataset]
    manifest = load_json(args.manifest)
    if manifest["plan_sha256"] != sha256(args.plan):
        raise ValueError("MANIFEST_PLAN_MISMATCH")
    packet_manifest = manifest["packets"][args.dataset]
    check_seal(args.predictions, args.seal, packet_manifest, sha256(args.plan))
    if args.dataset == "recbench-small":
        verify_source_tables(args.inputs, packet_manifest)
    inventory = args.plan.parent / "inventory" / "complete-v1" / "inventory.json"
    verify_gold_sources(inventory, plan, args.dataset, args.source, args.tier)
    if args.dataset == "recbench-small":
        # No payout->bank scorer exists.
        result = score_edges(
            ledger_processor_gold(args.source / "csv" / "truth_ledger_processor.csv"),
            load_outputs(args.predictions, Edge),
        )
    else:
        packets = read_packets(args.inputs, packet_manifest, args.dataset)
        ids = dataset["ids"][args.tier]
        if set(packets) != set(ids):
            raise ValueError("PACKETS_NOT_FROZEN_SELECTION")
        if args.dataset == "contract-nli":
            split = "dev" if args.tier == "adapter" else "test"
            gold = contract_gold(args.source / f"{split}.json", ids, dataset["hypothesis_ids"])
            result = score_contract(packets, load_outputs(args.predictions, ContractOutput), gold)
        else:
            doc_gold = docile_gold(args.source, ids)
            outputs = load_outputs(args.predictions, DocileOutput)
            result = score_docile(packets, outputs, doc_gold)
            # All native predictions produced from source packets before scorer view filtering.
            kile = {o.document_id: kile_predictions(packets[o.document_id], o)[0] for o in outputs}
            for key in packets:
                kile.setdefault(key, [])
            invoice_ids = {g.document_id for g in doc_gold if g.is_invoice}
            result["official_tool_status"] = (
                "READY"
                if any(kile[key] for key in invoice_ids)
                else "NO_PREDICTIONS_OFFICIAL_0_3_5_REJECTS_EMPTY_SET"
            )
            write_json(
                args.output.with_suffix(".kile.json"),
                {key: values for key, values in kile.items() if key in invoice_ids},
            )
            docile_scorer_view(
                args.source,
                ids,
                args.output.with_suffix(".native-view"),
                "clearledger_val_v1" if args.tier == "scored" else "clearledger_train_adapter_v1",
            )
    write_json(args.output, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["prepare", "validate-contract-dev", "validate-docile-dev", "seal", "score"],
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--evaluator", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tier", choices=["adapter", "scored"], default="adapter")
    parser.add_argument("--dataset", choices=["contract-nli", "docile", "recbench-small"])
    args = parser.parse_args()
    required = {
        "prepare": ("source", "runs"),
        "validate-contract-dev": ("source", "runs"),
        "validate-docile-dev": ("source", "runs", "evaluator"),
        "seal": ("predictions", "output", "manifest", "dataset"),
        "score": ("source", "predictions", "seal", "manifest", "inputs", "output", "dataset"),
    }
    if any(getattr(args, key) is None for key in required[args.action]):
        parser.error("MISSING_REQUIRED_ARGUMENTS")
    if args.action == "prepare":
        prepare(args.source, args.runs, args.plan, args.tier)
    elif args.action == "validate-contract-dev":
        validate_contract_dev(args.source, args.runs, args.plan)
    elif args.action == "validate-docile-dev":
        validate_docile_dev(args.source, args.runs, args.plan, args.evaluator)
    elif args.action == "seal":
        load_plan(args.plan)
        manifest = load_json(args.manifest)
        if manifest["plan_sha256"] != sha256(args.plan):
            raise ValueError("MANIFEST_PLAN_MISMATCH")
        seal_predictions(
            args.predictions, args.output, manifest["packets"][args.dataset], sha256(args.plan)
        )
    else:
        score_future(args)
    print("Offline operation completed. No model inference or financial application access.")


if __name__ == "__main__":
    try:
        main()
    except ValidationError:
        raise SystemExit("EVALUATION_SCHEMA_REJECTED") from None
