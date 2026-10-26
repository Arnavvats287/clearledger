"""Offline actual-API portfolio walkthrough; only existing synthetic unit fixtures."""

import json

from evaluate_ai_usefulness import ROOT, run_tests


def main():
    result = run_tests(["tests/test_portfolio_demo.py"])
    if result:
        return result
    output = ROOT / "local-data/portfolio-demo"
    accountant = json.loads((output / "accountant.json").read_text(encoding="utf-8"))
    ingestion = json.loads((output / "ingestion.json").read_text(encoding="utf-8"))
    print("OFFLINE PORTFOLIO DEMO PASS: actual API routes + disposable PostgreSQL")
    print("PRIMARY WORKFLOW: one invoice / receipt / remittance / case / claim")
    print(
        f"Invoice={accountant['invoice_open_paise']} paise; "
        f"receipt={accountant['receipt_unapplied_paise']} paise"
    )
    print(
        f"Candidate: {accountant['unattested_outcome']} -> {accountant['candidate_outcome']} "
        f"cash={accountant['candidate_cash_paise']} "
        f"remaining_AR={accountant['candidate_remaining_ar_paise']}"
    )
    print(
        f"Source-backed claim={accountant['claimed_rebate_paise']} paise; "
        f"receipt correlation={accountant['remittance_receipt_link']}; "
        f"verified citation records={accountant['citation_records']}"
    )
    print(
        f"Review: {accountant['finding']} / {accountant['next_action']} / "
        f"{accountant['case_state']}"
    )
    print("Action: review the 101-paise rebate against cited promotion; no adjustment approved")
    print("Actual AR=1101; cash unapplied=1000; verified settlement=0 (paise, unchanged)")
    print("SUPPLEMENTARY CONTROLS:")
    print("Ingestion: customers=1 invoices=1 bank_transactions=1 receipts=1")
    print(
        "Matching:",
        ingestion["matching_without_intent"],
        "->",
        ingestion["matching_with_test_attestation"],
        "(explicit synthetic test attestation)",
    )
    print(
        "Document:",
        ingestion["extraction_route"],
        ingestion["extraction_status"],
        f"claim_amount_paise={ingestion['claim_amount_paise']}",
    )
    for mode in ("supported", "missing", "conflict"):
        row = json.loads((output / f"{mode}.json").read_text(encoding="utf-8"))
        print(
            f"Investigation[{mode}]: {row['state']} {row['next_action']} "
            f"citations={row['citations']} tools={row['tool_calls']}"
        )
    print(
        "Provenance: import audit, original/canonical hashes, "
        "document/case events, graph trace PASS"
    )
    print(
        "Human review REQUIRED; financial authority FALSE; "
        "financial non-mutation PASS (5 scenarios)"
    )
    print("External AI DISABLED; no posting or approvals; no benchmark access")
    print("Synthetic observations:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
