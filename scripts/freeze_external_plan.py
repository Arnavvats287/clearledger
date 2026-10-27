"""Freeze metadata-only evaluation selections, without inference or application access."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from external_inventory import SELECTION_VERSION, digest


def workload(requests: int, input_limit: int, output_limit: int) -> dict:
    return {
        "maximum_generation_attempts": requests,
        "input_token_reservation": requests * input_limit,
        "output_token_reservation": requests * output_limit,
        "per_request_input_limit": input_limit,
        "per_request_output_limit": output_limit,
        "retries": 0,
        "calls_authorized_now": 0,
    }


def build_plan(data: dict, structure: dict, inventory_hash: str) -> dict:
    datasets = data["datasets"]
    doc = datasets["docile"]["inspection"]
    nli = datasets["contract-nli"]["inspection"]["splits"]
    rec = datasets["recbench-small"]["inspection"]
    doc_ids = doc["selected_ids"]
    nli_ids = {
        "adapter": nli["dev"]["selected_document_ids"],
        "scored": nli["test"]["selected_document_ids"],
    }
    rec_ids = rec["csv"]["bank_statements"]["selected_ids"]
    for selection, sizes in ((doc_ids, (8, 50)), (nli_ids, (3, 12)), (rec_ids, (16, 128))):
        if any(len(selection[k]) != n for k, n in zip(("adapter", "scored"), sizes, strict=True)):
            raise ValueError("UNEXPECTED_SAMPLE_SIZE")
        if set(selection["adapter"]) & set(selection["scored"]):
            raise ValueError("SAMPLE_OVERLAP")
        if any(len(ids) != len(set(ids)) for ids in selection.values()):
            raise ValueError("DUPLICATE_SAMPLE_ID")
    return {
        "protocol": "clearledger-external-evaluation-v1",
        "frozen_utc": datetime.now(UTC).isoformat(),
        "inventory_sha256": inventory_hash,
        "selection_version": SELECTION_VERSION,
        "inference_performed": False,
        "external_calls_authorized": False,
        "selection_rule": "SHA256(version|domain|source ID), ascending hex then ID; no labels",
        "common": {
            "leakage": "Separate source-only projection process and scorer; no raw dataset mount "
            "in application/provider worker; deny annotations, truth_*, labels_*, "
            "metadata and gold",
            "normalization": "Unicode NFC, strip leading/trailing whitespace only; case and "
            "internal punctuation/whitespace preserved; deduplicate exact predictions per document",
            "failures": "No retries or replacement samples. Every selected unit retained. Record "
            "parse/privacy/budget/provider/schema/citation failures separately and as non-answers",
            "latency": "perf_counter_ns wall time for projection, parse, provider, validation, "
            "persistence, total; report count, median, nearest-rank p95 and max including failures",
            "financial_safety": "No posting/approval/settlement; verify snapshots unchanged if "
            "application APIs are used. Standalone probes have no financial database access",
            "quota": "No current quota/model/pricing verified. Prior screenshot 15 RPM / "
            "250000 input TPM / 500 RPD is historical only. Future approval and recheck required; "
            "one caller, <=2 total provider HTTP operations/minute; reserve all operations/tokens",
            "scorer_command": None,
            "scorer_status": "NOT_IMPLEMENTED: native evaluator absent locally; pin and validate "
            "official tooling before native scores, or label independent secondary scorer",
        },
        "datasets": {
            "docile": {
                "task": "Conditional invoice-reference extraction, not general invoice parsing",
                "status": "BLOCKED_PRIVACY_REVIEW_AND_SOURCE_ONLY_OCR_ADAPTER",
                "input": [
                    "original PDF",
                    "source OCR words and geometry if source-only adapter validated",
                ],
                "hidden": [
                    "annotations/**",
                    "metadata",
                    "field_extractions",
                    "line_item_extractions",
                ],
                "adapter_split": "train",
                "scored_split": "val",
                "ids": doc_ids,
                "count": {"adapter_documents": 8, "scored_documents": 50},
                "mapping": "document_id -> invoice_references[].value ONLY for tax_invoice; "
                "document type is scorer-only, never an input or sample-selection filter",
                "metrics": [
                    "invoice-ID micro precision/recall/F1",
                    "exact ID set match",
                    "coverage",
                    "false invoice-reference emissions on non-invoice documents",
                    "source quote validity",
                    "unsupported-field rate",
                    "provider failures",
                ],
                "native_metrics": "KILE AP/localization after official evaluator and source-only "
                "box alignment verified; partial taxonomy only, never a full DocILE score",
                "unsupported": ["amount exact match", "dates", "parties", "line items", "LIR"],
                "abstention": "Empty list is abstention; count missed gold IDs on invoices, "
                "report non-invoice subset separately; never drop failed parser/privacy cases",
                "location_rule": "Only unique exact quote alignment to input OCR words; union word "
                "boxes, preserve native page coordinates. No gold-assisted alignment; unavailable "
                "alignment is failed/unavailable localization, not silently excluded",
                "workload": workload(58, 8192, 1024),
                "optional_full": {"split": "val", "documents": 500, "max_generations": 500},
                "output": "external-runs/docile-v1/{adapter,scored}/{predictions,telemetry}.jsonl",
            },
            "contract-nli": {
                "task": "Evaluation-only legal NLI, NOT AR-domain investigation accuracy",
                "status": "BLOCKED_NLI_ADAPTER_AND_REAL_DOCUMENT_PRIVACY_REVIEW",
                "input": ["documents[].text", "hypothesis ID and labels[ID].hypothesis text only"],
                "hidden": [
                    "annotation_sets",
                    "choice",
                    "all dataset spans",
                    "gold evidence indices",
                    "file_name",
                    "url",
                    "document_type",
                    "raw split JSON",
                ],
                "adapter_split": "dev",
                "scored_split": "test",
                "ids": nli_ids,
                "hypothesis_ids": nli["test"]["selected_hypothesis_ids"],
                "count": {
                    "adapter_documents": 3,
                    "adapter_pairs": 51,
                    "scored_documents": 12,
                    "scored_pairs": 204,
                },
                "labels": ["Entailment", "Contradiction", "NotMentioned"],
                "mapping": "Source support/conflict/insufficiency conceptual only; existing AR "
                "Investigator cannot accept arbitrary legal hypotheses. Separate read-only NLI DTO "
                "and document port required; never fabricate claims, authentication or tools",
                "execution": "All 17 hypotheses per document; one bounded plan and one synthesis "
                "generation. No native spans supplied; source-only segmentation or exact quotes",
                "metrics": [
                    "accuracy",
                    "macro F1",
                    "per-class precision/recall/F1",
                    "character-set evidence precision/recall/F1 for gold E/C pairs",
                    "unsupported-conclusion rate",
                    "source quote validity",
                    "abstention rate",
                    "provider/fallback rate",
                ],
                "evidence_rule": "Scorer unions gold candidate character ranges and predicted "
                "verified quote ranges; overlap length determines P/R. Micro over gold E/C pairs; "
                "report joint correct-label evidence F1 too. NotMentioned has no evidence score",
                "abstention": "NotMentioned is a substantive label, not provider failure. Explicit "
                "abstention/failure counts incorrect on full 204-pair denominator; answered-only "
                "accuracy separately. E/C on opposite gold or gold NotMentioned is unsupported",
                "workload": workload(30, 32768, 4096),
                "selected_text_characters": nli["dev"]["selected_text_characters"]
                + nli["test"]["selected_text_characters"],
                "optional_full": {
                    "split": "test",
                    "documents": 123,
                    "pairs": 2091,
                    "max_generations": 246,
                },
                "output": "external-runs/contractnli-v1/{adapter,scored}/"
                "{predictions,telemetry}.jsonl",
            },
            "recbench-small": {
                "task": "Native processor/ledger/payout/bank graph reconciliation suitability",
                "status": "BLOCKED_CURRENCY_DOMAIN_AND_UNDOCUMENTED_GROUP_TRUTH",
                "input": [
                    "csv/ledger.csv",
                    "csv/settlement_lines.csv",
                    "csv/payouts.csv",
                    "csv/bank_statements.csv",
                ],
                "hidden": ["truth_*", "labels_*", "manifest generator metadata"],
                "adapter_split": "local source-ID partition, no official split",
                "scored_split": "disjoint local source-ID partition of same generated scenario",
                "ids": rec_ids,
                "count": {"adapter_bank_rows": 16, "scored_bank_rows": 128},
                "candidate_rule": "All four source tables in static snapshot; filter by observable "
                "currency/entity only, never truth. Gold scored for selected bank rows only; other "
                "graph levels separate optional full-table tasks, not selected via gold closure",
                "metrics": [
                    "bank-edge precision/recall/F1",
                    "false and missed edges",
                    "integer native-minor-unit amount consistency",
                    "abstention",
                    "duplicate/replay",
                    "unsafe mutation count if application applicable",
                ],
                "normalization": "Exact case-sensitive natural-key edges, currency preserved; "
                "no USD-to-INR conversion, no tolerances, no changing signs or inventing FX rules",
                "abstention": "Empty edge set yields FN for eligible gold edges; no fabricated "
                "pairings. No score until group identities/candidate universe are documented",
                "structure": structure,
                "mapping": "No legitimate current ClearLedger financial import mapping: no INR, "
                "processor charges/payouts are not AR invoices, no verified payer intent. Native "
                "graph probe would be a different task, not actual application matching accuracy",
                "workload": workload(0, 0, 0),
                "optional_full": {"bank_rows": 75138, "max_generations": 0},
                "output": "external-runs/recbench-v1/{adapter,scored}/{edges,telemetry}.jsonl",
            },
        },
        "run_order": [
            "contract-nli adapter offline",
            "docile adapter offline",
            "recbench semantics clarification",
            "separately authorized inference",
        ],
        "freeze_policy": "No replacement/reselection after inference. Record model/prompt/adapter/"
        "scorer hashes before final scoring. Changes require version 2 and explicit approval; "
        "do not tune on scored subsets. Full runs must use the same frozen configuration",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--structure", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Check frozen hash and selections")
    args = parser.parse_args()
    plan = build_plan(
        json.loads(args.inventory.read_text(encoding="utf8")),
        json.loads(args.structure.read_text(encoding="utf8")),
        digest(args.inventory),
    )
    plan["builder_sha256"] = digest(Path(__file__))
    plan["structure_sha256"] = digest(args.structure)
    if args.check:
        existing = json.loads(args.output.read_text(encoding="utf8"))
        if digest(args.output) != args.output.with_suffix(".sha256").read_text().strip():
            raise ValueError("PLAN_DIGEST_MISMATCH")
        existing.pop("frozen_utc")
        plan.pop("frozen_utc")
        if existing != plan:
            raise ValueError("PLAN_INPUT_OR_SELECTION_MISMATCH")
        print("Frozen plan hash, provenance and selections verified; no inference.")
        return
    # Exclusive creation: a frozen plan is never silently replaced.
    with args.output.open("x", encoding="utf8") as stream:
        stream.write(json.dumps(plan, indent=2) + "\n")
    with args.output.with_suffix(".sha256").open("x", encoding="ascii") as stream:
        stream.write(digest(args.output) + "\n")
    print("Frozen plan written; no inference performed or authorized.")


if __name__ == "__main__":
    main()
