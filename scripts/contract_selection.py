"""Predeclared final ContractNLI comparison on the existing development cohorts."""

import argparse
from pathlib import Path
from typing import Any

from accuracy_campaign import ROOT, run
from accuracy_score import score
from external_eval.accuracy_nli import (
    EVIDENCE_INSTRUCTION,
    SELECTION_INSTRUCTION,
    exact_label_provider_schema,
)
from external_eval.contracts import ContractPacket
from external_eval.source import load_json, sha256, write_json

from clearledger.source_spans import digest

BASELINE = (
    ("hybrid-minimal", "hybrid", "direct", "MINIMAL"),
    ("global-minimal", "global", "direct", "MINIMAL"),
    ("select-minimal", "global", "select", "MINIMAL"),
    ("hybrid-low", "hybrid", "direct", "LOW"),
)
STRONGER = (("flash-hybrid-minimal", "hybrid", "direct", "MINIMAL"),)


def prepare(prior: Path, root: Path, *, stronger: bool) -> None:
    old_config = prior / "config/campaign.json"
    seal = load_json(prior / "development-seal.json")
    if (
        seal["scope"] != "TRAIN_DEV_ONLY"
        or sha256(old_config) != seal["files"]["config/campaign.json"]
    ):
        raise ValueError("UNVERIFIED_DEVELOPMENT_SOURCE")
    previous = load_json(old_config)
    sources = {
        (j.get("split", "dev"), j["input"]): j["input_sha256"]
        for j in previous["jobs"]
        if j["kind"] == "contract"
    }
    if {split: sum(s == split for s, _ in sources) for split in {s for s, _ in sources}} != {
        "dev": 3,
        "train": 8,
    }:
        raise ValueError("DEVELOPMENT_COHORT_CHANGED")
    root.mkdir(parents=True, exist_ok=False)
    jobs = []
    candidates = STRONGER if stronger else BASELINE
    for (split, path), expected in sorted(sources.items()):
        relative = Path(path)
        if relative.parent != Path("inputs/contract") or not relative.name.startswith(split + "-"):
            raise ValueError("DEVELOPMENT_SOURCE_SCOPE")
        if sha256(prior / relative) != expected:
            raise ValueError("DEVELOPMENT_SOURCE_HASH_CHANGED")
        packet = ContractPacket.model_validate(load_json(prior / relative))
        if len(packet.hypotheses) != 17:
            raise ValueError("DEVELOPMENT_HYPOTHESIS_COUNT_CHANGED")
        write_json(root / relative, packet.model_dump(mode="json"))
        for name, strategy, mode, thinking in candidates:
            variant = f"nli-{name}-{split}"
            jobs.append(
                {
                    "job_id": f"{variant}-{packet.document_id}",
                    "variant": variant,
                    "kind": "contract",
                    "mode": mode,
                    "thinking": thinking,
                    "strategy": strategy,
                    "split": split,
                    "input": path,
                    "input_sha256": sha256(root / relative),
                    "k": 20,
                    "hypotheses": [h.hypothesis_id for h in packet.hypotheses],
                }
            )
    control_path = "inputs/control/legal.json"
    write_json(
        root / control_path,
        {
            "document_id": "synthetic-label-admission",
            "text": (
                "Copies may be retained. The recipient is expressly prohibited "
                "from licensing the copies."
            ),
            "hypotheses": [
                {"hypothesis_id": "H01", "text": "Copies may be retained."},
                {"hypothesis_id": "H02", "text": "The recipient may license the copies."},
                {"hypothesis_id": "H03", "text": "The parties must arbitrate disputes."},
            ],
        },
    )
    controls = []
    for mode, thinking in (
        (("direct", "MINIMAL"),)
        if stronger
        else (("direct", "MINIMAL"), ("direct", "LOW"), ("select", "MINIMAL"))
    ):
        name = f"control-{mode}-{thinking.lower()}"
        controls.append(
            {
                "job_id": name,
                "variant": name,
                "kind": "contract",
                "mode": mode,
                "thinking": thinking,
                "strategy": "global",
                "k": 20,
                "input": control_path,
                "input_sha256": sha256(root / control_path),
                "hypotheses": ["H01", "H02", "H03"],
            }
        )
    code = {*map(Path, previous["code_hashes"]), Path(__file__), ROOT / "scripts/accuracy_score.py"}
    config: dict[str, Any] = {
        "run_root": str(root),
        "protocol": "contract-selection-1",
        "model": "gemini-3.5-flash" if stronger else "gemini-3.5-flash-lite",
        "simple_provider_shape": True,
        "retry_policy": "DEVELOPMENT_TRANSIENT_2",
        "pacing": {"http_interval_seconds": 20 if stronger else 10},
        "limits": {
            "generations": 18 if stronger else 78,
            "input_tokens": 2_600_000,
            "output_tokens": 320_000,
        },
        "request_spec": {},
        "jobs": jobs,
        "controls": controls,
        "code_hashes": {str(path): sha256(path) for path in sorted(code)},
        "operator_quota": {
            "tier": "Free",
            "project": "existing operator-approved evaluation project",
        },
        "prompt_sha256": digest(SELECTION_INSTRUCTION),
        "selection_prompt_sha256": digest(EVIDENCE_INSTRUCTION),
        "schema_sha256": digest(exact_label_provider_schema()),
        "request_limits": {"input": 32768, "output_including_thinking": 4096},
        "few_shot": False,
        "selection_gates": {
            "malformed_labels": 0,
            "document_cascades": 0,
            "unknown_aliases": 0,
            "grounded_coverage_min": 0.95,
            "unsupported_assertion_rate_max": 0.25,
            "dev_macro_f1_min": 0.3954,
            "positive_contradiction_f1_on_each_split": True,
        },
    }
    path = root / "config/campaign.json"
    write_json(path, config)
    path.with_suffix(".sha256").write_text(sha256(path) + "\n", encoding="ascii")
    print(f"Prepared {len(jobs)} development jobs on the existing 11 documents")


def score_existing(prior: Path, root: Path) -> None:
    config = load_json(root / "config/campaign.json")
    files = {Path(job["input"]).name for job in config["jobs"]}
    for file in sorted(files):
        if not file.startswith(("dev-", "train-")):
            raise ValueError("DEVELOPMENT_SCORER_SCOPE")
        relative = Path("scorer-only/contract") / file
        gold = load_json(prior / relative)
        if (root / relative).exists():
            if load_json(root / relative) != gold:
                raise ValueError("DEVELOPMENT_GOLD_CHANGED")
        else:
            write_json(root / relative, gold)
    score(prior, development_root=root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preflight", "run", "score"])
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stronger", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.prior.resolve(), args.root.resolve(), stronger=args.stronger)
    elif args.action == "score":
        score_existing(args.prior.resolve(), args.root.resolve())
    else:
        run(
            args.prior.resolve(),
            control=args.action == "preflight",
            development_root=args.root.resolve(),
        )
