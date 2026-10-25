"""Settlement metadata derives only from a committed-in-transaction ledger application."""

from sqlalchemy import select

from clearledger.case_domain import CASE_EDGES, CLAIM_EDGES, CaseError, CaseState, ClaimState
from clearledger.case_lifecycle import revise
from clearledger.case_models import Claim
from clearledger.case_repository import root
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.finance_models import LedgerJournal, NoncashSettlement
from clearledger.matching import owned


def update(session, org, proposal, principal, settings):
    journal = session.scalar(
        select(LedgerJournal).where(
            LedgerJournal.organization_id == org,
            LedgerJournal.proposal_id == proposal.id,
            LedgerJournal.kind == "APPLICATION",
        )
    )
    if journal is None or proposal.state != "SIMULATED_POSTED":
        raise CaseError("POSTED_LIFECYCLE_PROOF_REQUIRED", 403)
    case = root(session, org, proposal.case_id)
    changed = []
    for result in proposal.treatments:
        claim = owned(session, Claim, org, result["claim_id"])
        target = (
            "RESOLVED"
            if result["allowed_paise"]
            else (
                "NEEDS_TAX_REVIEW" if result["category"] == "tax" else "AWAITING_CUSTOMER_EVIDENCE"
            )
        )
        if (
            result["allowed_paise"]
            and session.scalar(
                select(NoncashSettlement.id).where(
                    NoncashSettlement.organization_id == org,
                    NoncashSettlement.claim_id == claim.id,
                    NoncashSettlement.journal_id == journal.id,
                )
            )
            is None
        ):
            raise CaseError("CLAIM_SETTLEMENT_PROOF_REQUIRED")
        # Choose only graph edges; authority comes from this ledger proof, not public labels.
        paths = {
            "RESOLVED": ["INVESTIGATING", "SUPPORTED", "ACCEPTED", "RESOLVED"],
            "AWAITING_CUSTOMER_EVIDENCE": [
                "INVESTIGATING",
                "INSUFFICIENT_EVIDENCE",
                "AWAITING_CUSTOMER_EVIDENCE",
            ],
            "NEEDS_TAX_REVIEW": ["INVESTIGATING", "NEEDS_TAX_REVIEW"],
        }
        for state in paths[target]:
            if claim.state == target:
                break
            if ClaimState(state) not in CLAIM_EDGES[ClaimState(claim.state)]:
                continue
            claim.state = state
            claim.version += 1
            changed.append(claim)
            revise(
                session,
                org,
                case,
                principal.identity,
                "case.claim_settlement_observed",
                EvidenceOriginals(settings.document_root),
                changed_claims=[claim],
                invalidate=True,
                enqueue=False,
                reopen_claims=False,
                details={"proposal_id": str(proposal.id), "journal_id": str(journal.id)},
            )
        if claim.state != target:
            raise CaseError("SETTLEMENT_LIFECYCLE_CONFLICT")
    # Financial partial settlement is introduced here; operational closure remains M09.
    for target in ("INVESTIGATING", "READY_TO_APPLY", "PARTIALLY_SETTLED"):
        if case.state == target:
            continue
        if CaseState(target) not in CASE_EDGES[CaseState(case.state)]:
            raise CaseError("FINANCE_CASE_TRANSITION_INVALID")
        case.state = target
        revise(
            session,
            org,
            case,
            principal.identity,
            "case.simulated_settlement",
            EvidenceOriginals(settings.document_root),
            invalidate=target == "INVESTIGATING",
            enqueue=False,
            reopen_claims=False,
            details={"proposal_id": str(proposal.id), "journal_id": str(journal.id)},
        )
