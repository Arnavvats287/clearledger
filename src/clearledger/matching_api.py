from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query
from sqlalchemy import select

from clearledger.api import DB, Scope
from clearledger.matching import build_snapshot, create_proposal, digest, owned, register_evidence
from clearledger.matching_schemas import EvidenceInput, MatchInput
from clearledger.models import MatchingEvidence, MatchingProposal, Receipt
from clearledger.views import RecordView

router = APIRouter()
Actor = Annotated[
    str, Header(alias="X-Actor-ID", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.@-]+$")
]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


class EvidenceView(RecordView):
    receipt_id: UUID
    customer_id: UUID
    invoice_id: UUID | None
    receipt_version: int
    customer_version: int
    invoice_version: int | None
    kind: str
    source_import_id: UUID
    source_row: int
    source_field: str
    start_offset: int
    end_offset: int
    exact_quote: str
    verified_by: str
    payload_sha256: str


class ProposalView(RecordView):
    receipt_id: UUID
    source_import_id: UUID
    customer_id: UUID | None
    invoice_id: UUID | None
    amount_paise: int
    outcome: str
    snapshot_sha256: str
    snapshot: dict
    result: dict
    is_stale: bool = False
    current_snapshot_sha256: str = ""


def proposal_payload(session, organization_id, proposal, current_hash=None):
    if current_hash is None:
        _, _, current = build_snapshot(session, organization_id, proposal.receipt_id)
        current_hash = digest(current)
    view = ProposalView.model_validate(proposal)
    view.is_stale = proposal.snapshot_sha256 != current_hash
    view.current_snapshot_sha256 = current_hash
    return view


@router.post("/receipts/{receipt_id}/matching-evidence", response_model=EvidenceView)
def verify_evidence(
    receipt_id: UUID,
    body: EvidenceInput,
    session: DB,
    organization_id: Scope,
    actor: Actor,
    key: Key,
):
    return register_evidence(session, organization_id, receipt_id, body, key, actor)


@router.get("/receipts/{receipt_id}/matching-evidence", response_model=list[EvidenceView])
def evidence_list(
    receipt_id: UUID,
    session: DB,
    organization_id: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    owned(session, Receipt, organization_id, receipt_id)
    return session.scalars(
        select(MatchingEvidence)
        .where(
            MatchingEvidence.organization_id == organization_id,
            MatchingEvidence.receipt_id == receipt_id,
        )
        .order_by(MatchingEvidence.created_at, MatchingEvidence.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/receipts/{receipt_id}/matching-context")
def matching_context(receipt_id: UUID, session: DB, organization_id: Scope):
    _, _, snapshot = build_snapshot(session, organization_id, receipt_id)
    return {"snapshot_sha256": digest(snapshot), "snapshot": snapshot}


@router.post("/receipts/{receipt_id}/match", response_model=ProposalView)
def match_receipt(
    receipt_id: UUID, body: MatchInput, session: DB, organization_id: Scope, actor: Actor, key: Key
):
    proposal = create_proposal(session, organization_id, receipt_id, body, key, actor)
    return proposal_payload(session, organization_id, proposal)


@router.get("/receipts/{receipt_id}/matches", response_model=list[ProposalView])
def proposal_list(
    receipt_id: UUID,
    session: DB,
    organization_id: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    _, _, snapshot = build_snapshot(session, organization_id, receipt_id)
    current_hash = digest(snapshot)
    proposals = session.scalars(
        select(MatchingProposal)
        .where(
            MatchingProposal.organization_id == organization_id,
            MatchingProposal.receipt_id == receipt_id,
        )
        .order_by(MatchingProposal.created_at, MatchingProposal.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        proposal_payload(session, organization_id, proposal, current_hash) for proposal in proposals
    ]


@router.get("/matching-proposals/{proposal_id}", response_model=ProposalView)
def get_proposal(proposal_id: UUID, session: DB, organization_id: Scope):
    proposal = owned(session, MatchingProposal, organization_id, proposal_id)
    return proposal_payload(session, organization_id, proposal)
