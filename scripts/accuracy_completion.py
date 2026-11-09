"""Prepare and measure the previously selected development corpus, then gate live calls."""

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from accuracy_campaign import ROOT, run
from accuracy_development import coverage, overlap_box, union
from external_eval.accuracy_nli import Strategy, packet
from external_eval.phase3 import read_source
from external_eval.source import load_json, no_links, normalized, sha256, write_json

from clearledger.document_contract import MAX_DOCUMENT_BYTES, ExtractionError
from clearledger.document_runtime import parse_bounded
from clearledger.source_candidates import Candidates
from clearledger.source_invoice_candidates import candidates, compact, fallback_candidates
from clearledger.source_semantics import semantic_source
from clearledger.source_spans import Page, Source, build, text_source


def pdf_text(path: Path, identifier: str) -> Source | None:
    no_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_DOCUMENT_BYTES:
        return None
    raw = path.read_bytes()
    try:
        parsed = parse_bounded(raw, "application/pdf")
    except ExtractionError:
        return None
    import hashlib

    return build(
        identifier,
        tuple(Page(i, p) for i, p in enumerate(parsed["pages"], 1)),
        source_hash=hashlib.sha256(raw).hexdigest(),
        version=parsed["parser_version"],
        kind="PDF_TEXT",
    )


def ranks(pool: Candidates, field: dict[str, Any]) -> tuple[int | None, int | None]:
    value = location = None
    for i, item in enumerate(pool.items, 1):
        if normalized(item.value) != normalized(field["text"]):
            continue
        if value is None:
            value = i
        span = pool.source.resolve(
            item.span_id,
            expected_hash=pool.source.source_hash,
            expected_version=pool.source.source_version,
        )
        if (
            span.page == field["page"] + 1
            and span.bbox
            and overlap_box(span.bbox, field["bbox"]) >= 0.5
        ):
            location = i
            break
    return value, location


def missed_reason(
    primary: Candidates, text: Source | None, field: dict[str, Any], rank: int | None
) -> str:
    if primary.admission == "OUT_OF_SCOPE":
        return "G_DOCUMENT_ADMISSION"
    if rank is not None:
        return "F_OCCURRENCE_GEOMETRY"
    value = normalized(field["text"])
    pages = [normalized(p.text) for p in primary.source.pages]
    if any(value in p for p in pages):
        return "A_OCR_CANDIDATE_CONSTRUCTION"
    if any(re.search(r"\s+".join(map(re.escape, value)), p) for p in pages):
        return "B_SPLIT_OCR_TOKENS"
    key = re.sub(r"[\W_]", "", value)
    if key and any(key in re.sub(r"[\W_]", "", p) for p in pages):
        return "C_PUNCTUATION_OR_SPACING"
    if text and any(value in normalized(p.text) for p in text.pages):
        return "D_PDF_TEXT_ONLY"
    return "E_SOURCE_ABSENT" if text else "H_PDF_TEXT_UNAVAILABLE"


def retrieval(root: Path, contract_files: list[Path]) -> None:
    results: list[dict[str, Any]] = []
    strategies: tuple[tuple[Strategy, int], ...] = (
        ("local", 20),
        ("local", 40),
        ("context", 20),
        ("context", 40),
        ("global", 20),
        ("section", 20),
        ("section-hybrid", 20),
    )
    for path in contract_files:
        data = load_json(path)
        gold = {x["hypothesis_id"]: x for x in load_json(root / "scorer-only/contract" / path.name)}
        source = semantic_source(text_source(data["document_id"], [data["text"]]))
        for size in (1, 5, 17):
            for strategy, k in strategies:
                for start in range(0, 17, size):
                    batch = data["hypotheses"][start : start + size]
                    p = packet(source, batch, request=f"measure-{start}", strategy=strategy, k=k)
                    spans = {
                        b.alias: p.registry.resolve(b.alias, scope=p.registry.scope)
                        for b in p.registry.bindings
                    }
                    positions = union([(s.start, s.end) for s in spans.values()])
                    payload_bytes = len(
                        json.dumps(p.payload, ensure_ascii=False, separators=(",", ":")).encode()
                    )
                    request: dict[str, Any] = {
                        "split": path.stem.split("-")[0],
                        "size": size,
                        "k": k,
                        "strategy": strategy,
                        "source_fraction": sum(b - a for a, b in positions) / len(data["text"]),
                        "token_estimate_bytes_div4": (payload_bytes + 3) // 4,
                        "aliases": len(spans),
                        "gold_chars": 0,
                        "found_chars": 0,
                        "complete": 0,
                        "positives": 0,
                    }
                    for h in batch:
                        key = h["hypothesis_id"]
                        intervals = gold[key]["evidence"]
                        if not intervals:
                            continue
                        visible = [spans[a] for a in p.selectable[key]]
                        total, found, complete = coverage(
                            intervals, [(s.start, s.end) for s in visible]
                        )
                        request["gold_chars"] += total
                        request["found_chars"] += found
                        request["complete"] += complete
                        request["positives"] += 1
                    results.append(request)
    groups: dict[tuple[str, int, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        groups[row["split"], row["size"], row["strategy"], row["k"]].append(row)
    out = []
    for (split, size, group_strategy, k), rows in groups.items():
        out.append(
            {
                "split": split,
                "size": size,
                "strategy": group_strategy,
                "k": k,
                "character_recall": sum(r["found_chars"] for r in rows)
                / sum(r["gold_chars"] for r in rows),
                "complete_coverage": sum(r["complete"] for r in rows),
                "positives": sum(r["positives"] for r in rows),
                **{
                    f"mean_{field}": sum(r[field] for r in rows) / len(rows)
                    for field in ("source_fraction", "token_estimate_bytes_div4", "aliases")
                },
            }
        )
    write_json(root / "retrieval-comparison.json", out)


def prepare(runs: Path, docile: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    prior = runs / "accuracy-development-v2"
    manifest = load_json(prior / "development-manifest.json")
    config = load_json(prior / "config/campaign.json")
    # Reuse only the established IDs and fixed, explicitly scoped inputs.
    files = []
    for split in ("dev", "train"):
        for identifier in manifest[f"contract_{split}_ids"]:
            name = f"{split}-{identifier}.json"
            for folder in ("inputs/contract", "scorer-only/contract", "inputs/oracle"):
                write_json(root / folder / name, load_json(prior / folder / name))
            files.append(root / "inputs/contract" / name)
    details = []
    for identifier in manifest["docile_train_ids"]:
        path = Path("inputs/invoice") / f"{identifier}.json"
        raw = load_json(prior / path)
        text = pdf_text(docile / "pdfs" / f"{identifier}.pdf", identifier)
        source = read_source(raw["canonical_source"])
        pool = candidates(source)
        supplement = fallback_candidates(pool, text) if text else None
        if text:
            raw["pdf_text_source"] = asdict(text)
        write_json(root / path, raw)
        gold_path = Path("scorer-only/invoice") / path.name
        gold = load_json(prior / gold_path)
        write_json(root / gold_path, gold)
        count = min(8, len(supplement.items)) if supplement else 0
        rows = []
        for field in gold["fields"]:
            vr, lr = ranks(pool, field)
            fr = ranks(supplement, field)[0] if supplement else None
            rows.append(
                {
                    "ocr_value_rank": vr,
                    "ocr_occurrence_rank": lr,
                    "pdf_value_rank": fr,
                    "miss_reason": missed_reason(pool, text, field, vr) if lr is None else None,
                    "live_value_visible": (vr is not None and vr <= 64 - count)
                    or (fr is not None and fr <= count),
                    "live_occurrence_visible": lr is not None and lr <= 64 - count,
                }
            )
        primary, _ = compact(pool, limit=64 - count)
        backup_rows = (
            compact(supplement, limit=count)[0]["candidates"] if supplement and count else []
        )
        details.append(
            {
                "source_id": identifier,
                "pdf_available": text is not None,
                "targets": rows,
                "candidate_count": len(pool.items),
                "pdf_candidates_offered": count,
                "packet_bytes": len(
                    json.dumps({**primary, "pdf": backup_rows}, ensure_ascii=False).encode()
                ),
            }
        )
    write_json(root / "invoice-ceilings.json", details)
    retrieval(root, files)

    for control in config["controls"]:
        write_json(root / control["input"], load_json(prior / control["input"]))
    for path in files:
        split = path.stem.split("-")[0]
        for strategy in ("section", "section-hybrid") if split == "dev" else ("section-hybrid",):
            variant = f"nli-{split}-{strategy}"
            config["jobs"].append(
                {
                    "job_id": f"{variant}-{path.stem}",
                    "variant": variant,
                    "kind": "contract",
                    "input": str(path.relative_to(root)),
                    "mode": "direct",
                    "split": split,
                    "hypotheses": [h["hypothesis_id"] for h in load_json(path)["hypotheses"]],
                    "strategy": strategy,
                    "k": 20,
                }
            )
    for job in [*config["jobs"], *config["controls"]]:
        job["input_sha256"] = sha256(root / job["input"])
    config.update(
        run_root=str(root),
        protocol="development-ablation-completion-1",
        simple_provider_shape=True,
        retry_policy="DEVELOPMENT_TRANSIENT_2",
    )
    hashed_files = [
        *map(Path, config["code_hashes"]),
        ROOT / "scripts/accuracy_schema_probe.py",
        Path(__file__),
    ]
    config["code_hashes"] = {str(f): sha256(f) for f in hashed_files}
    config["estimated_generations"] = sum(
        2 if j["mode"] in {"legacy", "plan", "select"} else 1 for j in config["jobs"]
    )
    path = root / "config/campaign.json"
    write_json(path, config)
    path.with_suffix(".sha256").write_text(sha256(path) + "\n", encoding="ascii")
    print(
        f"Prepared {len(config['jobs'])} development jobs, "
        f"{config['estimated_generations']} base generations"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preflight", "run"])
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--docile", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.docile is None:
            parser.error("--docile is required for preparation")
        prepare(args.runs, args.docile, args.root.resolve())
    else:
        run(args.runs, control=args.action == "preflight", development_root=args.root.resolve())
