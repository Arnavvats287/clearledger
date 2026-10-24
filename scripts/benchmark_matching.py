"""Numeric algorithm microbenchmarks only; no dataset creation or financial imports."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from platform import python_version
from statistics import median
from uuid import UUID

from clearledger.advanced_domain import Limits, subsets


def main():
    limits = Limits()
    # Tiny integer vectors probe complexity/collision/pruning boundaries independently of datasets.
    workloads = {
        "unique_24_pool": (tuple(2**i for i in range(24)), 255),
        "size_pruning_24": (tuple(2**i for i in range(24)), sum(2**i for i in (0, 3, 9, 17))),
        "collisions_24": ((1,) * 24, 6),
        "worst_cap_32": ((1,) * 32, 17),
        "candidate_cap_33": ((1,) * 33, 17),
    }
    measurements = {"python": python_version(), "limits": asdict(limits), "workloads": {}}
    for name, (amounts, target) in workloads.items():
        results = [
            subsets(tuple((UUID(int=i + 1), a) for i, a in enumerate(amounts)), target, limits)
            for _ in range(7)
        ]
        assert all(result.work <= limits.max_work for result in results)
        assert all(result.outcome != "UNIQUE" or result.search_exhaustive for result in results)
        measurements["workloads"][name] = {
            "outcomes": sorted({result.outcome for result in results}),
            "reasons": sorted({result.reason for result in results}),
            "median_ms": median(result.elapsed_ns for result in results) / 1_000_000,
            "max_ms": max(result.elapsed_ns for result in results) / 1_000_000,
            "max_work": max(result.work for result in results),
            "max_returned": max(len(result.candidates) for result in results),
        }
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "local-data"
        / "verification"
        / ("matching-benchmark-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
    print(json.dumps(measurements, indent=2))
    print(f"Log: {path}")


if __name__ == "__main__":
    main()
