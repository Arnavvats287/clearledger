import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from clearledger.case_domain import (
    CASE_EDGES,
    CLAIM_EDGES,
    MAX_PAISE,
    CaseError,
    CaseState,
    ClaimState,
    case_transition,
    claim_transition,
    claimed_total,
    retry_seconds,
)
from clearledger.case_schemas import TransitionInput


@given(st.sampled_from(list(CaseState)), st.sampled_from(list(CaseState)))
def test_case_graph_and_financial_capability_boundary(current, target):
    if target not in CASE_EDGES[current]:
        with pytest.raises(CaseError, match="INVALID_CASE_TRANSITION"):
            case_transition(current, target)
    elif target in {CaseState.READY_TO_APPLY, CaseState.PARTIALLY_SETTLED, CaseState.CLOSED}:
        with pytest.raises(CaseError) as error:
            case_transition(current, target)
        assert error.value.status == 403
    else:
        case_transition(current, target)


@given(st.sampled_from(list(ClaimState)), st.sampled_from(list(ClaimState)))
def test_claim_graph_and_adjudication_boundary(current, target):
    protected = {
        ClaimState.SUPPORTED,
        ClaimState.CONTRADICTED,
        ClaimState.ACCEPTED,
        ClaimState.RESOLVED,
    }
    if target not in CLAIM_EDGES[current]:
        with pytest.raises(CaseError, match="INVALID_CLAIM_TRANSITION"):
            claim_transition(current, target, "damage")
    elif target in protected:
        with pytest.raises(CaseError) as error:
            claim_transition(current, target, "damage")
        assert error.value.status == 403
    else:
        claim_transition(current, target, "damage")


@given(st.lists(st.one_of(st.none(), st.integers(0, MAX_PAISE)), max_size=100))
def test_claim_sum_independent_integer_oracle(amounts):
    expected = 0
    unknown = 0
    for amount in amounts:
        if amount is None:
            unknown += 1
        else:
            expected += amount
    assert claimed_total(amounts) == (expected if expected <= MAX_PAISE else None, unknown)


@pytest.mark.parametrize("value", [True, 1.01, "100", -1, MAX_PAISE + 1])
def test_non_paise_claim_rejected(value):
    with pytest.raises(ValueError):
        claimed_total([value])


@given(st.integers(1, 10))
def test_retry_is_bounded_integer(attempt):
    result = retry_seconds(attempt)
    assert type(result) is int and 1 <= result <= 60
    assert result == min(60, 2 ** (attempt - 1))


@pytest.mark.parametrize(
    "extra", [{"financial_authority": True}, {"tools": ["post"]}, {"actor": "admin"}]
)
def test_command_cannot_smuggle_authority(extra):
    with pytest.raises(ValidationError):
        TransitionInput.model_validate({"expected_case_version": 1, "target": "MATCHING", **extra})
