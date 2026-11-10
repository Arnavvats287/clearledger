"""Public deployment checks against disposable PostgreSQL and the actual application."""

import sys
from pathlib import Path

import certifi
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from clearledger.case_models import Case, Claim
from clearledger.db import build_engine
from clearledger.investigation_runtime import Runtime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from portfolio_sessions import Sessions, setup  # noqa: E402
from serve_frontend_demo import fingerprint, rows  # noqa: E402
from serve_portfolio import Loopback, bootstrap, make_gateway, neon_url, public_origin  # noqa: E402

ORIGIN = "https://clearledger.onrender.com"


def test_neon_tls_and_exact_origin():
    test_url = (
        "postgresql://test:test@ep-example.ap-southeast-1.aws.neon.tech/"
        "clearledger_portfolio?sslmode=require"
    )
    url = make_url(neon_url(test_url))
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "verify-full"
    assert url.query["sslrootcert"] == certifi.where()
    for invalid in (
        test_url.replace("require", "disable"),
        test_url.replace("ep-example.", "ep-example-pooler."),
        test_url.replace("clearledger_portfolio", "other"),
        test_url.replace("aws.neon.tech", "example.com"),
    ):
        with pytest.raises(ValueError):
            neon_url(invalid)
    assert public_origin(ORIGIN) == ORIGIN
    for invalid in ("http://clearledger.onrender.com", ORIGIN + "/", ORIGIN + "@example.com"):
        with pytest.raises(ValueError):
            public_origin(invalid)


@pytest.mark.postgres
def test_real_public_read_boundary_and_ephemeral_restart(
    disposable_database, tmp_path, monkeypatch
):
    url = disposable_database.render_as_string(hide_password=False)
    engine = build_engine(url)
    try:
        first, second = tmp_path / "first", tmp_path / "second"
        first.mkdir()
        second.mkdir()
        begin = Runtime.begin

        def start_with_short_fake_deadline(runtime):
            if runtime.snapshot["provider"] == "fake":
                runtime.limits = runtime.limits.model_copy(update={"timeout_ms": 100})
            begin(runtime)

        with monkeypatch.context() as seed:
            seed.setattr(Runtime, "begin", start_with_short_fake_deadline)
            settings, password = bootstrap(url, first)
        before = fingerprint(rows(engine))
        setup(engine, url)
        sessions = Sessions(engine)
        with TestClient(make_gateway(Loopback(settings, password), ORIGIN, sessions)) as client:
            assert client.get("/ready").status_code == 200
            assert client.get("/portfolio/bootstrap").status_code == 401
            token = client.post("/portfolio/session", headers={"Origin": ORIGIN}).json()[
                "access_token"
            ]
            auth = {"Authorization": f"Portfolio {token}"}
            snapshot_response = client.get("/portfolio/bootstrap", headers=auth)
            assert snapshot_response.status_code == 200
            assert snapshot_response.headers["Cache-Control"] == "no-store"
            snapshot = snapshot_response.json()
            assert all("pages" not in item for item in snapshot["documents"])
            assert snapshot["invoices"] and snapshot["receipts"] and snapshot["banks"]
            task_id = next(task["id"] for case in snapshot["cases"] for task in case["tasks"])
            assert (
                client.post(
                    f"/review/correlation-tasks/{task_id}/decision", headers=auth, json={}
                ).status_code
                == 404
            )
            assert all(
                "pages" not in item["case"]
                and all(
                    trace["node"] in {"investigator_synthesize", "human_review_or_request_evidence"}
                    for trace in item["trace"]
                )
                for item in snapshot["cases"]
            )
            response = client.get("/review/me", headers={"Origin": ORIGIN})
            assert response.headers["Access-Control-Allow-Origin"] == ORIGIN
            assert response.json()["role"] == "AUDITOR"
            assert response.json()["financial_authority"] is False
            assert "access_token" not in response.json()
            assert (
                "access-control-allow-origin"
                not in client.get(
                    "/review/me", headers={"Origin": "https://unapproved.example"}
                ).headers
            )
            cases = client.get("/cases").json()
            document = next(c["document_ids"][0] for c in cases if c["document_ids"])
            original = client.get(f"/documents/{document}/original")
            assert original.status_code == 200
            assert (
                client.post(
                    f"/documents/{document}/verify-span",
                    json={"page": 1, "start": 0, "end": 8, "quote": "CUSTOMER"},
                ).json()["source_consistent"]
                is True
            )
            assert (
                client.post(
                    f"/documents/{document}/verify-span",
                    json={"page": 1, "start": 0, "end": 8, "quote": "forged!!"},
                ).status_code
                == 422
            )
            for method, path in (
                ("POST", "/review/demo/login"),
                ("GET", "/review/demo/users"),
                ("POST", "/finance/journals"),
                ("POST", "/invoices"),
                ("GET", "/openapi.json"),
                ("POST", f"/documents/{document}/extract"),
            ):
                assert client.request(method, path).status_code == 404
            tasks = client.get(f"/review/cases/{cases[0]['id']}/correlation-tasks")
            assert tasks.status_code == 200
            states = {
                f["state"]
                for case in cases
                for run in client.get(f"/cases/{case['id']}/investigations").json()
                if not run["is_stale"]
                for f in client.get(f"/investigations/{run['id']}/findings").json()
            }
            assert "INSUFFICIENT_EVIDENCE" in states
            supported_invoice = next(
                row["id"]
                for row in client.get("/invoices").json()
                if row["invoice_number"] == "INV-2026-1043"
            )
            supported_case = next(
                case["id"] for case in cases if supported_invoice in case["invoice_ids"]
            )
            run = client.get(f"/cases/{supported_case}/investigations").json()[0]
            assert run["error_code"] == "TIMEOUT"
            timed_out = run["id"]
        restored, password = bootstrap(url, second, refresh_timeouts=True)
        assert restored.organization_id == settings.organization_id
        case_before = fingerprint(rows(engine, (Case, Claim)))
        with TestClient(make_gateway(Loopback(restored, password), ORIGIN, sessions)) as client:
            token = client.post("/portfolio/session", headers={"Origin": ORIGIN}).json()[
                "access_token"
            ]
            auth = {"Authorization": f"Portfolio {token}"}
            view = client.get(f"/portfolio/cases/{supported_case}", headers=auth)
            assert view.status_code == 200
            data = view.json()
            assert data["b"]["case"]["id"] == supported_case
            assert any(item["is_current"] for item in data["b"]["findings"])
            assert data["b"]["trace"] and data["sources"]
            assert all("pages" not in item for item in data["docs"])
            for route in (
                f"/cases/{supported_case}/draft-evidence-request",
                f"/cases/{supported_case}/review-comments",
                f"/cases/{supported_case}/request-evidence",
                f"/portfolio/cases/{supported_case}",
            ):
                assert client.post(route, headers=auth, json={}).status_code == 404
            assert client.get(f"/documents/{document}/original").content == original.content
            runs = client.get(f"/cases/{supported_case}/investigations").json()
            assert runs[0]["status"] == "COMPLETED"
            assert runs[0]["is_stale"] is False
            findings = client.get(f"/investigations/{runs[0]['id']}/findings").json()
            assert any(row["state"] == "SUPPORTED" and row["is_current"] for row in findings)
            assert any(row["id"] == timed_out and row["error_code"] == "TIMEOUT" for row in runs)
        assert fingerprint(rows(engine)) == before
        assert fingerprint(rows(engine, (Case, Claim))) == case_before
    finally:
        engine.dispose()
