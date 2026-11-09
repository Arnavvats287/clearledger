"""TRAIN/DEV-only scoring and diagnostic decomposition. Never imported by prediction worker."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from accuracy_development import overlap_box
from external_eval.accuracy_nli import RawDecision
from external_eval.contracts import Answer, ContractOutput, ContractPacket, ProviderMetadata
from external_eval.scorers import GoldNli, score_contract
from external_eval.source import load_json, normalized, write_json
from external_phase2_score import performance


def group(name: str) -> str:
    if name.startswith("nli-batch5-"):
        return "nli-batch5"
    if name.startswith("nli-single-"):
        return "nli-single"
    return name


def scoped_packet(packet: ContractPacket, selected: set[str]) -> ContractPacket:
    hypotheses = [h for h in packet.hypotheses if h.hypothesis_id in selected]
    if not hypotheses or {h.hypothesis_id for h in hypotheses} != selected:
        raise ValueError("INVALID_DEVELOPMENT_HYPOTHESIS_SCOPE")
    return packet.model_copy(update={"hypotheses": hypotheses})


def score(runs: Path, *, development_root: Path | None = None) -> None:
    root = development_root or runs / "accuracy-development-v2"
    config = load_json(root / "config/campaign.json")
    jobs = config["jobs"]
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        prediction_path = root / "predictions" / f"{job['job_id']}.json"
        if not prediction_path.exists():
            raise ValueError("INCOMPLETE_DEVELOPMENT_MATRIX")
        by_variant[group(job["variant"])].append({"job": job, "result": load_json(prediction_path)})
    oracle_ids = {row["result"]["source_id"] for row in by_variant.get("invoice-oracle", [])}
    if oracle_ids:
        by_variant["invoice-normal-paired"] = [
            row for row in by_variant["invoice-normal"] if row["result"]["source_id"] in oracle_ids
        ]
    single_ids: dict[str, set[str]] = defaultdict(set)
    for row in by_variant.get("nli-single", []):
        single_ids[row["result"]["source_id"]].update(row["job"]["hypotheses"])
    if single_ids:
        by_variant["nli-global-on-single-pairs"] = [
            {
                **row,
                "job": {**row["job"], "hypotheses": sorted(single_ids[row["result"]["source_id"]])},
            }
            for row in by_variant["nli-global"]
            if row["result"]["source_id"] in single_ids
        ]
    results: dict[str, Any] = {}
    for name, records in by_variant.items():
        if name.startswith("nli"):
            packets: dict[str, ContractPacket] = {}
            selected: dict[str, set[str]] = defaultdict(set)
            raw: dict[str, list[Answer]] = defaultdict(list)
            ground: dict[str, list[Answer]] = defaultdict(list)
            states: Counter[str] = Counter()
            reasons: Counter[str] = Counter()
            split_by_id = {}
            declared = 0
            malformed_labels = missing_label_fields = document_failures = 0
            for record in records:
                job, row = record["job"], record["result"]
                p = ContractPacket.model_validate(load_json(root / job["input"]))
                split_by_id[p.document_id] = job.get("split", "dev")
                packets[p.document_id] = p
                selected[p.document_id].update(job["hypotheses"])
                value = row.get("raw") or {}
                rows = value.get("answers")
                if not isinstance(rows, list) or not rows:
                    document_failures += 1
                for candidate in rows if isinstance(rows, list) else []:
                    if (
                        not isinstance(candidate, dict)
                        or candidate.get("hypothesis_id") not in job["hypotheses"]
                    ):
                        continue
                    identifiers = candidate.get("aliases", candidate.get("span_ids"))
                    if isinstance(identifiers, list):
                        declared += len(identifiers)
                    if "predicted_label" not in candidate:
                        missing_label_fields += 1
                    elif candidate["predicted_label"] not in (
                        "Entailment",
                        "Contradiction",
                        "NotMentioned",
                    ):
                        malformed_labels += 1
                    try:
                        label = RawDecision.model_validate(
                            {"predicted_label": candidate.get("predicted_label")}
                        ).predicted_label
                    except ValueError:
                        continue
                    raw[p.document_id].append(
                        Answer(
                            hypothesis_id=candidate["hypothesis_id"],
                            predicted_label=label,
                            evidence_quotes=[],
                        )
                    )
                output = ContractOutput.model_validate(row["output"])
                ground[p.document_id].extend(
                    answer for answer in output.answers if answer.hypothesis_id in job["hypotheses"]
                )
                diag = row["diagnostics"]
                if diag.get("legacy_rejected"):
                    states["LEGACY_DOCUMENT_REJECTION"] += 1
                for item in diag.get("items", []):
                    if item["hypothesis_id"] not in job["hypotheses"]:
                        continue
                    states[item["status"]] += 1
                    if item["reason"]:
                        reasons[item["reason"]] += 1
            gold: list[GoldNli] = []
            for identifier, ids in selected.items():
                path = root / f"scorer-only/contract/{split_by_id[identifier]}-{identifier}.json"
                gold.extend(
                    GoldNli(
                        x["document_id"],
                        x["hypothesis_id"],
                        x["label"],
                        tuple(tuple(p) for p in x["evidence"]),
                    )
                    for x in load_json(path)
                    if x["hypothesis_id"] in ids
                )

            def outputs(
                values: dict[str, list[Answer]], identifiers: list[str]
            ) -> list[ContractOutput]:
                # Duplicate hypothesis answers are independently invalid.
                out = []
                for identifier in identifiers:
                    counts = Counter(a.hypothesis_id for a in values[identifier])
                    answers = [a for a in values[identifier] if counts[a.hypothesis_id] == 1]
                    out.append(
                        ContractOutput(
                            document_id=identifier,
                            answers=answers,
                            metadata=ProviderMetadata(provider="gemini-development"),
                        )
                    )
                return out

            scope = {
                identifier: scoped_packet(packets[identifier], ids)
                for identifier, ids in selected.items()
            }
            raw_metrics = score_contract(scope, outputs(raw, list(selected)), gold)
            grounded = score_contract(scope, outputs(ground, list(selected)), gold)
            results[name] = {
                "pairs": len(gold),
                "raw_semantic": raw_metrics,
                "grounded": grounded,
                "item_statuses": dict(states),
                "rejection_reasons": dict(reasons),
                "declared_aliases": declared,
                "invalid_alias_items": states["INVALID_ALIAS"],
                "malformed_labels": malformed_labels,
                "missing_label_fields": missing_label_fields,
                "document_failures": document_failures,
                "validator_rejections": sum(
                    states[k] for k in ("INVALID_ALIAS", "INVALID_EVIDENCE")
                ),
                "raw_quotes_intentionally_not_scored": True,
            }
        else:
            total = correct = locations = emitted = targets = invalid = declared = (
                false_non_invoice
            ) = 0
            gold_occurrences = recovered_occurrences = 0
            for record in records:
                row = record["result"]
                g = load_json(root / f"scorer-only/invoice/{row['source_id']}.json")
                expect = {normalized(f["text"]) for f in g["fields"]}
                pred = {normalized(f["value"]) for f in row["output"]["invoice_references"]}
                targets += len(expect)
                correct += len(expect & pred)
                emitted += len(pred)
                total += 1
                if not g["is_invoice"]:
                    false_non_invoice += len(pred)
                occurrences = set()
                gold_occurrences += len(g["fields"])
                for selected_span in row["diagnostics"].get("selected", []):
                    if not selected_span["bbox"]:
                        continue
                    matched = {
                        i
                        for i, field in enumerate(g["fields"])
                        if normalized(selected_span["value"]) == normalized(field["text"])
                        and selected_span["page"] == field["page"] + 1
                        and overlap_box(selected_span["bbox"], field["bbox"]) >= 0.5
                    }
                    locations += bool(matched)
                    occurrences.update(matched)
                recovered_occurrences += len(occurrences)
                invalid += row["diagnostics"].get("invalid_aliases", 0)
                declared += row["diagnostics"].get("declared_aliases", 0)
            results[name] = {
                "documents": total,
                "distinct_gold_values": targets,
                "emitted_values": emitted,
                "correct_values": correct,
                "value_precision": correct / emitted if emitted else None,
                "value_recall": correct / targets if targets else None,
                "source_and_occurrence_correct_selections": locations,
                "distinct_gold_occurrences": gold_occurrences,
                "distinct_gold_occurrences_recovered": recovered_occurrences,
                "invalid_aliases": invalid,
                "declared_aliases": declared,
                "non_invoice_false_emissions": false_non_invoice,
            }
    variants = sorted({j["variant"] for j in jobs})
    write_json(
        root / "development-results.json",
        {
            "results": results,
            "performance": {v: performance(root, v) for v in variants},
            "financial_authority": False,
            "not_heldout": True,
        },
    )
    for name, row in results.items():
        if name.startswith("nli"):
            print(
                name,
                "raw accuracy/F1",
                row["raw_semantic"]["accuracy"],
                row["raw_semantic"]["macro_f1"],
                "grounded",
                row["grounded"]["accuracy"],
                row["grounded"]["macro_f1"],
            )
        else:
            print(name, row)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--development-root", type=Path)
    args = p.parse_args()
    score(args.runs, development_root=args.development_root)
