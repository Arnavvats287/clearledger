"""Evaluator-only successor measurements, loaded after application shutdown."""

import json
from collections import Counter


def email_body_location(actual, body):
    """Measure, never guess, the body position in actual application output."""
    if not body or actual.count(body) != 1:
        return None
    offset = actual.index(body)
    return {
        "body_char_start": offset,
        "body_byte_start": len(actual[:offset].encode("utf-8")),
        "prefix_chars": offset,
        "body_exact": actual[offset:] == body,
    }


def evaluate_compat(package, observations):
    summary = {"safety_blockers": []}
    details = {}
    for split, observed in observations.items():
        sources = observed["documents"]
        legacy_cases = [
            json.loads(line)
            for line in (package / split / "hidden_ground_truth/ground_truth_cases.jsonl")
            .read_text("utf-8")
            .splitlines()
            if line
        ]
        citation_groups = {}
        for case in legacy_cases:
            for pointer in case["evidence_pointers"]:
                entry = sources[pointer["document_id"]]
                suffix = entry["inventory"]["source_path"].rsplit(".", 1)[1]
                counts = citation_groups.setdefault(
                    suffix, {"total": 0, "direct": 0, "measured_delta_chars": Counter()}
                )
                counts["total"] += 1
                page = pointer["page_number"] - 1
                pages = entry["canonical"]["pages"]
                start, end = pointer["char_span"]
                if page < len(pages):
                    text = pages[page]
                    counts["direct"] += text[start:end] == pointer["exact_quote"]
                    if text.count(pointer["exact_quote"]) == 1:
                        counts["measured_delta_chars"][
                            text.index(pointer["exact_quote"]) - start
                        ] += 1
        pdfs = [
            entry
            for entry in sources.values()
            if entry["inventory"]["source_path"].endswith(".pdf")
        ]
        pdf_canonical = 0
        emails = []
        for identifier, entry in sources.items():
            expected = (
                package / split / "app_visible" / entry["inventory"]["canonical_text_path"]
            ).read_text("utf-8")
            actual = "\n".join(entry["canonical"]["pages"])
            if entry["inventory"]["source_path"].endswith(".pdf"):
                pdf_canonical += actual == expected
            if entry["inventory"]["source_path"].endswith(".eml"):
                emails.append(
                    {
                        "document": identifier,
                        "canonical_exact": actual == expected,
                        "actual_body_location": email_body_location(actual, expected),
                    }
                )
        truth = json.loads(
            (
                package / split / "hidden_ground_truth/compatibility_correlation_targets.json"
            ).read_text("utf-8")
        )
        supplemental = observed["compatibility_structured_remittances"]
        assert {t["synthetic_addition_file"] for t in truth["targets"]} == set(supplemental)
        banks = {row["id"]: row for row in observed["records"]["bank-transactions"]}
        positives = positive_hits = negatives = negative_hits = false_links = invoice_hits = 0
        records = []
        for target in truth["targets"]:
            entry = supplemental[target["synthetic_addition_file"]]
            attested = entry["simulated_utr_attested"]
            expected = None
            if "target_receipt" in target:
                positives += 1
                candidates = [
                    row["id"]
                    for row in observed["records"]["receipts"]
                    if all(
                        banks[row["bank_transaction_id"]][key] == value
                        for key, value in target["target_receipt"].items()
                    )
                ]
                assert len(candidates) == 1
                expected = candidates[0]
                positive_hits += (
                    attested["status"] == "LINKED" and attested["receipt_id"] == expected
                )
            else:
                negatives += 1
                negative_hits += (
                    attested["status"] == "UNRESOLVED" and attested["receipt_id"] is None
                )
            false_links += attested["status"] == "LINKED" and (
                expected is None or attested["receipt_id"] != expected
            )
            invoice_hits += [
                r["value"] for r in entry["extraction"]["result"]["invoice_references"]
            ] == target.get("invoice_references_stated_by_synthetic_sender", [])
            records.append(
                {
                    "source": target["synthetic_addition_file"],
                    "desired_receipt": expected,
                    "actual_status": attested["status"],
                    "reason": attested["result"]["reason"],
                }
            )
        summary[split] = {
            "pdf_count": len(pdfs),
            "pdf_ready": sum(p["document"]["parse_status"] == "READY" for p in pdfs),
            "pdf_canonical_equal": pdf_canonical,
            "email_count": len(emails),
            "email_direct_canonical_equal": sum(e["canonical_exact"] for e in emails),
            "email_unique_body_exact": sum(
                bool(e["actual_body_location"] and e["actual_body_location"]["body_exact"])
                for e in emails
            ),
            "measured_email_prefix_char_counts": dict(
                Counter(
                    e["actual_body_location"]["prefix_chars"]
                    for e in emails
                    if e["actual_body_location"]
                )
            ),
            "supplemental_documents": len(supplemental),
            "deterministic_successes": sum(
                e["extraction"]["route"] == "DETERMINISTIC"
                and e["extraction"]["status"] == "SUCCEEDED"
                for e in supplemental.values()
            ),
            "source_spans_api_verified": sum(e["verified_spans"] for e in supplemental.values()),
            "invoice_reference_truth_agreement": invoice_hits,
            "unattested_outcomes": dict(
                Counter(e["unattested"]["status"] for e in supplemental.values())
            ),
            "attested_outcomes": dict(
                Counter(e["simulated_utr_attested"]["status"] for e in supplemental.values())
            ),
            "positive_targets": positives,
            "correct_positive_links": positive_hits,
            "negative_controls": negatives,
            "correct_negative_abstentions": negative_hits,
            "false_links": false_links,
            "wrong_attestation_422": len(supplemental),
            "stale_version_409": sum(e["stale_version_probed"] for e in supplemental.values()),
            "missing_version_409": sum(e["missing_version_probed"] for e in supplemental.values()),
            "financial_mutations": observed["financial_mutations"],
            "legacy_citation_formats": citation_groups,
        }
        if false_links:
            summary["safety_blockers"].append(f"{split}: incorrect supplemental link")
        details[split] = {"emails": emails, "correlations": records}
    return summary, details
