"""Evidence/case association review, never payment approval."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from clearledger.evidence_contract import Hash, Strict
from clearledger.review_contract import Basis

ALGORITHM = "source-correlation-v1"


class RefreshInput(Strict):
    pass


class DecisionInput(Basis):
    expected_task_sha256: Hash
    decision: Literal["CONFIRM", "REJECT"]


class TaskView(Strict):
    id: UUID
    case_id: UUID
    document_id: UUID
    extraction_id: UUID
    input_sha256: Hash
    reason: str
    next_action: str
    candidates: list[dict[str, object]]
    status: Literal["PENDING", "CONFIRMED", "REJECTED", "STALE"]
    is_stale: bool
    created_at: datetime
    financial_authority: Literal[False] = False
    requires_human_review: Literal[True] = True


class DecisionView(Strict):
    id: UUID
    task_id: UUID
    decision: str
    actor: dict[str, object]
    receipt_id: UUID | None
    invoice_id: UUID | None
    association_id: UUID | None
    created_at: datetime
    is_stale: bool = False
    financial_authority: Literal[False] = False
