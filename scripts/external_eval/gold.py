"""Scorer-only gold readers. Never imported by source projection or packet readers."""

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .contracts import Edge
from .scorers import GoldInvoice, GoldNli
from .source import load_json, no_links, sha256, write_json


def contract_gold(path: Path, ids: list[str], hypothesis_ids: list[str]) -> list[GoldNli]:
    data = load_json(path)
    selected = {str(d["id"]): d for d in data["documents"] if str(d["id"]) in set(ids)}
    if set(selected) != set(ids):
        raise ValueError("MISSING_GOLD_DOCUMENT")
    result = []
    for identifier in ids:
        doc = selected[identifier]
        sets = doc["annotation_sets"]
        if len(sets) != 1:
            raise ValueError("UNSUPPORTED_MULTIPLE_ANNOTATORS")
        for key in hypothesis_ids:
            answer = sets[0]["annotations"][key]
            intervals = tuple(tuple(doc["spans"][i]) for i in answer["spans"])
            result.append(GoldNli(identifier, key, answer["choice"], intervals))
    return result


def docile_gold(root: Path, ids: list[str]) -> list[GoldInvoice]:
    result = []
    for identifier in ids:
        annotation = load_json(root / "annotations" / f"{identifier}.json")
        result.append(
            GoldInvoice(
                identifier,
                annotation["metadata"]["document_type"] == "tax_invoice",
                tuple(
                    f["text"]
                    for f in annotation["field_extractions"]
                    if f["fieldtype"] == "document_id"
                ),
            )
        )
    return result


def docile_scorer_view(root: Path, ids: list[str], output: Path, split: str) -> dict[str, Any]:
    """Native conditional invoice/document_id task, original field values/boxes unchanged."""
    no_links(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("SCORER_VIEW_NOT_EMPTY")
    selected = []
    for identifier in ids:
        path = root / "annotations" / f"{identifier}.json"
        annotation = load_json(path)
        if annotation["metadata"]["document_type"] != "tax_invoice":
            continue
        annotation["field_extractions"] = [
            f for f in annotation["field_extractions"] if f["fieldtype"] == "document_id"
        ]
        # KILE-only view; source originals are never modified.
        annotation["line_item_extractions"] = []
        write_json(output / "annotations" / path.name, annotation)
        write_json(output / "ocr" / path.name, load_json(root / "ocr" / path.name))
        selected.append(identifier)
    write_json(output / f"{split}.json", selected)
    return {
        "documents": len(selected),
        "split": split,
        "scope": "Native conditional KILE document_id only; not full DocILE",
        "original_gold_boxes_unchanged": True,
    }


def ledger_processor_gold(path: Path) -> Iterator[Edge]:
    no_links(path)
    if path.name != "truth_ledger_processor.csv":
        raise ValueError("UNSUPPORTED_TRUTH_TASK")
    with path.open(encoding="utf8", newline="") as stream:
        for row in csv.DictReader(stream):
            yield Edge(txn_id=row["txn_id"], line_id=row["line_id"])


def seal_predictions(
    path: Path, output: Path, packet_manifest: dict[str, str], plan_hash: str
) -> None:
    # Gold is not an argument to sealing. Later scoring rejects mutation of either side.
    write_json(
        output,
        {
            "predictions_sha256": sha256(path),
            "plan_sha256": plan_hash,
            "packet_manifest": packet_manifest,
        },
    )


def check_seal(path: Path, seal: Path, packet_manifest: dict[str, str], plan_hash: str) -> None:
    value = load_json(seal)
    if value != {
        "predictions_sha256": sha256(path),
        "plan_sha256": plan_hash,
        "packet_manifest": packet_manifest,
    }:
        raise ValueError("PREDICTION_SEAL_MISMATCH")


def verify_gold_sources(
    inventory_path: Path, plan: dict[str, Any], dataset: str, source: Path, tier: str
) -> None:
    """Hash check before interpreting answers; no gold fallback or rescue is permitted."""
    if sha256(inventory_path) != plan["inventory_sha256"]:
        raise ValueError("INVENTORY_HASH_MISMATCH")
    inspection = load_json(inventory_path)["datasets"][dataset]["inspection"]
    if dataset == "contract-nli":
        split = "dev" if tier == "adapter" else "test"
        if sha256(source / f"{split}.json") != inspection["splits"][split]["sha256"]:
            raise ValueError("GOLD_SOURCE_CHANGED")
    elif dataset == "docile":
        ids = set(plan["datasets"][dataset]["ids"][tier])
        hashes = {item["path"]: item["sha256"] for item in inspection["selected_file_sha256"]}
        for identifier in ids:
            for folder in ("annotations", "ocr"):
                relative = f"{folder}/{identifier}.json"
                if sha256(source / relative) != hashes[relative]:
                    raise ValueError("GOLD_SOURCE_CHANGED")
    elif dataset == "recbench-small":
        expected = inspection["csv"]["truth_ledger_processor"]["sha256"]
        if sha256(source / "csv" / "truth_ledger_processor.csv") != expected:
            raise ValueError("GOLD_SOURCE_CHANGED")
    else:
        raise ValueError("UNSUPPORTED_TRUTH_TASK")
