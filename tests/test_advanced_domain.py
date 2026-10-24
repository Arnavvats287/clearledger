import json
from dataclasses import replace
from itertools import combinations
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clearledger.advanced_domain import Limits, subsets
from clearledger.config import Settings


def rows(amounts):
    return tuple((UUID(int=i + 1), amount) for i, amount in enumerate(amounts))


@pytest.mark.parametrize(
    "amounts,target,outcome,count",
    [
        ([31, 69, 90], 100, "UNIQUE", 1),
        ([31, 69, 40, 60], 100, "AMBIGUOUS", 2),
        ([50, 50, 50], 100, "AMBIGUOUS", 3),
        ([100, 100], 100, "AMBIGUOUS", 2),
        ([5, 9], 8, "UNRESOLVED", 0),
        ([], 10, "UNRESOLVED", 0),
        ([10], 0, "UNRESOLVED", 0),
        ([2**62, 2**62 - 1], 2**63 - 1, "UNIQUE", 1),
    ],
)
def test_exact_combinations(amounts, target, outcome, count):
    result = subsets(rows(amounts), target)
    assert result.outcome == outcome
    assert result.search_exhaustive
    assert len(result.candidates) == count
    assert subsets(tuple(reversed(rows(amounts))), target).candidates == result.candidates


@settings(max_examples=150, deadline=None)
@given(st.lists(st.integers(1, 500), max_size=9), st.integers(1, 2000))
def test_independent_exhaustive_oracle(amounts, target):
    invoices = rows(amounts)
    oracle = {
        tuple(key for key, _ in combination)
        for size in range(1, len(invoices) + 1)
        for combination in combinations(invoices, size)
        if sum(amount for _, amount in combination) == target
    }
    result = subsets(invoices, target, Limits(max_combination_size=9, top_k=100))
    if len(oracle) > 100:
        assert result.outcome == "SEARCH_INCOMPLETE"
    else:
        assert result.search_exhaustive
        assert set(result.candidates) == oracle
        assert result.outcome == (
            "UNIQUE" if len(oracle) == 1 else "AMBIGUOUS" if oracle else "UNRESOLVED"
        )
    for candidate in result.candidates:
        assert len(set(candidate)) == len(candidate)
        assert sum(dict(invoices)[key] for key in candidate) == target


@pytest.mark.parametrize(
    "limits,amounts,target,reason",
    [
        (Limits(max_candidates=2), [1, 2, 3], 3, "CANDIDATE_LIMIT"),
        (Limits(max_combination_size=1), [1, 2, 3], 3, "COMBINATION_SIZE_LIMIT"),
        (Limits(max_work=1), [1, 2, 3], 3, "WORK_LIMIT"),
        (Limits(top_k=1), [50, 50], 50, "TOP_K_LIMIT"),
    ],
)
def test_limits_never_prove_uniqueness(limits, amounts, target, reason):
    result = subsets(rows(amounts), target, limits)
    assert result.outcome == "SEARCH_INCOMPLETE"
    assert result.reason == reason
    assert not result.search_exhaustive
    if reason == "TOP_K_LIMIT":
        assert result.ambiguity_proven


def test_timeout_after_one_solution_never_claims_unique():
    base = subsets(rows([20, 30, 50]), 50)
    # A step clock checks every bounded operation, including matching joins.
    for limit in range(1, base.work + 2):
        ticks = iter(range(1000))
        result = subsets(
            rows([20, 30, 50]),
            50,
            replace(Limits(), max_time_ms=limit),
            clock=lambda ticks=ticks: next(ticks) * 1_000_000,
        )
        if len(result.candidates) == 1:
            assert result.outcome == "SEARCH_INCOMPLETE"
            assert result.reason == "TIME_LIMIT"
            assert not result.search_exhaustive
            break
    else:
        pytest.fail("Clock did not interrupt after the first solution")


def test_work_limit_after_first_solution_never_proves_uniqueness():
    base = subsets(rows([20, 30, 50]), 50)
    for budget in range(1, base.work):
        result = subsets(rows([20, 30, 50]), 50, Limits(max_work=budget))
        if len(result.candidates) == 1:
            assert result.outcome == "SEARCH_INCOMPLETE"
            assert result.reason == "WORK_LIMIT" and not result.search_exhaustive
            break
    else:
        pytest.fail("Work limit did not interrupt after the first candidate")


def test_settings_json_configuration_and_hard_ceiling(monkeypatch):
    limits = Limits(
        max_candidates=25, max_combination_size=7, max_work=9999, max_time_ms=50, top_k=3
    )
    from dataclasses import asdict

    monkeypatch.setenv("MATCHING_LIMITS", json.dumps(asdict(limits)))
    assert Settings(database_url="postgresql+psycopg://unused/unused").matching_limits == limits
    monkeypatch.setenv("MATCHING_LIMITS", '{"max_candidates":41}')
    with pytest.raises(ValueError):
        Settings(database_url="postgresql+psycopg://unused/unused")


@pytest.mark.parametrize("bad", [True, 1.0, -1, 2**63])
def test_strict_integer_paise(bad):
    with pytest.raises((ValueError, TypeError)):
        subsets(rows([bad]), 10)
    with pytest.raises((ValueError, TypeError)):
        subsets(rows([1]), bad)


def test_zero_invoices_duplicate_ids_and_unsafe_limits_rejected():
    with pytest.raises(ValueError):
        subsets(rows([0]), 1)
    with pytest.raises(ValueError):
        subsets(((UUID(int=1), 1), (UUID(int=1), 2)), 3)
    for change in (
        {"max_candidates": 41},
        {"max_work": 0},
        {"top_k": True},
        {"max_work": 1_000_001},
        {"max_combination_size": 41},
        {"max_time_ms": 2001},
        {"top_k": 101},
    ):
        with pytest.raises((ValueError, TypeError)):
            Limits(**change)


def test_worst_case_cap_and_positive_amount_pruning():
    result = subsets(rows([1] * 32), 17, Limits(max_work=3000))
    assert result.outcome == "SEARCH_INCOMPLETE"
    assert result.work == 3000
    assert not result.search_exhaustive
    # Size limits do not prevent proof when all larger combinations exceed cash.
    result = subsets(rows([100, 101]), 100, Limits(max_combination_size=1))
    assert result.outcome == "UNIQUE"
