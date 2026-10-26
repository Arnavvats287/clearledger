"""Offline proof of live-smoke blockers; never sends a key or prompt externally."""

from decimal import Decimal
from typing import get_args

import pytest
from test_imports import environment as environment
from test_provider_controls import policy, reservations

from clearledger.config import Settings
from clearledger.document_contract import ExtractionError
from clearledger.extraction_provider import FakeTransport, Gateway
from clearledger.provider_budget import reserve


def test_exact_configuration_names_and_standard_price_reservation():
    assert "gemini_enabled" not in Settings.model_fields
    assert get_args(Settings.model_fields["extraction_provider"].annotation) == (
        "disabled",
        "gemini",
        "fake",
    )
    # Current official USD / million text-token rates, not a verified INR quote.
    per_attempt = (8192 * Decimal("0.25") + 512 * Decimal("1.50")) / 1_000_000
    assert per_attempt == Decimal("0.002816")
    assert 5 * per_attempt == Decimal("0.014080")
    assert 8 * per_attempt == Decimal("0.022528")
    # Five maximum reservations exceed INR1 whenever USD/INR exceeds this threshold.
    assert Decimal(1) / (5 * per_attempt) < Decimal("71.03")


@pytest.mark.postgres
def test_requested_two_http_operations_per_minute_denies_before_transport(environment):
    engine, org, _, _, _ = environment
    settings = policy(
        llm_shared_requests_per_minute=2,
        llm_daily_requests=8,
        llm_max_input_tokens=8192,
        llm_max_output_tokens=512,
        llm_attempts=1,
    )
    transport = FakeTransport([])
    with pytest.raises(ExtractionError, match="PROVIDER_SHARED_RATE_LIMIT"):
        Gateway(transport, attempts=1, requests_per_minute=2).generate(
            ["approved synthetic placeholder"],
            before_attempt=lambda: reserve(engine, org, "fake", settings),
        )
    assert not transport.calls and reservations(engine, org) == []


@pytest.mark.postgres
def test_eight_daily_http_operations_admits_only_two_complete_attempts(environment):
    engine, org, _, _, _ = environment
    settings = policy(llm_daily_requests=8)
    for _ in range(2):
        result = reserve(engine, org, "fake", settings)
        assert result["reserved_requests"] == 3
    with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED"):
        reserve(engine, org, "fake", settings)
    assert len(reservations(engine, org)) == 2


def test_reduced_profile_reserves_less_than_one_rupee_for_five_attempts():
    # Official USD prices converted at conservative INR110/USD, plus20% contingency.
    input_rate = Decimal("0.25") * 110 * 100 * Decimal("1.20")
    output_rate = Decimal("1.50") * 110 * 100 * Decimal("1.20")
    assert (input_rate, output_rate) == (3300, 19800)
    reserved = (2048 * int(input_rate) + 512 * int(output_rate) + 999999) // 1000000
    assert reserved == 17
    assert 5 * reserved == 85 < 100


@pytest.mark.postgres
def test_reduced_profile_admits_three_operations_without_relaxing_reservation(environment):
    engine, org, _, _, _ = environment
    settings = policy(
        llm_attempts=1,
        llm_requests_per_minute=1,
        llm_shared_requests_per_minute=3,
        llm_daily_requests=15,
        llm_daily_input_tokens=10240,
        llm_daily_output_tokens=2560,
        llm_max_input_tokens=2048,
        llm_max_output_tokens=512,
        llm_input_paise_per_million_tokens=3300,
        llm_output_paise_per_million_tokens=19800,
        llm_max_cost_paise_per_attempt=17,
    )
    admitted = reserve(engine, org, "fake", settings)
    assert admitted["reserved_requests"] == 3
    assert admitted["reserved_input_tokens"] == 2048
    assert admitted["reserved_output_tokens"] == 512
    with pytest.raises(ExtractionError, match="PROVIDER_SHARED_RATE_LIMIT"):
        reserve(engine, org, "fake", settings)


def test_approved_prose_has_exact_reviewed_privacy_projection():
    from test_ai_usefulness import PROSE

    from clearledger.document_privacy import project

    visible = project([PROSE])
    assert visible.pages == [
        "Invoice I-1: payment INR 9.00; damage INR 1.01 disputed, "
        + "\u2588" * 6
        + " "
        + "\u2588" * 8
        + "."
    ]
    assert len(visible.pages[0]) == len(PROSE)
    assert visible.masks
