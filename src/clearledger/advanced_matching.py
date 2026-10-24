"""Advanced immutable candidate proposals reusing exact-v1 evidence and transaction guards."""

import json
from dataclasses import asdict
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from clearledger.advanced_domain import Limits, subsets
from clearledger.imports import event
from clearledger.matching import build_snapshot, digest, lock_company, owned, prior_request
from clearledger.models import Invoice, MatchingProposal, MatchingRequest

ALGORITHM = "advanced-mitm-v1"


def context(session, organization_id, receipt_id, limits, structured=False):
    receipt, bank, snapshot = build_snapshot(
        session, organization_id, receipt_id, advanced=True, invoice_budget=limits.max_candidates
    )
    snapshot.update(
        algorithm=ALGORITHM,
        limits=asdict(limits),
        use_structured_allocations=structured,
        receipt_date=bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat(),
    )
    # Source text already lives in immutable ingestion; retain its digest and stable pointer.
    snapshot["bank"].update(source_import_id=str(bank.source_import_id), source_row=bank.source_row)
    return receipt, bank, snapshot


def structured_amounts(memo):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate structured key")
            result[key] = value
        return result

    try:
        value = json.loads(memo, object_pairs_hook=unique_object)
        if type(value) is not dict or set(value) != {"allocations_paise"}:
            return None
        amounts = value["allocations_paise"]
        if (
            type(amounts) is not dict
            or not amounts
            or any(
                type(amount) is not int or not 0 < amount <= 2**63 - 1
                for amount in amounts.values()
            )
        ):
            return None
        return amounts
    except (ValueError, TypeError, RecursionError):
        return None


def analyze(snapshot, memo):
    limits = Limits(**snapshot["limits"])
    validation = snapshot["validation"]
    receipt = snapshot["receipt"]
    result = {
        "algorithm": ALGORITHM,
        "outcome": "UNRESOLVED",
        "reason": "UNRESOLVED_CUSTOMER",
        "search_exhaustive": True,
        "requires_review": True,
        "intent_verified": False,
        "candidates": [],
        "partial_analysis": [],
        "work": 0,
        "elapsed_ns": 0,
    }
    if validation["input_limit_exceeded"]:
        result.update(outcome="SEARCH_INCOMPLETE", reason="INPUT_LIMIT", search_exhaustive=False)
        return result
    if validation["invalid_evidence"]:
        result["reason"] = "STALE_OR_INVALID_EVIDENCE"
        return result
    owners = validation["customers"]
    if len(owners) != 1:
        if owners:
            result.update(outcome="AMBIGUOUS", reason="CONFLICTING_CUSTOMER_EVIDENCE")
        return result
    cash = receipt["unapplied_amount_paise"]
    if cash <= 0 or receipt["status"] not in {"UNAPPLIED", "PARTIALLY_APPLIED"}:
        result["reason"] = "NO_AVAILABLE_CASH"
        return result
    eligible = {
        row["id"]: row
        for row in snapshot["invoices"]
        if row["customer_id"] == owners[0]
        and row["status"] == "OPEN"
        and row["open_amount_paise"] > 0
        and row["currency"] == "INR"
        and row["issued_date"] <= snapshot["receipt_date"]
    }

    def candidate(amounts):
        return {
            "allocations": [
                {
                    "invoice_id": key,
                    "invoice_version": eligible[key]["version"],
                    "open_amount_paise": eligible[key]["open_amount_paise"],
                    "amount_paise": amount,
                    "remaining_ar_paise": eligible[key]["open_amount_paise"] - amount,
                    "reference_evidence_ids": [
                        item["id"]
                        for item in snapshot["basis"]
                        if item.get("invoice_id") == key
                        and item.get("valid")
                        and not item.get("superseded", False)
                    ],
                    "amount_evidence": (
                        {
                            "source_import_id": snapshot["bank"]["source_import_id"],
                            "source_row": snapshot["bank"]["source_row"],
                            "source_field": "memo",
                            "json_pointer": "/allocations_paise/"
                            + eligible[key]["invoice_number"].replace("~", "~0").replace("/", "~1"),
                            "payload_sha256": snapshot["bank"]["payload_sha256"],
                        }
                        if snapshot["use_structured_allocations"]
                        else None
                    ),
                }
                for key, amount in sorted(amounts.items())
            ],
            "total_paise": sum(amounts.values()),
            "remaining_cash_paise": cash - sum(amounts.values()),
        }

    references = validation["references"]
    if references:
        if not snapshot["use_structured_allocations"] and memo.startswith("{"):
            # Never discard supplied amount instructions and label full balances as verified intent.
            result["reason"] = "STRUCTURED_ALLOCATION_MODE_REQUIRED"
            return result
        if any(key not in eligible for key in references):
            result["reason"] = "INELIGIBLE_REFERENCED_INVOICE"
            return result
        if len(references) > limits.max_combination_size:
            result.update(
                outcome="SEARCH_INCOMPLETE",
                reason="COMBINATION_SIZE_LIMIT",
                search_exhaustive=False,
            )
            return result
        if snapshot["use_structured_allocations"]:
            supplied = structured_amounts(memo)
            # IDs/versions/intent come from verified reference attestations, never JSON alone.
            names = {}
            # Invoice numbers are included only in advanced input snapshots.
            for key in references:
                names[eligible[key]["invoice_number"]] = key
            if supplied is None or set(supplied) != set(names):
                result["reason"] = "INVALID_STRUCTURED_ALLOCATION_EVIDENCE"
                return result
            amounts = {names[name]: value for name, value in supplied.items()}
        else:
            amounts = {key: eligible[key]["open_amount_paise"] for key in references}
            if len(references) == 1:
                amounts[references[0]] = min(cash, amounts[references[0]])
        if any(value > eligible[key]["open_amount_paise"] for key, value in amounts.items()):
            result["reason"] = "INVOICE_OVERALLOCATION"
        elif not snapshot["use_structured_allocations"] and sum(amounts.values()) != cash:
            result["reason"] = "EXPLICIT_ALLOCATION_INSTRUCTIONS_REQUIRED"
        elif sum(amounts.values()) > cash:
            result["reason"] = "RECEIPT_OVERALLOCATION"
        else:
            result.update(
                outcome="UNIQUE",
                reason="VERIFIED_REFERENCES",
                intent_verified=True,
                candidates=[candidate(amounts)],
            )
        return result
    if snapshot["use_structured_allocations"]:
        result["reason"] = "VERIFIED_REFERENCES_REQUIRED"
        return result
    search = subsets(
        tuple((UUID(key), row["open_amount_paise"]) for key, row in eligible.items()), cash, limits
    )
    result.update(asdict(search))
    result["candidates"] = [
        candidate({str(key): eligible[str(key)]["open_amount_paise"] for key in ids})
        for ids in search.candidates
    ]
    if search.outcome == "UNIQUE":
        result["reason"] = "MATHEMATICAL_UNIQUENESS_ONLY"
    if search.outcome == "UNRESOLVED":
        # These are possibilities, not allocations or authorized invoice settlements.
        partial = [key for key, row in sorted(eligible.items()) if row["open_amount_paise"] > cash]
        result["partial_analysis"] = [candidate({key: cash}) for key in partial[: limits.top_k]]
        result["partial_analysis_truncated"] = len(partial) > limits.top_k
        if partial:
            result["reason"] = "PARTIAL_INSTRUCTIONS_REQUIRED"
    return result


def create_advanced(session, organization_id, receipt_id, body, key, actor, limits):
    lock_company(session, organization_id)
    fingerprint = digest({"operation": ALGORITHM, **body.model_dump(mode="json")})
    prior = prior_request(session, organization_id, receipt_id, key, fingerprint)
    receipt, bank, snapshot = context(
        session, organization_id, receipt_id, limits, body.use_structured_allocations
    )
    snapshot_hash = digest(snapshot)
    if receipt.version != body.expected_receipt_version:
        raise HTTPException(409, "STALE_RECEIPT_VERSION")
    for invoice_id, version in body.expected_invoice_versions.items():
        if owned(session, Invoice, organization_id, invoice_id).version != version:
            raise HTTPException(409, "STALE_INVOICE_VERSION")
    if body.expected_snapshot_sha256 is not None and body.expected_snapshot_sha256 != snapshot_hash:
        raise HTTPException(409, "STALE_SNAPSHOT")
    if prior is not None:
        proposal = owned(session, MatchingProposal, organization_id, prior.proposal_id)
        if proposal.snapshot_sha256 != snapshot_hash:
            raise HTTPException(409, "STALE_PROPOSAL")
        return proposal
    proposal = session.scalar(
        select(MatchingProposal).where(
            MatchingProposal.organization_id == organization_id,
            MatchingProposal.receipt_id == receipt_id,
            MatchingProposal.snapshot_sha256 == snapshot_hash,
        )
    )
    result = proposal.result if proposal else analyze(snapshot, bank.memo)
    required = {
        UUID(allocation["invoice_id"])
        for item in result["candidates"]
        for allocation in item["allocations"]
    }
    if not required.issubset(body.expected_invoice_versions):
        raise HTTPException(409, "EXPECTED_INVOICE_VERSION_REQUIRED")
    if proposal is None:
        owners = snapshot["validation"]["customers"]
        proposal = MatchingProposal(
            organization_id=organization_id,
            receipt_id=receipt_id,
            source_import_id=bank.source_import_id,
            customer_id=UUID(owners[0]) if len(owners) == 1 else None,
            invoice_id=None,
            amount_paise=0,  # Candidate analysis is never an executable cash allocation.
            outcome=result["outcome"],
            snapshot_sha256=snapshot_hash,
            snapshot=snapshot,
            result=result,
        )
        session.add(proposal)
        session.flush()
        event(
            session,
            organization_id,
            bank.source_import_id,
            actor,
            "matching.proposal_created",
            proposal.id,
        )
    session.add(
        MatchingRequest(
            organization_id=organization_id,
            receipt_id=receipt_id,
            idempotency_key=key,
            request_sha256=fingerprint,
            proposal_id=proposal.id,
        )
    )
    session.commit()
    return proposal
