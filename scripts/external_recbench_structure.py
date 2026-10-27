"""Scorer-side public graph inspection; emits aggregates, never truth pairs."""

import argparse
import csv
from collections import Counter
from pathlib import Path

from external_inventory import digest, files, write_json


def rows(root: Path, name: str):
    with (root / "csv" / f"{name}.csv").open(encoding="utf8", newline="") as stream:
        yield from csv.DictReader(stream)


def inspect(root: Path) -> dict:
    # Check links before reading. This is not an application or prediction adapter.
    list(files(root))
    sources = {
        name: {row[key] for row in rows(root, name)}
        for name, key in (
            ("ledger", "txn_id"),
            ("settlement_lines", "line_id"),
            ("payouts", "payout_id"),
            ("bank_statements", "stmt_line_id"),
        )
    }
    output = {}
    for table, left, right, left_table, right_table in (
        ("truth_ledger_processor", "txn_id", "line_id", "ledger", "settlement_lines"),
        ("truth_line_payout", "line_id", "payout_id", "settlement_lines", "payouts"),
        ("truth_payout_bank", "payout_id", "stmt_line_id", "payouts", "bank_statements"),
    ):
        left_counts, right_counts = Counter(), Counter()
        pairs = set()
        missing_left, missing_right, duplicates = 0, 0, 0
        for row in rows(root, table):
            pair = (row[left], row[right])
            duplicates += pair in pairs
            pairs.add(pair)
            left_counts[pair[0]] += 1
            right_counts[pair[1]] += 1
            missing_left += pair[0] not in sources[left_table]
            missing_right += pair[1] not in sources[right_table]
        output[table] = {
            "edge_count": sum(left_counts.values()),
            "duplicate_pairs": duplicates,
            "left_degree_histogram": dict(Counter(left_counts.values())),
            "right_degree_histogram": dict(Counter(right_counts.values())),
            "edges_missing_left_source": missing_left,
            "edges_missing_right_source": missing_right,
        }
    line_payout = Counter()
    input_links = 0
    missing = 0
    for row in rows(root, "settlement_lines"):
        if row["payout_id"]:
            input_links += 1
            missing += row["payout_id"] not in sources["payouts"]
            line_payout[row["payout_id"]] += int(row["net_amount_minor"])
    mismatches = sum(
        line_payout[row["payout_id"]] != int(row["amount_minor"]) for row in rows(root, "payouts")
    )
    output["source_only_direct_links"] = {
        "settlement_rows_with_payout_id": input_links,
        "rows_missing_payout_source": missing,
        "payouts_with_all_linked_net_sum_different_from_amount": mismatches,
        "interpretation": "Arithmetic diagnostic only; duplicate/FX/group rules not assumed",
    }
    output["manifest_sha256"] = digest(root / "manifest.json")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("REFUSE_OVERWRITE")
    if args.root.resolve() in args.output.resolve().parents:
        raise ValueError("OUTPUT_INSIDE_DATASET")
    write_json(args.output, inspect(args.root))
    print("Scorer-only public structural aggregates written; no predictions executed.")


if __name__ == "__main__":
    main()
