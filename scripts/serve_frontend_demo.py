"""Loopback-only UI acceptance host. Minimal existing test fixtures; zero Gemini calls.

Fresh generated disposable PostgreSQL only. No production adapter/finance permissions.
Source facts pass real import/document/evidence/correlation APIs and immutable history.
The phased Investigator is explicitly ScriptedAR/fake, never labelled as live Gemini.
"""

import json
import logging
import secrets
import sys
import threading
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_REVIEW_REFERENCE = "offline-approved-synthetic-ui-control"
sys.path.insert(0, str(ROOT / "tests"))

from application_eval_host import initialize  # noqa: E402
from pilot_runtime import disposable_database, fingerprint, rows  # noqa: E402
from test_ai_investigator import ScriptedAR  # noqa: E402
from test_evidence import SOURCE_SECRET, sign  # noqa: E402
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, post  # noqa: E402

from clearledger.case_models import DomainEvent, OutboxEvent  # noqa: E402
from clearledger.case_outbox import claim_one, deliver  # noqa: E402
from clearledger.config import Settings  # noqa: E402
from clearledger.extraction_provider import FakeTransport, Gateway, ProviderReply  # noqa: E402
from clearledger.investigation_graph import execute  # noqa: E402
from clearledger.investigation_models import Investigation  # noqa: E402
from clearledger.investigation_runtime import Runtime  # noqa: E402
from clearledger.main import create_app  # noqa: E402
from clearledger.review_users import provision  # noqa: E402


def pump(engine, org, settings):
    """Existing worker entry points; fake injection exists only in this synthetic host."""
    before = fingerprint(rows(engine))
    for _ in range(100):
        lease = claim_one(engine, org, settings)
        if lease is None:
            break
        with Session(engine) as session:
            row = session.get(OutboxEvent, lease[0])
            event = session.get(DomainEvent, row.event_id)
            run = (
                session.get(Investigation, UUID(event.payload["run_id"]))
                if event.event_type == "investigation.requested"
                else None
            )
        if run is not None:
            outcome = execute(
                Runtime(engine, org, run.id, *lease, settings),
                ScriptedAR() if run.provider == "fake" else None,
            )
        else:
            outcome = deliver(engine, org, *lease, settings)
        if outcome != "DELIVERED":
            raise RuntimeError("SYNTHETIC_OUTBOX_FAILED")
    if fingerprint(rows(engine)) != before:
        raise RuntimeError("FINANCIAL_NONMUTATION_FAILED")


def populate(client, engine, org, settings, output):
    key = settings.document_api_token.get_secret_value()

    def headers():
        return {
            "Authorization": "Bearer " + key,
            "X-Actor-ID": "synthetic-source",
            "Idempotency-Key": str(uuid4()),
        }

    def upload(name, raw):
        response = client.post(
            "/documents",
            content=raw.encode(),
            headers={
                **headers(),
                "Content-Type": "text/plain",
                "X-Source-Filename": name,
                "X-Synthetic-Data": "true",
            },
        )
        assert response.status_code == 200, response.status_code
        return response.json()

    assert (
        post(client, "customers", {**CUSTOMER, "name": "Meridian Retail Pvt Ltd"}).status_code
        == 200
    )
    assert (
        post(client, "payer-aliases", {**ALIAS, "alias": "Meridian Retail Demo"}).status_code == 200
    )
    customer = client.get("/customers").json()[0]
    fixtures = []
    for index, mode in enumerate(("missing", "supported", "conflict", "confirm", "reject"), 1):
        number, utr = f"INV-2026-{1041 + index}", f"DEMO-UTR-{index:04}"
        assert (
            post(
                client,
                "invoices",
                {
                    **INVOICE,
                    "invoice_number": number,
                    "original_amount_paise": "5000000",
                    "open_amount_paise": "5000000",
                },
            ).status_code
            == 200
        )
        assert (
            post(
                client,
                "bank-transactions",
                {
                    **BANK,
                    "external_transaction_id": utr,
                    "amount_paise": "4700000",
                    "payer_name": "Meridian Retail Demo",
                },
            ).status_code
            == 200
        )
        invoice = next(i for i in client.get("/invoices").json() if i["invoice_number"] == number)
        raw = (
            f"CUSTOMER: c\nINVOICE: {number}\nUTR: {utr}\n"
            "AMOUNT: 300000 paise\nCLAIM damage: INR 3000.00"
        )
        document = upload(f"{number}-customer-remittance.txt", raw)

        def pointer(quote, raw=raw):
            start = raw.index(quote)
            return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

        # Existing offline transport control only. Never a live Gemini output or authority.
        result = {
            "invoice_references": [{"value": number, "span": pointer(number)}],
            "utr_references": [{"value": utr, "span": pointer(utr)}],
            "payer_hint": None,
            "claims": [
                {
                    "category": "damage",
                    "description": pointer("damage: INR 3000.00"),
                    "amount_paise": 300000,
                    "amount_span": pointer("INR 3000.00"),
                    "reason_code": None,
                }
            ],
            "uncertainty": "none",
            "unparsed_fields": [],
        }
        settings.extraction_provider = "fake"
        settings.external_ai_enabled = True
        settings.privacy_review_reference = SYNTHETIC_REVIEW_REFERENCE
        client.app.state.extraction_gateway = Gateway(
            FakeTransport([ProviderReply(json.dumps(result), 100, 100, 200)]), attempts=1
        )
        extracted = client.post(
            f"/documents/{document['id']}/extract",
            json={"expected_document_version": document["version"], "allow_external": True},
            headers=headers(),
        )
        settings.external_ai_enabled = False
        settings.extraction_provider = "disabled"
        client.app.state.extraction_gateway = None
        assert (
            extracted.status_code == 200
            and extracted.json()["result"]["claims"][0]["amount_paise"] == 300000
        )

        def source(kind, source_raw, doc, facts, mode=mode, invoice=invoice, number=number):
            def span(label):
                start = source_raw.index(label + ": ") + len(label) + 2
                end = source_raw.find("\n", start)
                end = len(source_raw) if end < 0 else end
                return {"page": 1, "start": start, "end": end, "quote": source_raw[start:end]}

            body = {
                "source_system": "test-origin",
                "source_record_id": f"unit-{mode}-{kind}-{uuid4().hex[:8]}",
                "revision": 1,
                "customer_id": customer["id"],
                "invoice_id": invoice["id"],
                "document_id": doc["id"],
                "document_version": doc["version"],
                "raw_sha256": doc["content_sha256"],
                "canonical_sha256": doc["canonical_sha256"],
                "excerpt": {"page": 1, "start": 0, "end": len(source_raw), "quote": source_raw},
                "customer_reference": {"value": "c", "span": span("CUSTOMER")},
                "invoice_reference": {"value": number, "span": span("INVOICE")},
                "categories": ["damage"],
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "occurred_at": "2026-01-01T00:00:00Z",
                "recorded_at": "2026-01-02T00:00:00Z",
                "signed_at": "2026-01-01T00:00:00Z",
                "approved_at": "2026-01-01T00:00:00Z",
                "date_basis": "INVOICE_ISSUED",
                "fact": {"type": kind},
            }
            for field, (label, value) in facts.items():
                body["fact"][field] = {"value": value, "span": span(label)}
            if kind in {"WMS", "POD"}:
                body["fact"]["unit"] = "EACH"
            signed = sign((engine, org, None, client, client), body)
            response = client.post("/evidence/records", json=signed, headers=headers())
            assert response.status_code == 200, response.status_code

        source("REMITTANCE", raw, document, {"amount": ("AMOUNT", 300000)})
        if mode in {"supported", "conflict"}:
            for kind, count in [("WMS", 1), ("POD", 1)] + (
                [("WMS", 2)] if mode == "conflict" else []
            ):
                source_raw = (
                    f"CUSTOMER: c\nINVOICE: {number}\nSHIPMENT: s\nSHIPPED: {count}\n"
                    f"DELIVERED: {count}\nDAMAGED: {count}\nUNIT_VALUE: 300000 paise"
                )
                doc = upload(f"{number}-{kind}-delivery-{count}.txt", source_raw)
                source(
                    kind,
                    source_raw,
                    doc,
                    {
                        "shipment": ("SHIPMENT", "s"),
                        "shipped": ("SHIPPED", count),
                        "delivered": ("DELIVERED", count),
                        "damaged": ("DAMAGED", count),
                        "unit_value": ("UNIT_VALUE", 300000),
                    },
                )
        fixtures.append({"mode": mode, "document_id": document["id"], "invoice_id": invoice["id"]})
    pump(engine, org, settings)
    password = secrets.token_urlsafe(24)
    with Session(engine) as session:
        for username, role in (
            ("controller", "CONTROLLER"),
            ("analyst", "AR_ANALYST"),
            ("auditor", "AUDITOR"),
        ):
            provision(session, org, username, role, password)
    settings.review_demo_enabled = settings.review_access_enabled = True
    result = client.post(
        "/review/demo/login", json={"username": "controller", "password": password}
    )
    assert result.status_code == 200
    client.headers["Authorization"] = "ReviewDemo " + result.json()["access_token"]
    for f in fixtures:
        cases = client.get("/cases").json()
        case = next(c for c in cases if f["document_id"] in c["document_ids"])
        task = client.get(f"/review/cases/{case['id']}/correlation-tasks").json()[0]
        assert task["reason"] == "READY_FOR_REVIEW", task["reason"]
        if f["mode"] in {"missing", "supported", "conflict"}:
            response = client.post(
                f"/review/correlation-tasks/{task['id']}/decision",
                headers={"Idempotency-Key": str(uuid4())},
                json={
                    "expected_case_version": case["version"],
                    "expected_context_sha256": case["context_sha256"],
                    "expected_task_sha256": task["input_sha256"],
                    "decision": "CONFIRM",
                },
            )
            assert response.status_code == 200, response.status_code
            pump(engine, org, settings)
            case = client.get(f"/cases/{case['id']}").json()
            claims = client.get(f"/cases/{case['id']}/claims").json()
            started = client.post(
                f"/cases/{case['id']}/investigations",
                headers={"Idempotency-Key": str(uuid4()), "X-Actor-ID": "workstation"},
                json={
                    "expected_case_version": case["version"],
                    "expected_context_sha256": case["context_sha256"],
                    "claim_ids": [c["id"] for c in claims],
                    "allow_external": False,
                },
            )
            assert started.status_code == 200
            pump(engine, org, settings)
        f["case_id"] = case["id"]
        f["task_id"] = task["id"]
    access = {
        "url": "http://127.0.0.1:5173",
        "username": "controller",
        "password": password,
        "fixtures": fixtures,
        "provider": "fake",
        "external_ai_enabled": False,
        "database_disposable": True,
    }
    (output / "access.json").write_text(json.dumps(access, indent=2), encoding="utf8")


def main():
    logging.disable(logging.CRITICAL)
    values = dotenv_values(ROOT / ".env")
    admin = values.get("TEST_DATABASE_URL")
    if not admin:
        raise SystemExit("Configure ignored TEST_DATABASE_URL; development DB is never used")
    output = ROOT / "local-data/frontend"
    output.mkdir(parents=True, exist_ok=True)
    with disposable_database(admin) as url:
        engine, org, _ = initialize(url)
        settings = Settings(
            _env_file=None,
            database_url=url,
            organization_id=org,
            document_root=output / uuid4().hex,
            document_api_token=SecretStr(secrets.token_urlsafe(40)),
            case_auto_correlate_extractions=True,
            case_auto_investigate_extractions=True,
            evidence_trusted_sources_json=SecretStr(
                json.dumps(
                    [
                        {
                            "organization_id": str(org),
                            "source_system": "test-origin",
                            "key_id": "test-key",
                            "secret": SOURCE_SECRET,
                            "allowed_kinds": ["REMITTANCE", "WMS", "POD"],
                        }
                    ]
                )
            ),
        )
        app = create_app(settings)
        app.state.investigation_provider = ScriptedAR()
        with TestClient(app) as client:
            populate(client, engine, org, settings, output)
        stop_path = output / ("stop-" + uuid4().hex)
        access_path = output / "access.json"
        access = json.loads(access_path.read_text(encoding="utf8"))
        access["stop_file"] = str(stop_path)
        access_path.write_text(json.dumps(access, indent=2), encoding="utf8")
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=8010, log_level="critical", access_log=False)
        )
        stopped = threading.Event()

        def work():
            while not stopped.wait(1):
                if stop_path.exists():
                    server.should_exit = True
                    return
                try:
                    pump(engine, org, settings)
                except Exception:
                    (output / "worker-failure.txt").write_text(
                        "SYNTHETIC_WORKER_FAILED", encoding="utf8"
                    )
                    return

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        print(
            "Synthetic UI API ready on127.0.0.1:8010; "
            "access details in local-data/frontend/access.json",
            flush=True,
        )
        print(
            "Offline model control only. No Gemini or financial authority. "
            "Ctrl+C cleans owned disposable DB.",
            flush=True,
        )
        try:
            server.run()
        finally:
            stopped.set()
            thread.join(timeout=20)
            engine.dispose()
    print("Owned disposable UI database removed.", flush=True)


if __name__ == "__main__":
    main()
