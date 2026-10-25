"""Prediction projection from runtime observations only; no answer/scorer imports."""

from collections import Counter


def receipt_key(bank):
    return {k: bank[k] for k in ("source_system", "account_ref", "external_transaction_id")}


def snapshot_predictions(data, matching, as_of):
    banks = {row["id"]: row for row in data["bank-transactions"]}
    customers = {row["id"]: row["external_reference"] for row in data["customers"]}
    result = []
    for receipt in data["receipts"]:
        observed = matching.get(receipt["id"], {})
        if observed.get("match", {}).get("outcome") == "EXACT_MATCH":
            raise ValueError("Unattested baseline unexpectedly produced supported exact match")
        advanced = observed.get("match-advanced", {})
        # No verification attestations are created by this baseline. Candidate
        # uniqueness is not intent; no proposal is projected into executed cash.
        if advanced.get("result", {}).get("intent_verified"):
            raise ValueError("Unattested baseline unexpectedly gained verified intent")
        customer = advanced.get("customer_id") or observed.get("match", {}).get("customer_id")
        result.append(
            {
                "receipt": receipt_key(banks[receipt["bank_transaction_id"]]),
                "as_of": as_of,
                "customer_reference": customers.get(customer),
                "abstain_invoice_allocation": True,
                "cash_allocations": [],
                "financial_authority": False,
                "human_reviews": ["REVIEW REQUIRED: verify identity, intent and source evidence"],
            }
        )
    return result


def outcome_counts(matching):
    return {
        algorithm: dict(
            Counter(
                value.get(algorithm, {}).get("outcome", "API_FAILURE")
                for value in matching.values()
            )
        )
        for algorithm in ("match", "match-advanced")
    }


def latency_summary(values):
    if not values:
        return {"count": 0, "p50_ns": None, "p95_ns": None, "max_ns": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "p50_ns": ordered[(len(values) - 1) // 2],
        "p95_ns": ordered[(95 * len(values) + 99) // 100 - 1],
        "max_ns": ordered[-1],
    }
