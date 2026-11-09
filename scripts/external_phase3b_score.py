"""Read public gold only after both Phase 3B seals verify."""

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from accuracy_development import coverage, overlap_box
from external_eval.accuracy_nli import packet
from external_eval.contracts import ContractOutput, ContractPacket, DocileOutput
from external_eval.gold import contract_gold, docile_gold, docile_scorer_view
from external_eval.phase3 import read_source
from external_eval.scorers import prf, ratio, score_contract
from external_eval.source import load_json, normalized, sha256, write_json
from external_phase2_score import performance
from external_phase3b import frozen, verified, write_sealed

from clearledger.source_semantics import semantic_source
from clearledger.source_spans import digest, make_span, text_source


def sealed_predictions(root: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    config = frozen(root)
    plan = verified(root / "evaluation-plan.json")
    predictions = {}
    for kind, dataset in (("contract", "contract-nli"), ("invoice", "docile")):
        record = verified(root / "seals" / f"{kind}.json")
        if (
            record["status"],
            record["plan_sha256"],
            record["config_sha256"],
            record["source_manifest_sha256"],
        ) != (
            "SEALED",
            config["plan_sha256"],
            sha256(root / "inference-config.json"),
            config["source_manifest_sha256"],
        ):
            raise ValueError("PREDICTION_SEAL_IDENTITY_MISMATCH")
        expected = {f"predictions/{kind}-final.jsonl"}
        for job in config["jobs"]:
            if job["kind"] == kind:
                expected.add(f"predictions/{job['job_id']}.json")
                if kind == "invoice":
                    expected.add(f"predictions/offers/{job['job_id']}.json")
        actual = {Path(p).as_posix() for p in record["files"]}
        if actual != expected or any(sha256(root / p) != h for p, h in record["files"].items()):
            raise ValueError("PREDICTION_OR_OFFER_CHANGED")
        text = (root / "predictions" / f"{kind}-final.jsonl").read_text(encoding="utf8")
        rows = [json.loads(line) for line in text.splitlines()]
        if [r["source_id"] for r in rows] != plan["datasets"][dataset]["ids"] or any(
            row["financial_authority"] is not False for row in rows
        ):
            raise ValueError("PREDICTION_DENOMINATOR_OR_AUTHORITY_CHANGED")
        predictions[kind] = rows
    return plan, predictions


def contract_metrics(root: Path, source: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    packets = {
        row["source_id"]: ContractPacket.model_validate(
            load_json(root / "inputs/contract" / f"{row['source_id']}.json")
        )
        for row in rows
    }
    hypotheses = [h.hypothesis_id for h in next(iter(packets.values())).hypotheses]
    gold = contract_gold(source / "contract-nli/test.json", list(packets), hypotheses)
    measured = score_contract(
        packets, [ContractOutput.model_validate(r["output"]) for r in rows], gold
    )
    contradictions = {
        key: [g for g in gold if g.document_id == key and g.label == "Contradiction"]
        for key in packets
    }
    alias: Counter[str] = Counter()
    states: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    transport: Counter[str] = Counter()
    evidence: Counter[str] = Counter()
    for row in rows:
        p = packets[row["source_id"]]
        h = [item.model_dump() for item in p.hypotheses]
        view = packet(
            semantic_source(text_source(p.document_id, [p.text])),
            h,
            request=row["job_id"],
            strategy="global",
            k=20,
        )
        if digest(view.payload) != row["selection_configuration"]["synthesis_packet_sha256"]:
            raise ValueError("CONTRACT_PACKET_PROVENANCE_CHANGED")
        aliases = {
            b.alias: view.registry.resolve(b.alias, scope=view.registry.scope)
            for b in view.registry.bindings
        }
        status = row["metadata"]["status"]
        transport[status] += 1
        raw_answers = (row.get("raw") or {}).get("answers")
        for candidate in raw_answers if isinstance(raw_answers, list) else []:
            if not isinstance(candidate, dict):
                continue
            refs = candidate.get("aliases")
            for a in refs if isinstance(refs, list) else []:
                alias["declared"] += 1
                if not isinstance(a, str) or a not in aliases:
                    alias["unknown"] += 1
                elif not isinstance(
                    candidate.get("hypothesis_id"), str
                ) or a not in view.selectable.get(candidate["hypothesis_id"], ()):
                    alias["outside_scope"] += 1
        for item in row["diagnostics"].get("items", []):
            states[item["status"]] += 1
            if item["reason"]:
                reasons[item["reason"]] += 1
            for a, canonical in zip(item["aliases"], item["canonical_ids"], strict=True):
                if aliases[a].span_id != canonical:
                    raise ValueError("CITATION_CANONICAL_ID_CHANGED")
                alias["validated"] += 1
        for g in contradictions[p.document_id]:
            spans = [aliases[a] for a in view.selectable[g.hypothesis_id]]
            total, found, complete = coverage(g.evidence, [(s.start, s.end) for s in spans])
            evidence.update(
                positive_pairs=1,
                gold_characters=total,
                available_characters=found,
                complete_pairs=complete,
            )
    return {
        **measured,
        "alias_counts": dict(alias),
        "item_statuses": dict(states),
        "validation_reasons": dict(reasons),
        "transport_statuses": dict(transport),
        "contradiction_evidence_availability": dict(evidence),
        "performance": performance(root, "contract"),
    }


def validate_offer(raw: dict[str, Any], entry: dict[str, Any]) -> None:
    source = read_source(
        raw["pdf_text_source"] if entry["source_kind"] == "PDF_TEXT" else raw["canonical_source"]
    )
    span = make_span(source, entry["page"], entry["start"], entry["end"], entry["reading_order"])
    from dataclasses import asdict

    canonical = json.loads(json.dumps(asdict(span)))
    if any(entry[key] != value for key, value in canonical.items()):
        raise ValueError("INVOICE_SOURCE_SPAN_INTEGRITY")


def invoice_metrics(
    root: Path, runs: Path, source: Path, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    ids = [row["source_id"] for row in rows]
    gold = {g.document_id: g for g in docile_gold(source / "docile", ids)}
    counts: Counter[str] = Counter()
    transport: Counter[str] = Counter()
    native: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row["source_id"]
        g = gold[key]
        raw = load_json(root / "inputs/invoice" / f"{key}.json")
        annotation = load_json(source / "docile/annotations" / f"{key}.json")
        fields = (
            [f for f in annotation["field_extractions"] if f["fieldtype"] == "document_id"]
            if g.is_invoice
            else []
        )
        expected = {normalized(v) for v in g.references} if g.is_invoice else set()
        output = DocileOutput.model_validate(row["output"])
        offers = load_json(root / "predictions/offers" / f"{row['job_id']}.json")
        offered = {e["alias"]: e for e in offers["entries"]}
        if len(offered) != len(offers["entries"]):
            raise ValueError("DUPLICATE_OFFERED_ALIAS")
        values = {normalized(e["value"]) for e in offered.values()}
        counts.update(
            expected_values=len(expected),
            available_values=len(expected & values),
            gold_occurrences=len(fields),
            incomplete_candidate_pools=not offers["complete"],
        )
        counts["available_occurrences"] += sum(
            any(
                e["bbox"] is not None
                and e["page"] == f["page"] + 1
                and normalized(e["value"]) == normalized(f["text"])
                and overlap_box(e["bbox"], f["bbox"]) >= 0.5
                for e in offered.values()
            )
            for f in fields
        )
        selected = row["diagnostics"].get("selected", [])
        localized, emitted, native_rows = set(), set(), []
        for ref, entry in zip(output.invoice_references, selected, strict=True):
            candidate = offered[entry["alias"]]
            if any(entry[k] != v for k, v in candidate.items()):
                raise ValueError("SELECTED_CANDIDATE_NOT_IN_SEALED_OFFER")
            validate_offer(raw, candidate)
            if (ref.value, ref.quote.text, ref.quote.start, ref.quote.end, ref.page) != (
                entry["value"],
                entry["text"],
                entry["start"],
                entry["end"],
                entry["page"] - 1,
            ):
                raise ValueError("INVOICE_REFERENCE_PROVENANCE_CHANGED")
            value = normalized(entry["value"])
            emitted.add(value)
            counts["selected_occurrences"] += 1
            if entry["bbox"] is not None:
                counts["localized_occurrences"] += 1
                localized.add(value)
                item = {
                    "fieldtype": "document_id",
                    "text": value,
                    "page": entry["page"] - 1,
                    "bbox": entry["bbox"],
                    "score": 0.0,
                }
                if item not in native_rows:
                    native_rows.append(item)
        if g.is_invoice and (source / "docile/ocr" / f"{key}.json").is_file():
            native[key] = native_rows
        status = row["metadata"]["status"]
        transport[status] += 1
        correct = emitted & expected
        localized_correct = localized & expected
        counts.update(
            tp=len(correct),
            fp=len(emitted - correct),
            fn=len(expected - correct),
            localized_tp=len(localized_correct),
            localized_fp=len(emitted - localized_correct),
            localized_fn=len(expected - localized_correct),
            emitted_values=len(emitted),
            exact_set_match=status in {"SUCCESS", "OUT_OF_SCOPE", "NO_CANDIDATES"}
            and emitted == expected,
            localized_exact_set_match=status in {"SUCCESS", "OUT_OF_SCOPE", "NO_CANDIDATES"}
            and emitted == expected
            and localized == emitted,
            covered_documents=bool(emitted),
            abstained_documents=not emitted,
            source_input_failures=status == "ADAPTER_INPUT_FAILURE",
            non_invoice_documents=not g.is_invoice,
            non_invoice_false_emissions=len(emitted) if not g.is_invoice else 0,
            partial_ocr_documents=bool(raw["canonical_source"]["fallbacks"]),
            pdf_text_available=bool(raw.get("pdf_text_source")),
            pdf_candidates_offered=sum(e["source_kind"] == "PDF_TEXT" for e in offered.values()),
            pdf_candidates_selected=sum(e["source_kind"] == "PDF_TEXT" for e in selected),
            rejected_aliases=row["diagnostics"].get("invalid_aliases", 0),
        )
    result = {
        "documents": len(ids),
        "counts": dict(counts),
        "transport_statuses": dict(transport),
        "invoice_id": prf(counts["tp"], counts["fp"], counts["fn"]),
        "localized_invoice_id": prf(
            counts["localized_tp"], counts["localized_fp"], counts["localized_fn"]
        ),
        "exact_set_match": ratio(counts["exact_set_match"], len(ids)),
        "localized_exact_set_match": ratio(counts["localized_exact_set_match"], len(ids)),
        "coverage": ratio(counts["covered_documents"], len(ids)),
        "localization_validity": ratio(
            counts["localized_occurrences"], counts["selected_occurrences"]
        ),
        "source_quote_validity": ratio(
            counts["selected_occurrences"], counts["selected_occurrences"]
        ),
        "performance": performance(root, "invoice"),
    }
    result.update(native_evaluation(root, runs, source, native))
    return result


def native_evaluation(
    root: Path, runs: Path, source: Path, native: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    native_path = root / "scoring/docile-conditional.kile.json"
    write_json(native_path, native)
    if not any(native.values()):
        return {"official_status": "NOT COMPUTABLE: ALL EMPTY", "native_documents": len(native)}
    environment = runs / "phase1-v1/venv/Scripts"
    version = subprocess.check_output(
        [
            str(environment / "python.exe"),
            "-c",
            'from importlib.metadata import version; print(version("docile-benchmark"))',
        ],
        text=True,
    ).strip()
    if version != "0.3.5":
        raise ValueError("OFFICIAL_DOCILE_VERSION_CHANGED")
    view = root / "scoring/docile-native-view"
    native_scope = docile_scorer_view(
        source / "docile", list(native), view, "clearledger_phase3b_val"
    )
    command = [
        str(environment / "docile_evaluate.exe"),
        "--task",
        "KILE",
        "--dataset-path",
        str(view),
        "--split",
        "clearledger_phase3b_val",
        "--predictions",
        str(native_path),
        "--evaluate-x-shot-subsets",
        "",
        "--evaluate-fieldtypes",
        "--evaluate-also-text",
        "--store-evaluation-result",
        str(root / "scoring/docile-official.json"),
    ]
    completed = subprocess.run(command, capture_output=True, timeout=180, check=False)
    (root / "scoring/docile-official.log").write_bytes(completed.stdout + completed.stderr)
    return {
        "official_status": "COMPUTED" if completed.returncode == 0 else "NOT COMPUTABLE",
        "native_scope": native_scope,
        "version": version,
    }


def score(runs: Path, source: Path) -> None:
    root = runs / "phase3b-v1"
    plan, rows = sealed_predictions(root)  # Both seals must verify before any gold access.
    manifest = verified(root / "source-manifest.json")
    paths = {
        **manifest["source_files"],
        "contract-nli/test.json": plan["datasets"]["contract-nli"]["source_split_sha256"],
        "docile/val.json": plan["datasets"]["docile"]["source_split_sha256"],
    }
    if any(sha256(source / path) != h for path, h in paths.items()):
        raise ValueError("FROZEN_SOURCE_CHANGED")
    annotation_hashes = {
        f"docile/annotations/{i}.json": sha256(source / "docile/annotations" / f"{i}.json")
        for i in plan["datasets"]["docile"]["ids"]
    }
    write_sealed(
        root / "scoring/gold-source-hashes.json",
        {**annotation_hashes, "contract-nli/test.json": paths["contract-nli/test.json"]},
    )
    contract = contract_metrics(root, source, rows["contract"])
    invoice = invoice_metrics(root, runs, source, rows["invoice"])
    write_sealed(
        root / "scoring/aggregate.json",
        {
            "contract-nli": contract,
            "docile": invoice,
            "financial_mutations": 0,
            "financial_authority": False,
        },
    )
    sealed_predictions(root)
    print("Phase 3B scoring finished from sealed predictions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    score(args.runs.resolve(), args.source.resolve())
