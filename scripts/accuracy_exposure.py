"""Offline TRAIN/DEV actual-request exposure analysis; no provider calls."""

import argparse
from pathlib import Path

from accuracy_development import coverage
from external_eval.accuracy_nli import packet
from external_eval.source import load_json, write_json

from clearledger.source_semantics import semantic_source
from clearledger.source_spans import text_source


def measure(root: Path) -> None:
    totals: dict[tuple[str, int, int, str], dict[str, float]] = {}
    for source in sorted((root / "inputs/contract").glob("*.json")):
        split = source.stem.split("-", 1)[0]
        p = load_json(source)
        gold = load_json(root / "scorer-only/contract" / source.name)
        lookup = {g["hypothesis_id"]: g for g in gold}
        cat = semantic_source(text_source(p["document_id"], [p["text"]]))
        for size in (17, 5, 1):
            for k in (20, 40):
                for strategy in ("local", "global", "hybrid"):
                    key = (split, size, k, strategy)
                    t = totals.setdefault(
                        key,
                        {
                            "gold_chars": 0,
                            "found_chars": 0,
                            "positive_pairs": 0,
                            "complete_pairs": 0,
                            "source_fraction_sum": 0,
                        },
                    )
                    for i in range(0, len(p["hypotheses"]), size):
                        pack = packet(
                            cat,
                            p["hypotheses"][i : i + size],
                            request=f"offline-{source.stem}-{i}",
                            strategy=strategy,
                            k=k,
                        )
                        for h in p["hypotheses"][i : i + size]:
                            g = lookup[h["hypothesis_id"]]
                            if not g["evidence"]:
                                continue
                            spans = [
                                pack.registry.resolve(a, scope=pack.registry.scope)
                                for a in pack.selectable[h["hypothesis_id"]]
                            ]
                            total, found, complete = coverage(
                                g["evidence"], [(s.start, s.end) for s in spans]
                            )
                            t["gold_chars"] += total
                            t["found_chars"] += found
                            t["positive_pairs"] += 1
                            t["complete_pairs"] += complete
                            t["source_fraction_sum"] += sum(len(s.text) for s in spans) / max(
                                1, len(p["text"])
                            )
    out = []
    for (split, size, k, strategy), t in totals.items():
        out.append(
            {
                "split": split,
                "batch_size": size,
                "k": k,
                "strategy": strategy,
                "character_recall": t["found_chars"] / max(1, t["gold_chars"]),
                "complete_coverage": t["complete_pairs"] / max(1, t["positive_pairs"]),
                "mean_source_fraction": t["source_fraction_sum"] / max(1, t["positive_pairs"]),
            }
        )
    write_json(root / "actual-request-ceilings.json", out)
    print("Actual request selectable-pool ceilings saved; selected DEV rows:")
    for row in out:
        if row["split"] == "dev" and row["k"] == 20:
            print(row)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    measure(p.parse_args().root)
