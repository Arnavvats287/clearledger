"""Offline cost-control tests; tiny isolated fixtures, no provider network calls."""

import io
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_document_domain import minimal_model_result
from test_documents import documents_environment as documents_environment
from test_documents import enable_fake, extract, upload
from test_imports import environment as environment
from test_restart_persistence import running_api, tenant_rows

from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.document_contract import ExtractionError
from clearledger.document_privacy import project
from clearledger.extraction_provider import FakeTransport, Gateway, ProviderFailure, ProviderReply
from clearledger.models import ProviderReservation
from clearledger.provider_budget import reserve


def policy(**changes):
    return Settings(_env_file=None, database_url="postgresql+psycopg://unused/unused", **changes)


def reservations(engine, org):
    return tenant_rows(engine, org, (ProviderReservation,))["provider_reservations"]


@pytest.mark.postgres
@pytest.mark.parametrize("limit", ["requests", "input_tokens", "output_tokens"])
def test_daily_caps_fail_closed_before_transport(environment, limit):
    engine, org, _, _, _ = environment
    settings = policy(**{f"llm_daily_{limit}": 0})
    transport = FakeTransport([ProviderReply("{}", 1, 1)])
    gateway = Gateway(transport)
    with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED"):
        gateway.generate(["safe"], before_attempt=lambda: reserve(engine, org, "fake", settings))
    assert transport.calls == [] and reservations(engine, org) == []


@pytest.mark.postgres
def test_exact_quota_boundary_failure_and_retry_remain_charged(environment):
    engine, org, _, _, _ = environment
    settings = policy(
        llm_daily_requests=3, llm_daily_input_tokens=8192, llm_daily_output_tokens=4096
    )
    transport = FakeTransport([ProviderFailure("private failure body", retryable=True)])
    gateway = Gateway(transport, sleep=lambda _: None)
    with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED") as error:
        gateway.generate(["safe"], before_attempt=lambda: reserve(engine, org, "fake", settings))
    assert len(transport.calls) == 1
    assert error.value.metrics["attempts"] == 1
    assert len(error.value.metrics["budget_reservations"]) == 1
    assert "private failure body" not in str(error.value.metrics)
    assert len(reservations(engine, org)) == 1
    # New gateway/process-local counters cannot refund the shared reservation.
    with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED"):
        reserve(engine, org, "fake", settings)


@pytest.mark.postgres
def test_shared_minute_limit_and_tenant_scope(environment):
    engine, org, other, _, _ = environment
    settings = policy(llm_shared_requests_per_minute=3)
    reserve(engine, org, "fake", settings)
    with pytest.raises(ExtractionError, match="PROVIDER_SHARED_RATE_LIMIT"):
        reserve(engine, org, "fake", settings)
    reserve(engine, other, "fake", settings)
    assert len(reservations(engine, org)) == len(reservations(engine, other)) == 1


@pytest.mark.postgres
def test_real_sessions_compete_for_last_slot_without_overspending(environment):
    engine, org, _, _, _ = environment
    barrier = Barrier(2)
    settings = policy(llm_daily_requests=3)

    def submit():
        with engine.connect() as connection:
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            try:
                return pid, reserve(engine, org, "fake", settings)
            except ExtractionError as error:
                return pid, str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert results[0][0] != results[1][0]
    assert sum(isinstance(result, dict) for _, result in results) == 1
    assert [r for _, r in results if isinstance(r, str)] == ["PROVIDER_DAILY_BUDGET_EXHAUSTED"]
    assert len(reservations(engine, org)) == 1


@pytest.mark.postgres
def test_reservation_survives_rollback_connection_and_application_restart(environment):
    engine, org, _, _, _ = environment
    settings = policy(llm_daily_requests=3)
    with Session(engine) as outer:
        outer.execute(text("SELECT 1"))
        reserve(engine, org, "fake", settings)
        outer.rollback()
    before = reservations(engine, org)
    url = engine.url.render_as_string(hide_password=False)
    with running_api(url, org) as (_, first_pid):
        pass
    with running_api(url, org) as (_, second_pid):
        assert first_pid != second_pid
    fresh = build_engine(url)
    try:
        assert reservations(fresh, org) == before
        with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED"):
            reserve(fresh, org, "fake", settings)
        with fresh.connect() as connection:
            with pytest.raises(ExtractionError, match="PROVIDER_BUDGET_UNAVAILABLE"):
                reserve(connection, org, "fake", settings)
    finally:
        fresh.dispose()


@pytest.mark.postgres
@pytest.mark.parametrize(
    "operation",
    [
        "UPDATE provider_reservations SET requests=3",
        "DELETE FROM provider_reservations",
        "TRUNCATE provider_reservations",
    ],
)
def test_reservation_history_is_immutable(environment, operation):
    engine, org, _, _, _ = environment
    reserve(engine, org, "fake", policy())
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(operation))
    assert len(reservations(engine, org)) == 1


@pytest.mark.postgres
def test_utc_day_rollover_does_not_consume_new_day_budget(environment):
    engine, org, _, _, _ = environment
    yesterday = datetime.now(UTC) - timedelta(days=1)
    with Session(engine) as session, session.begin():
        session.add(
            ProviderReservation(
                organization_id=org,
                provider="fake",
                quota_day=yesterday.date(),
                created_at=yesterday,
                requests=3,
                input_tokens=8192,
                output_tokens=4096,
            )
        )
    reserve(engine, org, "fake", policy(llm_daily_requests=3))
    assert len(reservations(engine, org)) == 2


@pytest.mark.postgres
@pytest.mark.parametrize(
    "rates,ceiling,code",
    [
        ({}, 1, "PROVIDER_PRICE_UNVERIFIED"),
        (
            {
                "llm_input_paise_per_million_tokens": 1000000,
                "llm_output_paise_per_million_tokens": 1000000,
            },
            12287,
            "PROVIDER_COST_LIMIT",
        ),
    ],
)
def test_optional_integer_cost_ceiling_fails_closed(environment, rates, ceiling, code):
    engine, org, _, _, _ = environment
    with pytest.raises(ExtractionError, match=code):
        reserve(engine, org, "fake", policy(llm_max_cost_paise_per_attempt=ceiling, **rates))
    assert reservations(engine, org) == []


@pytest.mark.postgres
def test_successful_revision_reuse_without_new_quota_or_financial_changes(documents_environment):
    engine, org, _, client, _ = documents_environment
    source = "Name: PrivateCanary\nPAN: ABCDE1234F\nInvoice I-1 paid INR 1.00."
    doc = upload(client, source.encode()).json()
    visible = project([source]).pages[0]
    transport = enable_fake(
        client, [ProviderReply(json.dumps(minimal_model_result(visible)), 15, 20)]
    )
    before = tenant_rows(engine, org)
    first = extract(client, doc["id"], allow_external=True).json()
    assert first["error_code"] is None and first["result"]
    prior = reservations(engine, org)
    assert len(prior) == 1
    client.app.state.settings.llm_daily_requests = 0
    second = extract(client, doc["id"], allow_external=True, revision_label="retry").json()
    assert second["id"] != first["id"] and second["result"] == first["result"]
    assert second["metrics"]["cache_hit"] is True
    assert second["metrics"]["cached_from_extraction_id"] == first["id"]
    assert second["metrics"]["estimated_cost_paise"] == 0
    assert second["metrics"]["attempts"] == 0
    assert len(transport.calls) == 1 and "PrivateCanary" not in str(transport.calls)
    assert reservations(engine, org) == prior
    assert tenant_rows(engine, org) == before


@pytest.mark.postgres
def test_failed_output_not_cached_and_deterministic_route_never_reserves(documents_environment):
    engine, org, _, client, _ = documents_environment
    transport = enable_fake(client, [ProviderReply("{}"), ProviderReply("{}")])
    doc = upload(client, b"Invoice I-1 paid INR 1.00.").json()
    first = extract(client, doc["id"], allow_external=True).json()
    second = extract(client, doc["id"], allow_external=True, revision_label="retry").json()
    assert first["status"] == second["status"] == "FAILED"
    assert len(transport.calls) == 2 and len(reservations(engine, org)) == 2
    structured = upload(client, b"INVOICE: i").json()
    result = extract(client, structured["id"], allow_external=True).json()
    assert result["route"] == "DETERMINISTIC"
    assert len(transport.calls) == 2 and len(reservations(engine, org)) == 2


@pytest.mark.postgres
@pytest.mark.parametrize(
    "setting,value",
    [
        ("gemini_model", "different-unit-model"),
        ("llm_max_output_tokens", 1024),
        ("privacy_review_reference", "different-unit-review"),
    ],
)
def test_changed_semantic_identity_misses_cache(documents_environment, setting, value):
    engine, org, _, client, _ = documents_environment
    source = "Invoice I-1 paid INR 1.00."
    doc = upload(client, source.encode()).json()
    reply = ProviderReply(json.dumps(minimal_model_result(project([source]).pages[0])), 15, 20)
    transport = enable_fake(client, [reply, reply])
    first = extract(client, doc["id"], allow_external=True).json()
    assert first["error_code"] is None
    setattr(client.app.state.settings, setting, value)
    second = extract(client, doc["id"], allow_external=True, revision_label="changed").json()
    assert second["error_code"] is None and second["id"] != first["id"]
    assert len(transport.calls) == 2 and len(reservations(engine, org)) == 2


@pytest.mark.parametrize(
    "change,code",
    [
        ({"name": "models/other"}, "MODEL_NOT_AVAILABLE"),
        ({"supported_actions": []}, "MODEL_NOT_SUPPORTED"),
        ({"input_token_limit": None}, "MODEL_LIMITS_UNAVAILABLE"),
        ({"output_token_limit": 1}, "MODEL_OUTPUT_LIMIT"),
        ({"count": 8193}, "PROVIDER_INPUT_LIMIT"),
        ({"count": None}, "INVALID_TOKEN_COUNT"),
        ({"missing": True}, "PROVIDER_FAILED"),
    ],
)
def test_unavailable_or_unsuitable_model_abstains_without_generation(monkeypatch, change, code):
    from google import genai

    from clearledger import gemini_worker

    info = dict(
        name="models/unit-model",
        supported_actions=["generateContent"],
        input_token_limit=8192,
        output_token_limit=4096,
        version="unit",
    )
    info.update({k: v for k, v in change.items() if k in info})
    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, **kwargs):
            calls.append(kwargs["model"])
            if change.get("missing"):
                raise ValueError("private provider diagnostic")
            return SimpleNamespace(**info)

        def count_tokens(self, **kwargs):
            return SimpleNamespace(total_tokens=change.get("count", 100))

        def generate_content(self, **kwargs):
            pytest.fail("Preflight failure must not generate or escalate")

    output = io.StringIO()
    monkeypatch.setattr(genai, "Client", Client)
    monkeypatch.setattr(logging, "disable", lambda _: None)
    monkeypatch.setattr("clearledger.worker_security.install_guard", lambda **_: None)
    monkeypatch.setattr("clearledger.worker_security.posix_limits", lambda: None)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.TextIOWrapper(
            io.BytesIO(
                json.dumps(
                    {
                        "key": "unit-only",
                        "model": "unit-model",
                        "timeout_ms": 1000,
                        "pages": ["sanitized"],
                    }
                ).encode()
            )
        ),
    )
    monkeypatch.setattr(sys, "stdout", output)
    gemini_worker.main()
    assert json.loads(output.getvalue()) == {"error": code, "retryable": False}
    assert calls == ["unit-model"] and "private" not in output.getvalue()


def test_reservation_failure_never_calls_transport_and_releases_local_slot():
    transport = FakeTransport([ProviderReply("{}", 1, 1)])
    gateway = Gateway(transport)

    def fail():
        raise RuntimeError("secret database diagnostic")

    with pytest.raises(ExtractionError, match="PROVIDER_FAILED") as error:
        gateway.generate(["safe"], before_attempt=fail)
    assert transport.calls == [] and "secret" not in str(error.value.metrics)
    assert gateway.generate(["safe"])[0].json_text == "{}"


def test_each_retry_has_independent_reservation_and_unknown_total_cost():
    calls = []
    gateway = Gateway(
        FakeTransport([ProviderFailure("timeout", True), ProviderReply("{}", 1, 2)]),
        sleep=lambda _: None,
        input_rate=1,
        output_rate=1,
    )
    _, metrics = gateway.generate(["safe"], before_attempt=lambda: calls.append(1) or {"ok": True})
    assert len(calls) == len(metrics["budget_reservations"]) == 2
    assert metrics["estimated_cost_paise"] is None and metrics["usage_complete"] is False


def test_reported_usage_cannot_exceed_configured_caps():
    with pytest.raises(ExtractionError, match="PROVIDER_USAGE_EXCEEDS_RESERVATION"):
        Gateway(FakeTransport([ProviderReply("{}", 8193, 1)])).generate(["safe"])
