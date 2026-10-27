"""Offline public-dataset metadata inventory. Never imports the application or a model.

Only the three explicitly supplied public child roots are traversed. Outputs contain
schemas/counts/provenance and label-independent IDs, never document/row/gold contents.
Annotations are read by this inspection/scorer-side process, not prediction code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SELECTION_VERSION = "clearledger-external-phase0-v1"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_ids(ids: list[str], domain: str, count: int) -> list[str]:
    """Independent of documents, gold labels, difficulty and model outputs."""
    if count < 0:
        raise ValueError("NEGATIVE_SAMPLE_COUNT")
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_INPUT_ID")
    return sorted(
        ids,
        key=lambda value: (
            hashlib.sha256(f"{SELECTION_VERSION}|{domain}|{value}".encode()).hexdigest(),
            value,
        ),
    )[:count]


def files(root: Path):
    if root.is_symlink() or root.is_junction():
        raise ValueError("LINKED_ROOT_REFUSED")
    for base, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            child = Path(base) / name
            if child.is_symlink() or child.is_junction():
                raise ValueError("LINKED_DESCENDANT_REFUSED")
        directories.sort()
        for name in sorted(names):
            yield Path(base) / name


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def inventory(root: Path, output: Path) -> dict:
    counts: Counter[str] = Counter()
    total = 0
    metadata = []
    index_hash = hashlib.sha256()
    with (output / f"{root.name}-files.jsonl").open("w", encoding="utf8") as index:
        for path in files(root):
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
            row = {"path": relative, "bytes": size}
            line = json.dumps(row, sort_keys=True) + "\n"
            index.write(line)
            index_hash.update(line.encode())
            total += size
            counts[path.suffix or "<none>"] += 1
            if path.suffix == ".py" or path.name.lower().startswith(
                ("readme", "license", "terms", "manifest", "pyproject", "setup", "config")
            ):
                metadata.append({**row, "sha256": digest(path)})
    return {
        "source_name": root.name,
        "local_path": str(root),
        "file_count": sum(counts.values()),
        "size_bytes": total,
        "extensions": counts,
        "path_size_index_sha256": index_hash.hexdigest(),
        "metadata_files": metadata,
        "index_strategy": "Sorted relative paths + byte sizes; not a content-integrity hash",
    }


def shape(value: object, depth: int = 0) -> object:
    if depth > 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: shape(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return {"type": "list", "item": shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def docile(root: Path) -> dict:
    splits = {
        name: json.loads((root / f"{name}.json").read_text(encoding="utf8"))
        for name in ("train", "val", "trainval")
    }
    selected = {
        "adapter": select_ids(splits["train"], "docile:adapter", 8),
        "scored": select_ids(splits["val"], "docile:scored", 50),
    }
    fields: Counter[str] = Counter()
    lines: Counter[str] = Counter()
    types: Counter[str] = Counter()
    currencies: Counter[str] = Counter()
    pages: Counter[int] = Counter()
    missing = Counter()
    first_schema = None
    for identifier in splits["trainval"]:
        for folder, suffix in (("annotations", ".json"), ("ocr", ".json"), ("pdfs", ".pdf")):
            if not (root / folder / (identifier + suffix)).is_file():
                missing[folder] += 1
        data = json.loads((root / "annotations" / f"{identifier}.json").read_text())
        if first_schema is None:
            first_schema = shape(data)
        fields.update(item["fieldtype"] for item in data["field_extractions"])
        lines.update(item["fieldtype"] for item in data["line_item_extractions"])
        metadata = data["metadata"]
        types[metadata.get("document_type", "UNKNOWN")] += 1
        currencies[metadata.get("currency", "UNKNOWN")] += 1
        pages[metadata.get("page_count", 0)] += 1
    archive = root / "annotated-trainval.zip"
    with zipfile.ZipFile(archive) as zipped:
        entries = [
            {"path": x.filename, "bytes": x.file_size, "crc32": f"{x.CRC:08x}"}
            for x in zipped.infolist()
            if not x.is_dir()
        ]
    central = json.dumps(sorted(entries, key=lambda x: x["path"]), sort_keys=True).encode()
    hashes = []
    for identifier in selected["adapter"] + selected["scored"]:
        for folder, suffix in (("pdfs", ".pdf"), ("ocr", ".json"), ("annotations", ".json")):
            path = root / folder / (identifier + suffix)
            hashes.append({"path": path.relative_to(root).as_posix(), "sha256": digest(path)})
    ocr = json.loads((root / "ocr" / f"{selected['adapter'][0]}.json").read_text())
    return {
        "splits": {
            k: {"count": len(v), "sha256": digest(root / f"{k}.json")} for k, v in splits.items()
        },
        "train_val_disjoint": not set(splits["train"]) & set(splits["val"]),
        "trainval_is_union": set(splits["trainval"]) == set(splits["train"]) | set(splits["val"]),
        "missing_files": missing,
        "field_taxonomy_observed": fields,
        "line_item_taxonomy_observed": lines,
        "document_types_scorer_only": types,
        "currencies_scorer_only": currencies,
        "page_count_distribution": pages,
        "annotation_shape": first_schema,
        "ocr_shape": shape(ocr),
        "selected_ids": selected,
        "selected_file_sha256": hashes,
        "archive": {
            "bytes": archive.stat().st_size,
            "members": len(entries),
            "central_directory_sha256": hashlib.sha256(central).hexdigest(),
        },
        "license": "UNKNOWN: no local license/readme/version or evaluator in root/archive",
        "version": "annotated-trainval archive; no explicit release version locally",
        "native_scorer_present": False,
    }


def contract_nli(root: Path) -> dict:
    result = {}
    all_ids: set[str] = set()
    for split in ("train", "dev", "test"):
        path = root / f"{split}.json"
        data = json.loads(path.read_text(encoding="utf8"))
        documents = data["documents"]
        ids = [str(d["id"]) for d in documents]
        if all_ids & set(ids):
            raise ValueError("CONTRACT_SPLIT_OVERLAP")
        all_ids.update(ids)
        # Selection occurs without consulting annotation choices or evidence.
        sample = select_ids(ids, f"contractnli:{split}", 3 if split == "dev" else 12)
        spans_valid = True
        choices: Counter[str] = Counter()
        hypothesis_counts: Counter[int] = Counter()
        for document in documents:
            length = len(document["text"])
            spans_valid &= all(0 <= start < end <= length for start, end in document["spans"])
            annotations = document["annotation_sets"][0]["annotations"]
            hypothesis_counts[len(annotations)] += 1
            choices.update(a["choice"] for a in annotations.values())
            spans_valid &= all(
                0 <= i < len(document["spans"]) for a in annotations.values() for i in a["spans"]
            )
        selected = [d for d in documents if str(d["id"]) in sample]
        result[split] = {
            "documents": len(documents),
            "hypotheses": len(data["labels"]),
            "pairs": sum(k * v for k, v in hypothesis_counts.items()),
            "label_names": sorted(choices),
            "hypotheses_per_document": hypothesis_counts,
            "spans_and_annotation_indices_valid": bool(spans_valid),
            "selected_document_ids": sample,
            "selected_hypothesis_ids": sorted(data["labels"]),
            "selected_text_characters": sum(len(d["text"]) for d in selected),
            "selected_text_max_characters": max(len(d["text"]) for d in selected),
            "sha256": digest(path),
            "document_shape": shape(documents[0]),
        }
    return {
        "splits": result,
        "license": "CC BY 4.0; local README, LICENSE and TERMS",
        "version": "README initial release 2021-10-05; no separate version tag",
        "native_scorer_present": False,
    }


def recbench(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    result = {}
    # CSV mirrors permit offline structural inspection without adding a Parquet engine.
    for path in sorted((root / "csv").glob("*.csv")):
        counts: Counter[str] = Counter()
        categories: dict[str, Counter] = {}
        primary: set[str] = set()
        duplicates = 0
        with path.open(encoding="utf8", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            for row in reader:
                counts["rows"] += 1
                key = row[headers[0]]
                duplicates += key in primary
                primary.add(key)
                for name, value in row.items():
                    if name in {
                        "currency",
                        "gross_currency",
                        "settle_currency",
                        "direction",
                        "type",
                        "line_type",
                        "status",
                        "relation",
                        "level",
                        "match_type",
                        "role",
                    }:
                        categories.setdefault(name, Counter())[value] += 1
                    if name.endswith("amount_minor"):
                        if not value:
                            counts[f"missing:{name}"] += 1
                            continue
                        try:
                            integer = int(value)
                        except ValueError:
                            counts[f"invalid_integer:{name}"] += 1
                            continue
                        counts[f"negative:{name}"] += integer < 0
                        counts[f"zero:{name}"] += integer == 0
        result[path.stem] = {
            "columns": headers,
            "counts": counts,
            "categories": categories,
            "unique_first_key_count": len(primary),
            "duplicate_first_key_rows": duplicates,
            "sha256": digest(path),
            "manifest_row_count": manifest["row_counts"].get(path.stem),
        }
        if path.stem == "bank_statements":
            result[path.stem]["selected_ids"] = {
                "adapter": select_ids(sorted(primary), "recbench:adapter", 16),
                "scored": [],
            }
            remaining = sorted(primary - set(result[path.stem]["selected_ids"]["adapter"]))
            result[path.stem]["selected_ids"]["scored"] = select_ids(
                remaining, "recbench:scored", 128
            )
    return {
        "manifest": manifest,
        "manifest_sha256": digest(root / "manifest.json"),
        "csv": result,
        "version": manifest["generator_version"],
        "license": "UNKNOWN: no local license or upstream README",
        "native_scorer_present": False,
        "parquet_engine_available": any(
            importlib.util.find_spec(x) for x in ("pyarrow", "fastparquet", "duckdb")
        ),
        "parquet_hash_status": "Publisher-declared hashes retained, not independently rehashed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source_root.absolute(), args.output.absolute()
    if source == output or source in output.parents:
        raise ValueError("OUTPUT_MUST_BE_OUTSIDE_DATASETS")
    if output.exists() and any(output.iterdir()):
        raise ValueError("REFUSE_TO_OVERWRITE_EXISTING_INVENTORY")
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "evaluation_utc": datetime.now(UTC).isoformat(),
        "selection_version": SELECTION_VERSION,
        "datasets": {},
    }
    for name, inspect in (
        ("docile", docile),
        ("contract-nli", contract_nli),
        ("recbench-small", recbench),
    ):
        root = source / name
        summary["datasets"][name] = {**inventory(root, output), "inspection": inspect(root)}
        write_json(output / f"{name}-inspection.json", summary["datasets"][name])
    write_json(output / "inventory.json", summary)
    print("Public dataset inventory saved; no inference/application/database was invoked.")


if __name__ == "__main__":
    main()
