"""Deterministic objectives and conservative consistency, independent of LangGraph."""

from clearledger.document_contract import Category
from clearledger.evidence_contract import Question, Verification
from clearledger.investigation_contract import (
    Action,
    Conclusion,
    Finding,
    Objective,
    OfferedPointer,
    Proposal,
    Tool,
)

PRIMARY: dict[Category, Question] = {
    "damage": "DELIVERY_DAMAGE",
    "short_shipment": "DELIVERY_SHORTAGE",
    "rebate": "PROMOTION_AMOUNT",
    "early_discount": "PROMOTION_AMOUNT",
    "tax": "TAX_DOCUMENT",
    "other": "CLAUSE_LIMIT",
    "unknown": "CLAUSE_LIMIT",
}
SEARCH: dict[Question, list[Tool]] = {
    "DELIVERY_DAMAGE": ["get_wms_deliveries", "get_proof_of_delivery"],
    "DELIVERY_SHORTAGE": ["get_wms_deliveries", "get_proof_of_delivery"],
    "PROMOTION_AMOUNT": ["find_promotions"],
    "TAX_DOCUMENT": ["get_tagged_tax_evidence"],
    "CLAUSE_LIMIT": ["find_contract_clauses"],
}


def consistency(
    objective: Objective,
    proposal: Proposal | None,
    verification: Verification | None,
    citations: list[OfferedPointer],
    *,
    error: str | None = None,
    incomplete: bool = False,
) -> Finding:
    unknowns = set(objective.unknowns)
    if proposal:
        unknowns.update(proposal.unknowns)
    state: Conclusion = "INSUFFICIENT_EVIDENCE"
    contradictions = []
    action: Action = "REQUEST_EVIDENCE"
    if error:
        unknowns.add(
            "FORGED_CITATION"
            if error == "FORGED_CITATION"
            else "STALE_INPUTS"
            if error == "STALE_INPUTS"
            else "BUDGET_EXHAUSTED"
            if error
            in {
                "ROUND_LIMIT",
                "TOOL_LIMIT",
                "TOKEN_LIMIT",
                "SPEND_LIMIT",
                "TIMEOUT",
                "REPEATED_TOOL",
            }
            else "PROVIDER_FAILURE"
        )
        action = "HUMAN_REVIEW"
    if incomplete:
        unknowns.add("SEARCH_INCOMPLETE")
    if verification:
        contradictions = sorted(
            {
                reason
                for f in verification.findings
                for reason in f.reasons
                if f.outcome == "CONTRADICTED" or "CONFLICT" in reason
            }
        )
        if verification.outcome in {"SUPPORTED", "CONTRADICTED"} and not unknowns and citations:
            state = "SUPPORTED" if verification.outcome == "SUPPORTED" else "CONTRADICTED"
            action = "HUMAN_REVIEW"
        elif verification.outcome == "INSUFFICIENT":
            unknowns.add("CONFLICTING_EVIDENCE" if contradictions else "MISSING_EVIDENCE")
    else:
        unknowns.add("MISSING_EVIDENCE")
    if proposal and proposal.classification != objective.category:
        unknowns.add("UNSUPPORTED_CLASSIFICATION")
        state = "INSUFFICIENT_EVIDENCE"
    if objective.category == "tax":
        state, action = "NEEDS_TAX_REVIEW", "TAX_REVIEW"
        unknowns.add("NEEDS_TAX_REVIEW")
    if error or incomplete or unknowns:
        state = "NEEDS_TAX_REVIEW" if objective.category == "tax" else "INSUFFICIENT_EVIDENCE"
    return Finding(
        claim_id=objective.claim_id,
        classification=objective.category,
        state=state,
        source_facts=[verification] if verification else [],
        citations=citations,
        inference="PREDICATE_MAY_APPLY"
        if state == "SUPPORTED"
        else "POSSIBLE_CONTRADICTION"
        if state == "CONTRADICTED"
        else "NO_BACKED_CONCLUSION",
        contradictions=contradictions,
        unknowns=sorted(unknowns),
        next_action=action,
    )
