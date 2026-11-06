"""Trusted TRAIN/DEV preparation and offline ceilings. Never selects held-out IDs."""

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from external_eval.gold import contract_gold
from external_eval.source import contract_packets, load_json, normalized, sha256, write_json

from clearledger.source_invoice_candidates import candidates, compact
from clearledger.source_ocr import from_ocr
from clearledger.source_semantics import context, rank, semantic_source
from clearledger.source_spans import Span, make_span, text_source


def union(intervals: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return out


def coverage(
    gold: Sequence[tuple[int, int]], found: Sequence[tuple[int, int]]
) -> tuple[int, int, bool]:
    g, p = union(gold), union(found)
    total = sum(b - a for a, b in g)
    overlap = sum(max(0, min(b, d) - max(a, c)) for a, b in g for c, d in p)
    complete = total > 0 and overlap == total
    return total, overlap, complete


def overlap_box(a: Sequence[float], b: Sequence[float]) -> float:
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (aa + bb - inter) if aa + bb > inter else 0


def prepare(runs: Path, source: Path, revision: str = "v1") -> None:
    root = runs / f"accuracy-development-{revision}"
    root.mkdir(exist_ok=False)
    old = load_json(runs / "phase3-v1/config/source-manifest.json")
    # Only existing dev/train adapter IDs and additional source-ID-selected TRAIN IDs.
    dev_ids = old["contract_smoke"]["ids"]
    train = load_json(source / "contract-nli/train.json")
    train_ids = sorted(
        (str(d["id"]) for d in train["documents"]),
        key=lambda i: hashlib.sha256(("accuracy-dev|nli|" + i).encode()).hexdigest(),
    )[:8]
    hypothesis_ids = list(train["labels"])
    invoice_train = load_json(source / "docile/train.json")
    initial = old["docile_smoke"]["ids"]
    rest = sorted(
        (i for i in invoice_train if i not in initial),
        key=lambda i: hashlib.sha256(("accuracy-dev|invoice|" + i).encode()).hexdigest(),
    )
    invoice_ids = initial + rest[: 32 - len(initial)]
    manifest = {
        "protocol": "accuracy-development-v1",
        "not_heldout": True,
        "contract_dev_ids": dev_ids,
        "contract_train_ids": train_ids,
        "docile_train_ids": invoice_ids,
        "docile_live_ids": invoice_ids[:16],
        "metrics": {
            "retrieval": "micro gold-character recall and complete interval coverage; "
            "context separate",
            "candidate_occurrence": "exact normalized value and page plus bbox IoU >=0.5",
            "normalization": "NFC + outer trim only; no case/punctuation/zero changes",
        },
        "source_split_hashes": {
            n: sha256(source / n)
            for n in ("contract-nli/train.json", "contract-nli/dev.json", "docile/train.json")
        },
    }
    write_json(root / "development-manifest.json", manifest)
    retrieval = []
    for split, ids in (("dev", dev_ids), ("train", train_ids)):
        packets = contract_packets(source / f"contract-nli/{split}.json", ids, hypothesis_ids)
        gold = contract_gold(source / f"contract-nli/{split}.json", ids, hypothesis_ids)
        for p in packets:
            write_json(
                root / f"inputs/contract/{split}-{p.document_id}.json", p.model_dump(mode="json")
            )
            items = [g for g in gold if g.document_id == p.document_id]
            write_json(
                root / f"scorer-only/contract/{split}-{p.document_id}.json",
                [asdict(g) for g in items],
            )
            cat = semantic_source(text_source(p.document_id, [p.text]))
            extras: list[Span] = []
            for g in items:
                for a, b in g.evidence:
                    extras.append(
                        make_span(cat.source, 1, a, b, len(cat.source.spans) + len(extras))
                    )
            # Explicit TRAIN/DEV oracle exception; no labels or gold markers in worker inputs.
            write_json(
                root / f"inputs/oracle/{split}-{p.document_id}.json",
                {"source_ranges": sorted(set((s.start, s.end) for s in extras))},
            )
            questions = {h.hypothesis_id: h.text for h in p.hypotheses}
            for g in items:
                if not g.evidence:
                    continue
                ranking = rank(cat, questions[g.hypothesis_id], limit=40)
                for k in (5, 10, 20, 40):
                    for adjacent in (False, True):
                        chosen = context(cat, ranking[:k]) if adjacent else ranking[:k]
                        total, matched, complete = coverage(
                            g.evidence, [(s.start, s.end) for s in chosen]
                        )
                        retrieval.append(
                            {
                                "split": split,
                                "document_id": p.document_id,
                                "hypothesis_id": g.hypothesis_id,
                                "k": k,
                                "adjacent": adjacent,
                                "gold_chars": total,
                                "found_chars": matched,
                                "complete": complete,
                                "visible_chars": sum(len(s.text) for s in chosen),
                                "document_chars": len(p.text),
                            }
                        )
    write_json(root / "scorer-only/retrieval-details.json", retrieval)
    rows = []
    for identifier in invoice_ids:
        original = source / "docile/ocr" / f"{identifier}.json"
        canonical = from_ocr(identifier, load_json(original), source_hash=sha256(original))
        annotation = load_json(source / "docile/annotations" / f"{identifier}.json")
        write_json(
            root / f"inputs/invoice/{identifier}.json",
            {"document_id": identifier, "canonical_source": asdict(canonical)},
        )
        applicable = annotation["metadata"]["document_type"] == "tax_invoice"
        fields = (
            [f for f in annotation["field_extractions"] if f["fieldtype"] == "document_id"]
            if applicable
            else []
        )
        write_json(
            root / f"scorer-only/invoice/{identifier}.json",
            {"is_invoice": applicable, "fields": fields},
        )
        c = candidates(canonical)
        compact_packet, _ = compact(c)
        per = []
        for field in fields:
            matches = []
            for index, item in enumerate(c.items, 1):
                s = c.source.resolve(
                    item.span_id,
                    expected_hash=canonical.source_hash,
                    expected_version=canonical.source_version,
                )
                if normalized(item.value) == normalized(field["text"]):
                    box = field["bbox"]
                    correct = (
                        s.page == field["page"] + 1
                        and s.bbox is not None
                        and overlap_box(s.bbox, box) >= 0.5
                    )
                    matches.append((index, correct))
            per.append(
                {
                    "value_rank": min((i for i, _ in matches), default=None),
                    "occurrence_rank": min((i for i, correct in matches if correct), default=None),
                }
            )
        rows.append(
            {
                "document_id": identifier,
                "is_invoice": applicable,
                "targets": per,
                "candidate_count": len(c.items),
                "complete": c.complete,
                "fallbacks": len(canonical.fallbacks),
                "missing_boxes": sum(s.bbox is None for s in canonical.spans),
                "compact_bytes": len(json.dumps(compact_packet, ensure_ascii=False).encode()),
            }
        )
    write_json(root / "scorer-only/candidate-details.json", rows)
    print(
        "Development projection complete:3 DEV +8 TRAIN legal,32 TRAIN invoices; "
        "no test/validation source read"
    )


def summarize(runs: Path, revision: str = "v1") -> None:
    root = runs / f"accuracy-development-{revision}"
    details = load_json(root / "scorer-only/retrieval-details.json")
    retrieval = []
    for split in ("dev", "train"):
        for k in (5, 10, 20, 40):
            for adjacent in (False, True):
                rows = [
                    x
                    for x in details
                    if (x["split"], x["k"], x["adjacent"]) == (split, k, adjacent)
                ]
                denom = sum(x["gold_chars"] for x in rows)
                retrieval.append(
                    {
                        "split": split,
                        "k": k,
                        "adjacent": adjacent,
                        "positive_pairs": len(rows),
                        "character_recall": sum(x["found_chars"] for x in rows) / denom
                        if denom
                        else None,
                        "complete_evidence_coverage": sum(x["complete"] for x in rows) / len(rows)
                        if rows
                        else None,
                        "mean_source_fraction": sum(
                            x["visible_chars"] / max(1, x["document_chars"]) for x in rows
                        )
                        / max(1, len(rows)),
                    }
                )
    ds = load_json(root / "scorer-only/candidate-details.json")
    targets = [t for d in ds for t in d["targets"]]
    candidate = [
        {
            "k": k,
            "targets": len(targets),
            "value_recall": sum(
                t["value_rank"] is not None and t["value_rank"] <= k for t in targets
            )
            / max(1, len(targets)),
            "occurrence_recall": sum(
                t["occurrence_rank"] is not None and t["occurrence_rank"] <= k for t in targets
            )
            / max(1, len(targets)),
        }
        for k in (8, 16, 32, 64, 128, 256, 1024)
    ]
    result = {
        "retrieval": retrieval,
        "candidate_recall": candidate,
        "invoice_documents": len(ds),
        "applicable_invoices": sum(x["is_invoice"] for x in ds),
        "candidate_incomplete": sum(not x["complete"] for x in ds),
    }
    write_json(root / "offline-ceilings.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "summarize"])
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--revision", choices=["v1", "v2"], default="v1")
    args = p.parse_args()
    if args.action == "prepare":
        if args.source is None:
            raise ValueError("SOURCE_REQUIRED")
        prepare(args.runs, args.source, args.revision)
    else:
        summarize(args.runs, args.revision)
