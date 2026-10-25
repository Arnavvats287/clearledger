from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from clearledger.review_contract import DraftInput, EvidenceRequest, Note
from clearledger.review_password import encode, verify


def test_password_salt_bounded_and_no_plaintext():
    password = "isolated-password-123456789"
    first, second = encode(password), encode(password)
    assert first != second and password not in first
    assert verify(password, first) and not verify("wrong", first)
    assert not verify(password, "corrupt") and not verify(password, first.replace("600000", "1"))
    with pytest.raises(ValueError):
        encode("short")
    with pytest.raises(ValueError):
        encode("x" * 129)


@pytest.mark.parametrize("invalid", [True, 1.5, "1", 0, -1, 2**31])
def test_review_versions_strict(invalid):
    with pytest.raises(ValidationError):
        Note(
            expected_case_version=invalid, expected_context_sha256="0" * 64, reason="REVIEW_COMMENT"
        )


@given(st.lists(st.uuids(), min_size=1, max_size=20, unique=True))
def test_draft_source_lists_unique_bounded(ids):
    draft = DraftInput(
        expected_case_version=1,
        expected_context_sha256="0" * 64,
        reason="CUSTOMER_FOLLOW_UP",
        invoice_ids=ids,
    )
    assert len(draft.invoice_ids) == len(set(ids))
    with pytest.raises(ValidationError):
        DraftInput(**{**draft.model_dump(), "invoice_ids": ids + [ids[0]]})


def test_partial_proposal_binding_and_unknown_authority_rejected():
    base = {
        "expected_case_version": 1,
        "expected_context_sha256": "0" * 64,
        "reason": "MISSING_EVIDENCE",
        "claim_ids": [uuid4()],
    }
    with pytest.raises(ValidationError):
        EvidenceRequest(**base, proposal_id=uuid4())
    with pytest.raises(ValidationError):
        EvidenceRequest(**base, role="CONTROLLER")
