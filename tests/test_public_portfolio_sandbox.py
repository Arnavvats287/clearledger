"""Public gateway checks with real PostgreSQL and the isolated parser."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from clearledger.db import build_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import portfolio_sandbox as sandbox  # noqa: E402
from portfolio_sessions import Sessions, setup  # noqa: E402
from serve_portfolio import make_gateway  # noqa: E402

ORIGIN = "https://clearledger-jduu.onrender.com"
FIXTURE = b"INVOICE: INV-2026-1042\nUTR: DEMO-UTR-0001\nCLAIM damage: INR 3000.00\n"
MOCK_KEY = "visitor-placeholder-for-isolated-tests"


@pytest.fixture
def gateway(disposable_database, migration_config):
    from contextlib import asynccontextmanager

    class StubReads:
        @asynccontextmanager
        async def serve(self):
            yield

    url = disposable_database.render_as_string(hide_password=False)
    engine = build_engine(url)
    try:
        with engine.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.upgrade(migration_config, "head")
        setup(engine, url)
        setup(engine, url)
        with TestClient(
            make_gateway(StubReads(), ORIGIN, Sessions(engine), "synthetic-provider")
        ) as client:
            yield client, engine
    finally:
        engine.dispose()


def login(client):
    reply = client.post("/portfolio/session", headers={"Origin": ORIGIN})
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store"
    return {"Origin": ORIGIN, "Authorization": f"Portfolio {reply.json()['access_token']}"}


def upload(client, headers, content=FIXTURE, **overrides):
    return client.post(
        "/portfolio/extract",
        content=content,
        headers={
            **headers,
            "Content-Type": "text/plain",
            "X-Portfolio-Consent": "true",
            "X-Portfolio-Filename": "..%2Fwindows%5Csample.txt",
            **overrides,
        },
    )


@pytest.mark.postgres
def test_public_entry_logout_and_upload_isolation(gateway):
    client, engine = gateway
    assert client.post("/portfolio/session").status_code == 403
    headers = login(client)
    user = client.get("/portfolio/session", headers=headers).json()
    assert user["role"] == "AUDITOR" and user["financial_authority"] is False
    assert upload(client, headers, **{"X-Portfolio-Consent": "false"}).status_code == 422
    assert upload(client, headers, **{"Content-Type": "application/zip"}).status_code == 415
    assert upload(client, headers, b"x" * (sandbox.MAX_DOCUMENT_BYTES + 1)).status_code == 413
    assert upload(client, headers, b"PK\x03\x04archive").status_code == 422
    assert (
        upload(client, headers, b"unrecognized prose").json()["deterministic_status"] == "ABSTAINED"
    )
    result = upload(client, headers)
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["filename"] == "sample.txt"
    assert result.json()["financial_authority"] is False
    reference = result.json()["extraction"]["invoice_references"][0]
    span = reference["span"]
    assert result.json()["pages"][0][span["start"] : span["end"]] == reference["value"]
    assert result.json()["extraction"]["claims"][0]["amount_paise"] == 300000
    for path in ("/imports/invoices", "/finance/journals", "/documents", "/review/demo/login"):
        assert client.post(path, headers=headers, json={}).status_code == 404
    assert client.get("/finance/journals", headers=headers).status_code == 404
    with engine.connect() as db:
        schema = (
            db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='portfolio_demo'"
                )
            )
            .scalars()
            .all()
        )
        assert set(schema) == {
            "token_hash",
            "expires_at",
            "day",
            "sessions",
            "uploads",
            "included",
            "byok",
        }
        rows = (
            db.execute(text("SELECT to_jsonb(s)::text FROM portfolio_demo.sessions s"))
            .scalars()
            .all()
        )
        assert all("INV-2026-1042" not in row and "sample.txt" not in row for row in rows)
    assert client.delete("/portfolio/session", headers=headers).status_code == 200
    assert client.get("/portfolio/session", headers=headers).status_code == 401
    assert upload(client, headers).status_code == 401


def synthetic_reply(packet, alias):
    record = packet["record_ids"][0]
    return json.dumps(
        {
            "plan": None,
            "synthesis": {
                "evidence_span_ids": [alias],
                "amount_paise": 300000,
                "state": "INSUFFICIENT_EVIDENCE",
                "next_action": "REQUEST_EVIDENCE",
                "record_ids": [record],
                "observations": [],
                "missing_evidence_types": ["POD"],
                "rationale": "Required authenticated evidence is missing or incomplete.",
                "confidence": "LOW",
                "uncertainty": "MISSING_EVIDENCE",
                "financial_authority": False,
            },
        }
    )


@pytest.mark.postgres
def test_included_fixed_fixture_and_durable_quotas(gateway, monkeypatch):
    client, engine = gateway
    calls = []

    class Provider:
        def generate(self, pages):
            packet = json.loads(pages[0])
            calls.append(packet)
            alias = packet["evidence_spans"][0]["span_id"]
            return SimpleNamespace(json_text=synthetic_reply(packet, alias))

    monkeypatch.setattr(sandbox, "transport", lambda *_: Provider())
    headers = login(client)
    endpoint = "/portfolio/included"
    assert client.post(endpoint, headers=headers, json={"prompt": "user text"}).status_code == 413
    assert not calls
    result = client.post(endpoint, headers=headers).json()
    assert result["status"] == "SOURCE_CHECKED"
    assert result["citations"] == result["offered"]
    assert result["next_action"] == "REQUEST_EVIDENCE"
    assert result["financial_authority"] is False
    assert calls[0]["phase"] == "investigator_synthesize"
    assert "user text" not in json.dumps(calls)
    assert client.post(endpoint, headers=headers).json()["detail"] == "DEMO_INCLUDED_SESSION_LIMIT"
    with engine.begin() as db:
        db.execute(text("UPDATE portfolio_demo.daily SET included=20"))
    assert (
        client.post(endpoint, headers=login(client)).json()["detail"] == "DEMO_INCLUDED_DAILY_LIMIT"
    )
    assert len(calls) == 1


@pytest.mark.postgres
def test_byok_request_only_and_failed_validation(gateway, monkeypatch, caplog):
    client, engine = gateway
    headers = login(client)
    seen = []

    class Provider:
        def generate_for_source(self, pages, context):
            seen.append((pages, context))
            if len(seen) == 2:
                raise RuntimeError(MOCK_KEY)
            candidate = "FORGED" if len(seen) == 1 else "INV-2026-1042"
            return SimpleNamespace(
                json_text=json.dumps(
                    {
                        "invoice_references": [
                            {
                                "value": candidate,
                                "span": {
                                    "page": 1,
                                    "start": 9,
                                    "end": 9 + len(candidate),
                                    "quote": candidate,
                                },
                            }
                        ],
                        "utr_references": [],
                        "payer_hint": None,
                        "claims": [],
                        "uncertainty": "none",
                        "unparsed_fields": [],
                    }
                )
            )

    def provider(key, task):
        assert key == MOCK_KEY and task == "remittance_grounded"
        return Provider()

    monkeypatch.setattr(sandbox, "transport", provider)
    auth = {"X-Portfolio-Gemini-Key": MOCK_KEY, "X-Portfolio-Gemini-Consent": "true"}
    assert (
        upload(client, headers, **{**auth, "X-Portfolio-Gemini-Consent": "false"}).status_code
        == 422
    )
    assert (
        upload(client, headers, b"CONTACT: test@example.test", **auth).json()["ai"]["status"]
        == "BLOCKED"
    )
    assert not seen
    result = upload(client, headers, **auth)
    assert result.json()["ai"]["status"] == "REJECTED"
    assert result.json()["ai"]["validated"] is None
    assert result.json()["deterministic_status"] == "SOURCE_CHECKED"
    assert result.headers["cache-control"] == "no-store"
    failed = upload(client, headers, **auth)
    assert failed.status_code == 503
    accepted = upload(client, headers, **auth)
    assert accepted.json()["ai"]["status"] == "SOURCE_CHECKED"
    assert accepted.json()["ai"]["validated"]["invoice_references"][0]["value"] == "INV-2026-1042"
    assert upload(client, headers, **auth).json()["detail"] == "DEMO_BYOK_SESSION_LIMIT"
    assert len(seen) == 3
    assert MOCK_KEY not in result.text + failed.text + accepted.text + caplog.text
    with engine.connect() as db:
        state = (
            db.execute(text("SELECT to_jsonb(s)::text FROM portfolio_demo.sessions s"))
            .scalars()
            .all()
        )
        assert all(MOCK_KEY not in row for row in state)
        assert db.scalar(text("SELECT count(*) FROM investigation_traces")) == 0
