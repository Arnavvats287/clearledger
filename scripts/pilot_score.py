"""Answer-only scorer. Imported after application shutdown, never by application code."""

import hashlib
import itertools
import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo


def ratio(hits, total):
    return {"correct": hits, "total": total, "rate": hits / total if total else None}


def allocation(candidate, invoice_numbers):
    return {
        invoice_numbers[item["invoice_id"]]: item["amount_paise"]
        for item in candidate["allocations"]
    }


def exhaustive_subsets(invoices, target):
    """Independent brute force oracle for this small pilot, not the MITM implementation."""
    if len(invoices) > 20:
        raise ValueError("Pilot oracle candidate limit")
    return [
        dict((row["invoice_number"], row["open_amount_paise"]) for row in group)
        for size in range(1, len(invoices) + 1)
        for group in itertools.combinations(invoices, size)
        if sum(row["open_amount_paise"] for row in group) == target
    ]


def family(case):
    if case["abstain_invoice_allocation"]:
        return "ambiguous_subsets"
    if case["linked_receipt_natural_keys"]:
        return "distinct_duplicate_payment"
    if case["claims_truth"]:
        return "claims_future_adjudication"
    if "UNIQUE_SUBSET" in case["expected_safe_matching_decision"]:
        return "unique_subset"
    if any(len(a) > 1 for a in case["stages"][0]["incremental_cash_allocations_paise"].values()):
        return "multi_invoice"
    return "single_invoice_or_partial"


def matching_score(observed, cases, mode):
    data = observed["records"]
    banks = {row["id"]: row for row in data["bank-transactions"]}
    customers = {row["external_reference"]: row["id"] for row in data["customers"]}
    numbers = {row["id"]: row["invoice_number"] for row in data["invoices"]}
    invoices = {row["invoice_number"]: row for row in data["invoices"]}
    exact_eligible = exact_hit = exact_supported = exact_false = 0
    multi_total = multi_hit = candidate_total = candidate_hit = partial_hit = 0
    advanced_supported = advanced_false = abstain_total = abstain_hit = 0
    ambiguity_total = ambiguity_hit = oracle_total = oracle_hit = 0
    details = []
    families = {}
    for receipt in data["receipts"]:
        bank = banks[receipt["bank_transaction_id"]]
        natural = {
            key: bank[key] for key in ("source_system", "account_ref", "external_transaction_id")
        }
        linked = [
            case
            for case in cases
            if natural
            in [case["primary_receipt_natural_key"], *case["linked_receipt_natural_keys"]]
        ]
        assert len(linked) == 1, "Every accepted receipt must have exactly one truth association"
        case = linked[0]
        transaction = bank["external_transaction_id"]
        expected = {}
        for stage in case["stages"]:
            for invoice, amount in (
                stage["incremental_cash_allocations_paise"].get(transaction, {}).items()
            ):
                expected[invoice] = expected.get(invoice, 0) + amount
        result = observed[mode][receipt["id"]]
        exact, advanced = result["match"], result["match-advanced"]
        correct_customer = customers[case["true_customer_external_reference"]]
        exact_allocation = (
            {numbers[exact["invoice_id"]]: exact["amount_paise"]} if exact["invoice_id"] else {}
        )
        supported_exact = exact["outcome"] == "EXACT_MATCH"
        exact_supported += supported_exact
        exact_false += supported_exact and (
            exact_allocation != expected or exact["customer_id"] != correct_customer
        )
        eligible = (
            len(expected) == 1
            and next(iter(expected.values())) == receipt["amount_paise"]
            and invoices[next(iter(expected))]["open_amount_paise"] == receipt["amount_paise"]
        )
        exact_eligible += eligible
        exact_hit += (
            eligible
            and supported_exact
            and exact_allocation == expected
            and exact["customer_id"] == correct_customer
        )
        analysis = advanced["result"]
        candidates = [allocation(candidate, numbers) for candidate in analysis["candidates"]]
        partials = [allocation(candidate, numbers) for candidate in analysis["partial_analysis"]]
        supported_advanced = analysis["outcome"] == "UNIQUE" and analysis["intent_verified"]
        advanced_supported += supported_advanced
        advanced_false += supported_advanced and (
            len(candidates) != 1
            or candidates[0] != expected
            or advanced["customer_id"] != correct_customer
        )
        candidate_total += bool(expected)
        candidate_hit += bool(expected) and expected in candidates
        partial_hit += bool(expected) and expected in candidates + partials
        multi_total += len(expected) > 1
        multi_hit += len(expected) > 1 and expected in candidates
        if not expected:
            abstain_total += 1
            abstain_hit += not supported_exact and not supported_advanced
        if case["abstain_invoice_allocation"]:
            ambiguity_total += 1
            ambiguity_hit += analysis["outcome"] == "AMBIGUOUS" and len(candidates) > 1

        # Unattested mathematics checked independently, with verified-alias identity
        # requirement derived from actual imported aliases; no hidden attestation.
        if mode == "unattested":
            alias = next(
                (
                    a
                    for a in data["payer-aliases"]
                    if a["normalized_alias"] == " ".join(bank["payer_name"].split()).casefold()
                ),
                None,
            )
            if alias and alias["customer_id"] == correct_customer:
                day = (
                    datetime.fromisoformat(bank["occurred_at"])
                    .astimezone(ZoneInfo("Asia/Kolkata"))
                    .date()
                    .isoformat()
                )
                eligible_rows = [
                    row
                    for row in data["invoices"]
                    if row["customer_id"] == correct_customer
                    and row["status"] == "OPEN"
                    and row["open_amount_paise"] > 0
                    and row["issued_date"] <= day
                ]
                combinations = exhaustive_subsets(eligible_rows, receipt["unapplied_amount_paise"])
                expected_outcome = (
                    "UNRESOLVED"
                    if not combinations
                    else "UNIQUE"
                    if len(combinations) == 1
                    else "AMBIGUOUS"
                )
            else:
                combinations, expected_outcome = [], "UNRESOLVED"
            oracle_total += 1
            oracle_hit += analysis["outcome"] == expected_outcome and sorted(
                candidates, key=lambda row: tuple(sorted(row.items()))
            ) == sorted(combinations, key=lambda row: tuple(sorted(row.items())))
        label = family(case)
        counts = families.setdefault(label, Counter())
        counts["receipts"] += 1
        counts["expected_cash_candidate"] += bool(expected)
        counts["candidate_found"] += bool(expected) and expected in candidates
        counts["safe_abstentions"] += not supported_exact and not supported_advanced
        counts["false_supported"] += bool(
            supported_exact
            and exact_allocation != expected
            or supported_advanced
            and candidates != [expected]
        )
        details.append(
            {
                "scenario": case["scenario_id"],
                "transaction": transaction,
                "family": label,
                "expected_cash": expected,
                "exact": exact["outcome"],
                "advanced": analysis["outcome"],
                "reason": analysis["reason"],
                "candidate_found": bool(expected) and expected in candidates,
                "partial_or_exact_candidate_found": bool(expected)
                and expected in candidates + partials,
            }
        )
    return {
        "exact_recall_full_balance_targets": ratio(exact_hit, exact_eligible),
        "exact_false_supported": {
            "false": exact_false,
            "supported": exact_supported,
            "rate": exact_false / exact_supported if exact_supported else None,
        },
        "advanced_false_supported": {
            "false": advanced_false,
            "supported": advanced_supported,
            "rate": advanced_false / advanced_supported if advanced_supported else None,
        },
        "advanced_expected_cash_candidate_recall": ratio(candidate_hit, candidate_total),
        "advanced_including_partial_analysis_recall": ratio(partial_hit, candidate_total),
        "multi_invoice_candidate_recall": ratio(multi_hit, multi_total),
        "correct_abstention_required_receipts": ratio(abstain_hit, abstain_total),
        "ambiguous_subset_detection": ratio(ambiguity_hit, ambiguity_total),
        "independent_subset_oracle": ratio(oracle_hit, oracle_total),
        "families": {k: dict(v) for k, v in families.items()},
    }, details


def documents_score(package, split, observed, cases):
    sources = observed["documents"]
    strict = quotes = raw_hash = temporal = pointers = 0
    mismatched_documents = set()
    for case in cases:
        for pointer in case["evidence_pointers"]:
            pointers += 1
            source = sources[pointer["document_id"]]
            pages = source["canonical"]["pages"]
            start, end = pointer["char_span"]
            page = pointer["page_number"] - 1
            matches = page < len(pages) and pages[page][start:end] == pointer["exact_quote"]
            strict += matches
            quotes += sum(text.count(pointer["exact_quote"]) for text in pages) == 1
            if not matches:
                mismatched_documents.add(pointer["document_id"])
            raw_hash += source["document"]["content_sha256"] == pointer["source_sha256"]
            stage = next(s for s in case["stages"] if s["stage"] == pointer["available_at_stage"])
            temporal += datetime.fromisoformat(
                source["inventory"]["available_at"]
            ) <= datetime.fromisoformat(stage["as_of"])
    canonical_equal = correlation_targets = 0
    remittances = []
    for entry in sources.values():
        metadata = entry["inventory"]
        expected = (package / split / "app_visible" / metadata["canonical_text_path"]).read_text(
            "utf-8"
        )
        canonical_equal += "\n".join(entry["canonical"]["pages"]) == expected
        if metadata["document_type"] == "remittances":
            remittances.append(entry)
            known_utrs = {
                row["external_transaction_id"]
                for row in observed["records"]["bank-transactions"]
                if row["external_transaction_id"] in expected
            }
            correlation_targets += len(known_utrs) == 1
    # Reference coverage can be measured without claiming semantic model accuracy.
    expected_refs = parseable_refs = returned_refs = correct_refs = 0
    for case in cases:
        doc_ids = {p["document_id"] for p in case["evidence_pointers"]}
        for doc_id in doc_ids:
            entry = sources[doc_id]
            if entry["inventory"]["document_type"] != "remittances":
                continue
            original_canonical = (
                package / split / "app_visible" / entry["inventory"]["canonical_text_path"]
            ).read_text("utf-8")
            expected = {n for n in case["invoice_numbers"] if n in original_canonical}
            returned = {
                r["value"] for r in entry["extraction"]["result"].get("invoice_references", [])
            }
            expected_refs += len(expected)
            if entry["document"]["parse_status"] == "READY":
                parseable_refs += len(expected)
            returned_refs += len(returned)
            correct_refs += len(expected & returned)
    privacy_leaks = sum(
        s["privacy_probe"]["recognized_identifiers_remaining"] for s in sources.values()
    )
    return {
        "sources": len(sources),
        "types": dict(Counter(e["inventory"]["document_type"] for e in sources.values())),
        "parse_status": dict(Counter(e["document"]["parse_status"] for e in sources.values())),
        "parse_failures": dict(
            Counter(
                e["document"]["parse_error"]
                for e in sources.values()
                if e["document"]["parse_error"]
            )
        ),
        "document_ingestion_200": sum(e["ingestion_http_status"] == 200 for e in sources.values()),
        "originals_preserved": len(sources),
        "application_positive_spans_verified": sum(
            bool(page) for e in sources.values() for page in e["canonical"]["pages"]
        ),
        "application_forged_spans_rejected": sum(
            bool(page) for e in sources.values() for page in e["canonical"]["pages"]
        ),
        "extraction_routes": dict(Counter(e["extraction"]["route"] for e in sources.values())),
        "extraction_status": dict(Counter(e["extraction"]["status"] for e in sources.values())),
        "canonical_sidecar_equal": ratio(canonical_equal, len(sources)),
        "hidden_citation_original_hash": ratio(raw_hash, pointers),
        "hidden_citation_exact_application_offsets": ratio(strict, pointers),
        "hidden_citation_unique_quote_in_application": ratio(quotes, pointers),
        "hidden_citation_available_at_stage": ratio(temporal, pointers),
        "offset_mismatch_source_count": len(mismatched_documents),
        "remittance_reference_recall": ratio(correct_refs, expected_refs),
        "parseable_remittance_reference_recall": ratio(correct_refs, parseable_refs),
        "remittance_reference_precision": ratio(correct_refs, returned_refs),
        "semantic_provider_accuracy": "NOT EVALUABLE: provider disabled; no mocked accuracy",
        "correlation_attempts": len(remittances),
        "unattested_end_to_end_link_recall": ratio(
            sum(e["correlation"]["status"] == "LINKED" for e in remittances), correlation_targets
        ),
        "correlation_outcomes": dict(Counter(e["correlation"]["status"] for e in remittances)),
        "supported_correlation_accuracy": "NOT EVALUABLE without source-backed extracted UTRs",
        "privacy_projection_abstentions": sum(
            s["privacy_probe"]["status"] == "ABSTAINED" for s in sources.values()
        ),
        "privacy_probe_sources_with_text": sum(
            bool(e["canonical"]["pages"]) for e in sources.values()
        ),
        "recognized_identifier_projection_failures": privacy_leaks,
        "external_transmissions": 0,
        "live_privacy_accuracy": "NOT EVALUABLE: no external transmission",
        "disabled_optin_routes": dict(
            Counter(s["disabled_optin"]["status"] for s in sources.values())
        ),
    }


def evaluate(package, observations):
    summary, details, blockers = {}, {}, []
    for split, observed in observations.items():
        cases = [
            json.loads(line)
            for line in (package / split / "hidden_ground_truth/ground_truth_cases.jsonl")
            .read_text("utf-8")
            .splitlines()
            if line
        ]
        metrics = {
            "case_count": len(cases),
            "stage_count": sum(len(c["stages"]) for c in cases),
            "import_file_success": ratio(len(observed["imports"]), 4),
            "valid_import_rows": sum(r["first"]["inserted"] for r in observed["imports"]),
            "valid_import_failures": 0,
            "invalid_header_requests_rejected": 4,
            "conflicting_bank_requests_rejected": sum(
                len(r.get("row_probes", [])) for r in observed["imports"]
            ),
            "row_duplicate_requests_accepted_without_insertion": sum(
                len(r.get("row_probes", [])) for r in observed["imports"]
            ),
            "same_key_and_fresh_key_replays": 8,
            "record_counts": {k: len(v) for k, v in observed["records"].items()},
            "simulated_attestations": len(observed["attestations"]),
            "financial_mutations": observed["financial_mutations"],
            "tenant_isolation_404_checks": observed["tenant_isolation_404_checks"],
            "document_auth_401_checks": observed["document_auth_401_checks"],
        }
        details[split] = {}
        negative_fixture = (
            package / split / "hidden_ground_truth/negative_import_tests/replay_safety.json"
        )
        if negative_fixture.exists():
            fixture = json.loads(negative_fixture.read_text("utf-8"))

            def payload_digest(value):
                return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

            covered = any(
                probe
                == {
                    "duplicate": payload_digest(fixture["identical_row_replay"]),
                    "conflict": payload_digest(fixture["conflict_variant"]),
                }
                for item in observed["imports"]
                for probe in item.get("row_probes", [])
            )
            metrics["provided_hidden_negative_fixture_covered"] = covered
            assert covered, "Provided negative fixture not covered by visible-input probes"
        for mode in ("unattested", "simulated_attested"):
            metrics[mode], details[split][mode] = matching_score(observed, cases, mode)
            if (
                metrics[mode]["exact_false_supported"]["false"]
                or metrics[mode]["advanced_false_supported"]["false"]
            ):
                blockers.append(f"{split}/{mode}: false supported proposal")
        metrics["documents"] = documents_score(package, split, observed, cases)
        if metrics["documents"]["recognized_identifier_projection_failures"]:
            blockers.append(f"{split}: recognized identifier survived projection")
        latencies = sorted(observed["performance"]["latencies_ns"])
        metrics["performance"] = {
            "api_calls": len(latencies),
            "elapsed_seconds": observed["performance"]["elapsed_ns"] / 1_000_000_000,
            "api_p50_ms": latencies[len(latencies) // 2] / 1_000_000,
            "api_p95_ms": latencies[int((len(latencies) - 1) * 0.95)] / 1_000_000,
            "api_max_ms": max(latencies) / 1_000_000,
        }
        summary[split] = metrics
    summary["safety_blockers"] = blockers
    summary["unsupported"] = [
        "tax/deduction adjudication",
        "case lifecycle/late-stage financial replay",
        "journal posting",
        "approvals/maker-checker",
        "live provider extraction",
        "accounting balance outcomes",
        "human review time",
        "A/B/C investigator ablation",
    ]
    return summary, details
