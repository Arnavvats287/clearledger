"""Opt-in, sequential actual-API latency probe. Excluded from normal test discovery."""

import json
import os
from collections import Counter
from functools import wraps
from pathlib import Path
from time import perf_counter_ns

import pytest
from pydantic import SecretStr
from sqlalchemy import event, text
from test_advanced_matching import advanced, prepare
from test_ai_usefulness import PROSE
from test_cases import correlate, pump
from test_documents import extract, get, upload
from test_evidence import SOURCE_SECRET, manifest, register
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_investigations import run, start
from test_matching import add_evidence, financial_state, match
from test_restart_persistence import tenant_rows

from clearledger import advanced_matching, document_api, documents, matching, remittance_parser
from clearledger.finance_models import (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    FinanceCommand,
    FinanceProposal,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)
from clearledger.grounded_extraction import catalog
from clearledger.investigation_broker import Broker
from clearledger.models import ProviderReservation

pytestmark = pytest.mark.postgres
CASES = ("clean_extraction", "exact_correlation", "supported", "missing", "conflict")
FINANCE = (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    FinanceCommand,
    FinanceProposal,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
    ProviderReservation,
)
REPEATS = int(os.environ.get("CLEARLEDGER_PERF_REPEATS", "20"))


class Timings:
    def __init__(self):
        self.samples = Counter()
        self.calls = Counter()
        self.statuses = Counter()

    def call(self, name, function, *args, **kwargs):
        started = perf_counter_ns()
        try:
            result = function(*args, **kwargs)
            if name == "http":
                self.statuses[result.status_code] += 1
            return result
        finally:
            self.calls[name] += 1
            self.samples[name] += perf_counter_ns() - started

    def watch(self, monkeypatch, owner, attribute, name):
        function = getattr(owner, attribute)

        @wraps(function)
        def measured(*args, **kwargs):
            return self.call(name, function, *args, **kwargs)

        monkeypatch.setattr(owner, attribute, measured)

    def observe_db(self, monkeypatch, engine):
        def before(conn, cursor, statement, parameters, context, executemany):
            context.latency_probe_started_ns = perf_counter_ns()

        def after(conn, cursor, statement, parameters, context, executemany):
            self.calls["db_statements"] += 1
            self.samples["db_statements"] += perf_counter_ns() - context.latency_probe_started_ns

        event.listen(engine, "before_cursor_execute", before)
        event.listen(engine, "after_cursor_execute", after)
        self.watch(monkeypatch, engine.dialect, "do_commit", "db_commit")
        return lambda: (
            event.remove(engine, "before_cursor_execute", before),
            event.remove(engine, "after_cursor_execute", after),
        )


def response_json(response):
    assert response.status_code == 200, response.status_code
    return response.json()


@pytest.mark.parametrize("mode", CASES)
@pytest.mark.parametrize("iteration", range(REPEATS + 1))
def test_product_latency(documents_environment, monkeypatch, mode, iteration):
    env = documents_environment
    engine, org, _, client, _ = env
    settings = client.app.state.settings
    assert not settings.external_ai_enabled and not settings.investigation_external_enabled
    assert settings.extraction_provider == "disabled"
    assert settings.investigation_provider == "deterministic"
    assert client.app.state.finance_identity_verifier is None
    investigation = mode in {"supported", "missing", "conflict"}
    if investigation:
        settings.evidence_trusted_sources_json = SecretStr(
            json.dumps(
                [
                    {
                        "organization_id": str(org),
                        "source_system": "test-origin",
                        "key_id": "test-key",
                        "secret": SOURCE_SECRET,
                        "allowed_kinds": ["PROMOTION"],
                    }
                ]
            )
        )
    receipt_id = prepare(client, amounts=(1101 if investigation else 1000,), cash=1000)
    baseline = financial_state(client)
    financial_rows = tenant_rows(engine, org, FINANCE)
    assert all(not rows for rows in financial_rows.values())
    with engine.connect() as connection:
        pg = connection.scalar(text("SHOW server_version"))
    receipt = baseline["/receipts"][0]
    invoice = baseline["/invoices"][0]
    raw = b"INVOICE: i\nUTR: t"
    if investigation:
        raw += b"\nCLAIM rebate: INR 1.01"

    timers = Timings()
    with monkeypatch.context() as patches:
        for owner, attribute, name in (
            (client, "send", "http"),
            (documents, "parse_bounded", "parser"),
            (remittance_parser, "validate_semantics", "extraction_validation"),
            (matching, "decide", "exact_decision"),
            (advanced_matching, "analyze", "allocation_candidates"),
            (document_api, "correlate", "correlation_service"),
            (Broker, "search", "evidence_retrieval"),
            (Broker, "verify", "evidence_validation"),
        ):
            timers.watch(patches, owner, attribute, name)
        stop_observers = [
            timers.observe_db(patches, observed)
            for observed in (engine, client.app.state.session_factory.kw["bind"])
        ]
        started = perf_counter_ns()
        try:
            document = response_json(timers.call("document_ingest_api", upload, client, raw))
            extraction = response_json(
                timers.call("extraction_api", extract, client, document["id"])
            )
            assert extraction["route"] == "DETERMINISTIC" and extraction["status"] == "SUCCEEDED"
            assert extraction["requires_human_review"] and not extraction["financial_authority"]
            assert extraction["result"]["invoice_references"][0]["value"] == "i"
            if mode != "clean_extraction":
                assert response_json(add_evidence(client, receipt_id))
                if investigation:
                    proposal = response_json(
                        timers.call("matching_api", advanced, client, receipt_id)
                    )
                    candidate = proposal["result"]["candidates"][0]
                    assert proposal["outcome"] == "UNIQUE" and proposal["result"]["intent_verified"]
                    assert candidate["allocations"][0]["remaining_ar_paise"] == 101
                    assert extraction["result"]["claims"][0]["amount_paise"] == 101
                else:
                    proposal = response_json(timers.call("matching_api", match, client, receipt_id))
                    assert proposal["outcome"] == "EXACT_MATCH" and proposal["amount_paise"] == 1000
                association = response_json(
                    timers.call("correlation_api", correlate, client, document, extraction, receipt)
                )
                assert association["status"] == "LINKED"
                timers.call("outbox_drain", pump, env)
                cases = response_json(get(client, "/cases"))
                assert len(cases) == 1
                case = cases[0]
                assert invoice["id"] in case["invoice_ids"] and receipt_id in case["receipt_ids"]
                assert document["id"] in case["document_ids"]
                assert not case["financial_authority"] and case["verified_settled_paise"] == 0
            outcome = "SUCCEEDED"
            action = None
            if mode == "exact_correlation":
                outcome = "EXACT_MATCH / LINKED"
            if investigation:
                claim = response_json(get(client, f"/cases/{case['id']}/claims"))[0]
                # The existing source fixture uploads, signs and scopes its own synthetic document.
                for value in {"supported": (101,), "missing": (), "conflict": (101, 100)}[mode]:
                    assert response_json(
                        register(
                            env,
                            manifest(
                                env,
                                kind="PROMOTION",
                                category="rebate",
                                value=value,
                            ),
                        )
                    )["source_authenticated"]
                timers.call("outbox_drain", pump, env)
                queued = response_json(
                    timers.call("investigation_enqueue", start, env, case, claim)
                )
                identifier = queued["id"]
                assert timers.call("investigation_worker", run, env, identifier) == "DELIVERED"
                finding = response_json(get(client, f"/investigations/{identifier}/findings"))[0]
                assert finding["is_current"] and finding["requires_human_review"]
                assert not finding["financial_authority"]
                outcome, action = finding["state"], finding["next_action"]
                expected = (
                    ("SUPPORTED", "HUMAN_REVIEW")
                    if mode == "supported"
                    else ("INSUFFICIENT_EVIDENCE", "REQUEST_EVIDENCE")
                )
                assert (outcome, action) == expected, (outcome, action)
                if mode == "conflict":
                    assert "CONFLICTING_EVIDENCE" in finding["unknowns"]
                if mode == "missing":
                    assert "MISSING_EVIDENCE" in finding["unknowns"]
            timers.samples["end_to_end"] = perf_counter_ns() - started
        finally:
            for stop in stop_observers:
                stop()
    # In-process source candidate discovery is independently measured, outside API wall time.
    candidates = timers.call("invoice_span_candidates", catalog, [PROSE])
    assert any(row.value == "I-1" for row in candidates.items)
    assert timers.statuses and set(timers.statuses) == {200}
    assert timers.calls["parser"] and timers.calls["extraction_validation"]
    assert timers.calls["db_statements"] and timers.calls["db_commit"]
    if mode == "exact_correlation":
        assert timers.calls["exact_decision"] and timers.calls["correlation_service"]
    if investigation:
        assert timers.calls["allocation_candidates"]
        assert timers.calls["evidence_retrieval"] and timers.calls["evidence_validation"]
    assert financial_state(client) == baseline
    assert tenant_rows(engine, org, FINANCE) == financial_rows
    path = Path(os.environ["CLEARLEDGER_PERF_OUTPUT"])
    with path.open("a", encoding="utf-8") as output:
        print(
            json.dumps(
                {
                    "case": mode,
                    "iteration": iteration,
                    "postgres": pg,
                    "elapsed_ns": dict(timers.samples),
                    "calls": dict(timers.calls),
                    "http_statuses": dict(timers.statuses),
                    "outcome": outcome,
                    "next_action": action,
                    "financial_nonmutation": True,
                    "external_ai_calls": 0,
                }
            ),
            file=output,
        )
