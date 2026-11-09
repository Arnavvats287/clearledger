"""Score saved TRAIN/DEV formulation attempts against the unchanged reference."""

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from accuracy_development import coverage
from accuracy_score import scoped_packet
from contradiction_run import EXCEPTION, NEGATION
from external_eval.accuracy_nli import Packet, packet, rows
from external_eval.contracts import Answer, ContractOutput, ContractPacket, ProviderMetadata
from external_eval.contradiction import LABELS, VARIANTS, raw_label
from external_eval.scorers import GoldNli, score_contract
from external_eval.source import load_json, sha256, write_json
from external_phase2_score import performance

from clearledger.source_semantics import semantic_source
from clearledger.source_spans import digest, text_source

SCOPE = re.compile(r"\b(?:party|parties|recipient|representative|only|each|affiliate)\w*\b", re.I)
TIME = re.compile(r"\b(?:during|after|before|until|termination|expiration|year|month)\w*\b", re.I)


def references(row: dict[str, Any]) -> list[Any]:
    return [
        value
        for key in ("aliases", "support_evidence", "conflict_evidence")
        if isinstance(items := row.get(key), list)
        for value in items
    ]


def taxonomy(
    gold: GoldNli,
    view: Packet,
    text: str,
    row: dict[str, Any],
    raw: str | None,
    grounded: str | None,
    failure: str | None,
    stage_status: str,
) -> list[str]:
    if grounded == "Contradiction":
        return []
    result = []
    if raw in {"Entailment", "NotMentioned"}:
        result.append("PREDICTED_" + raw.upper())
    elif raw is None:
        result.append("MALFORMED_OR_MISSING" if stage_status == "SUCCESS" else "REQUEST_FAILURE")
    if failure:
        result.append("LOCAL_VALIDATION_REJECTION")
    offered = set(view.selectable[gold.hypothesis_id])
    intervals = {
        a: (s.start, s.end)
        for a in offered
        if (s := view.registry.resolve(a, scope=view.registry.scope))
    }
    _, _, complete = coverage(gold.evidence, list(intervals.values()))
    selected = [intervals[a] for a in references(row) if isinstance(a, str) and a in intervals]
    _, overlap, _ = coverage(gold.evidence, selected)
    if complete and raw in {"Entailment", "NotMentioned"}:
        result.append("EVIDENCE_AVAILABLE_WRONG_SEMANTIC_DECISION")
    if not overlap:
        result.append("ANNOTATED_CONFLICT_NOT_SELECTED")
    elif raw in {"Entailment", "NotMentioned"}:
        result.append("ANNOTATED_CONFLICT_OVERLAP_WRONG_LABEL")
        conflict = row.get("conflict_evidence", [])
        if row.get("relation") == "CONFLICT" or (
            isinstance(conflict, list)
            and coverage(
                gold.evidence,
                [intervals[a] for a in conflict if isinstance(a, str) and a in intervals],
            )[1]
        ):
            result.append("EXPLICIT_CONFLICT_ROLE_WRONG_LABEL")
    context = " ".join(text[a:b] for a, b in gold.evidence)
    for name, pattern in (
        ("PARTY_SCOPE", SCOPE),
        ("TEMPORAL", TIME),
        ("EXCEPTION", EXCEPTION),
        ("NEGATION", NEGATION),
    ):
        if pattern.search(context):
            result.append("SOURCE_CUE_" + name)
    return result or ["OTHER"]


def summarize(
    root: Path,
    baseline: Path,
    jobs: list[dict[str, Any]],
    variant: str,
    split: str,
    sanity: set[tuple[str, str]],
) -> dict[str, Any]:
    sources, raw_outputs, grounded_outputs, gold_rows = {}, [], [], []
    counter: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    detailed = []
    phase = f"nli-global-minimal-{split}" if variant == "reference" else f"nli-{variant}-{split}"
    for job in jobs:
        if job["variant"] != phase:
            continue
        source = ContractPacket.model_validate(load_json(root / job["input"]))
        key = source.document_id
        sources[key] = source
        view = packet(
            semantic_source(text_source(key, [source.text])),
            [h.model_dump() for h in source.hypotheses],
            request=job["job_id"],
            strategy="global",
            k=20,
        )
        result = load_json(root / "predictions" / f"{job['job_id']}.json")
        expected = (
            job.get("packet_sha256") or result["selection_configuration"]["synthesis_packet_sha256"]
        )
        if digest(view.payload) != expected:
            raise ValueError("SCORER_REFERENCE_PACKET_CHANGED")
        ids = {h.hypothesis_id for h in source.hypotheses}
        found, duplicates, extras = rows(result.get("raw"), ids, stage="answers")
        # The row parser marks every expected ID unavailable for an invalid envelope.
        # Only IDs actually observed in the envelope can be duplicate rows.
        counter["duplicate_hypotheses"] += len(duplicates & found.keys())
        counter["extra_rows"] += extras
        counter["document_failures"] += not found
        counter["missing_rows"] += len(ids - found.keys())
        accepted = ContractOutput.model_validate(result["output"])
        grounded_outputs.append(accepted)
        grounded_by_h = {
            answer.hypothesis_id: answer.predicted_label for answer in accepted.answers
        }
        reasons = {
            item["hypothesis_id"]: item["reason"] for item in result["diagnostics"].get("items", [])
        }
        raw_answers = []
        raw_by_h = {}
        offered = {b.alias for b in view.registry.bindings}
        for h, row in found.items():
            for alias in references(row):
                counter["declared_aliases"] += 1
                if not isinstance(alias, str) or alias not in offered:
                    counter["unknown_aliases"] += 1
                elif alias not in view.selectable[h]:
                    counter["outside_scope_aliases"] += 1
            label = raw_label(row, variant)
            if variant == "binary":
                counter["malformed_binary_decisions"] += label is None
                counter["invalid_conflicts"] += (
                    row.get("support_present") is True
                    and row.get("explicit_conflict_present") is True
                )
            else:
                counter["missing_label_fields"] += "predicted_label" not in row
                counter["malformed_labels"] += (
                    "predicted_label" in row and row["predicted_label"] not in LABELS
                )
            if label is not None and h not in duplicates:
                raw_by_h[h] = label
                raw_answers.append(
                    Answer.model_validate(
                        {"hypothesis_id": h, "predicted_label": label, "evidence_quotes": []}
                    )
                )
        raw_outputs.append(
            ContractOutput(
                document_id=key,
                answers=raw_answers,
                metadata=ProviderMetadata(provider="diagnostic-raw"),
            )
        )
        for g in load_json(baseline / "scorer-only/contract" / Path(job["input"]).name):
            gold = GoldNli(
                g["document_id"],
                g["hypothesis_id"],
                g["label"],
                tuple(tuple(p) for p in g["evidence"]),
            )
            gold_rows.append(gold)
            if gold.label == "Contradiction":
                h = gold.hypothesis_id
                tags = taxonomy(
                    gold,
                    view,
                    source.text,
                    found.get(h, {}),
                    raw_by_h.get(h),
                    grounded_by_h.get(h),
                    reasons.get(h),
                    result["metadata"]["status"],
                )
                errors.update(tags)
                if tags:
                    detailed.append({"source_id": key, "hypothesis_id": h, "tags": tags})
    result = {
        "raw": score_contract(sources, raw_outputs, gold_rows),
        "grounded": score_contract(sources, grounded_outputs, gold_rows),
        "format_and_alias": dict(counter),
        "contradiction_taxonomy": dict(errors),
        "contradiction_items": detailed,
        "performance": performance(root, phase),
    }
    if split == "train":
        selected = [g for g in gold_rows if (g.document_id, g.hypothesis_id) in sanity]
        if len(selected) != len(sanity) or len(sanity) != 36:
            raise ValueError("TRAIN_SANITY_SCOPE_CHANGED")
        scope = {
            d: scoped_packet(p, ids)
            for d, p in sources.items()
            if (ids := {h for s, h in sanity if s == d})
        }
        result["train_sanity"] = score_contract(
            scope,
            [
                o.model_copy(
                    update={
                        "answers": [
                            a for a in o.answers if (o.document_id, a.hypothesis_id) in sanity
                        ]
                    }
                )
                for o in grounded_outputs
                if o.document_id in scope
            ],
            selected,
        )
    return result


def score(root: Path, prior: Path, *, output_name: str = "results.json") -> None:
    if Path(output_name).name != output_name or not output_name.endswith(".json"):
        raise ValueError("RESULT_FILENAME_REQUIRED")
    config = load_json(root / "config/campaign.json")
    if any(not (root / "predictions" / f"{j['job_id']}.json").is_file() for j in config["jobs"]):
        raise ValueError("INCOMPLETE_DEVELOPMENT_MATRIX")
    manifest_path = root / "scorer-only/predeclared.json"
    if (
        sha256(manifest_path) != config["scorer_manifest_sha256"]
        or sha256(prior / "development-seal.json") != config["reference_seal_sha256"]
    ):
        raise ValueError("FROZEN_SCORER_INPUT_CHANGED")
    baseline = prior / "baseline"
    old_jobs = load_json(baseline / "config/campaign.json")["jobs"]
    sanity = {(r["document_id"], r["hypothesis_id"]) for r in load_json(manifest_path)["sanity"]}
    results = {
        variant: {
            split: summarize(
                baseline if variant == "reference" else root,
                baseline,
                old_jobs if variant == "reference" else config["jobs"],
                variant,
                split,
                sanity,
            )
            for split in ("dev", "train")
        }
        for variant in ("reference", *VARIANTS)
    }
    write_json(root / "scorer-only" / output_name, results)
    for name, splits in results.items():
        for split, data in splits.items():
            print(
                name,
                split,
                "raw/grounded accuracy",
                data["raw"]["accuracy"],
                data["grounded"]["accuracy"],
                "contradiction F1",
                data["grounded"]["per_class"]["Contradiction"]["f1"],
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output-name", default="results.json")
    args = parser.parse_args()
    score(args.root, args.prior, output_name=args.output_name)
