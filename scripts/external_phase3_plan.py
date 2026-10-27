"""Freeze source-ID-based Phase 3 selection; never interpret any annotations."""

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from external_eval.source import load_json, load_plan, sha256, write_json


def freeze(runs: Path, source: Path) -> None:
    old = load_plan(runs / "evaluation-plan-v1.json")
    if sha256(runs / "evaluation-plan-v1.json") != (
        "a83dc857f3f4ee8d0f6468fd945358504b59173e4ad55f53845bec3c7d00589d"
    ):
        raise ValueError("V1_PLAN_CHANGED")
    seed = "clearledger-grounding-phase3-v1"
    tasks = {}
    for name, count, split in (("contract-nli", 24, "test"), ("docile", 100, "val")):
        raw = load_json(source / name / f"{split}.json")
        ids = [str(d["id"]) for d in raw["documents"]] if name == "contract-nli" else raw
        excluded = set(old["datasets"][name]["ids"]["scored"])
        ordered = sorted(
            set(ids) - excluded,
            key=lambda i: hashlib.sha256(f"{seed}|{name}|{i}".encode()).hexdigest(),
        )
        chosen = ordered[:count]
        if len(chosen) != count:
            raise ValueError("INSUFFICIENT_UNUSED_SOURCE_IDS")
        tasks[name] = {
            "split": split,
            "ids": chosen,
            "adapter_ids": old["datasets"][name]["ids"]["adapter"],
            "excluded_v1_scored_ids": sorted(excluded),
            "count": count,
            "source_split_sha256": sha256(source / name / f"{split}.json"),
        }
    root = runs / "phase3-v1"
    value = {
        "protocol": "clearledger-grounding-phase3-v1",
        "frozen_utc": datetime.now(UTC).isoformat(),
        "seed": seed,
        "selection": "lowest SHA256(seed|dataset|source-ID); no gold stratification",
        "baseline": {
            "plan_sha256": sha256(runs / "evaluation-plan-v1.json"),
            "completion_sha256": sha256(runs / "phase2-v1/scoring/completion-metadata.json"),
        },
        "datasets": tasks,
        "model": "gemini-3.5-flash-lite",
        "retry_policy": "NONE",
        "generations_per_document": {"contract-nli": 2, "docile": 1},
        "max_generations_including_synthetic_and_smoke": 165,
        "per_request_input": {"contract-nli": 32768, "docile": 8192},
        "per_request_output": {"contract-nli": 4096, "docile": 1024},
        "pacing": {"http_operations_per_minute": 6, "callers": 1},
        "metrics": {
            "contract-nli": (
                "Original accuracy/macro/per-class F1, unsupported-conclusion rate and union "
                "character-overlap formulas; original quote scorer plus separately reported "
                "ID/span integrity"
            ),
            "docile": (
                "Original NFC+outer-trim and ID-set P/R/F1/denominators; source-ID localization "
                "resolves exact source tokens, no gold rescue; native official 0.3.5 unchanged"
            ),
        },
        "abstention": "All frozen documents remain in denominator; failed inputs never replaced",
        "gold": "SCORER_ONLY_AFTER_SEALS; no labels, annotations or evidence boundaries to worker",
        "development": (
            "Only train/dev and application-owned fixtures; no v1 final examples used for tuning"
        ),
    }
    path = root / "evaluation-plan.json"
    write_json(path, value)
    with path.with_suffix(".sha256").open("x", encoding="ascii") as stream:
        stream.write(sha256(path) + "\n")
    print("Fresh Phase 3 selection frozen:", sha256(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    freeze(args.runs, args.source)
