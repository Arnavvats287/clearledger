"""Synthetic application-owned evidence/observation workloads; no benchmark inputs."""

import base64
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.orm import Session
from test_chronological_evaluation import message
from test_chronological_evaluation import owner_url as owner_url
from test_imports import INVOICE, csv_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chronological_adapter as adapter_module  # noqa: E402
from application_eval_host import rows  # noqa: E402
from application_eval_inputs import sha  # noqa: E402
from chronological_adapter import Adapter  # noqa: E402
from chronological_diagnostics import ObservationFailure, diagnostic  # noqa: E402
from chronological_protocol import Stage  # noqa: E402

from clearledger.review_users import provision  # noqa: E402


@pytest.mark.postgres
def test_fragmented_imports_exceed_readonly_source_budget_not_authorization(owner_url, tmp_path):
    a = Adapter(owner_url, tmp_path / "private")
    try:
        initial = message()
        assert a.stage(Stage(initial))["status"] == "ABSTAIN"
        for number in range(9):
            result = a.api.request(
                "POST",
                "/imports/invoices",
                content=csv_bytes("invoices", {**INVOICE, "invoice_number": "unit-" + str(number)}),
                headers={
                    "Content-Type": "text/csv",
                    "X-Data-Contract-Version": "1.0",
                    "X-Source-Filename": "unit.csv",
                },
            )
            assert result.status_code == 200
        case = a.api.collection("/review/cases")[0]
        refreshed = a.api.request(
            "POST", f"/cases/{case['id']}/refresh", json={"expected_case_version": case["version"]}
        )
        assert refreshed.status_code == 200
        case = a.api.get(f"/review/cases/{case['id']}")
        before = rows(a.engine)
        original_token = a.api.token
        a.api.token = "invalid-unit-session-token-" + "0" * 32
        a.api.logged_at = time.monotonic()
        denied = a.api.request(
            "POST",
            f"/cases/{case['id']}/evidence/search",
            json={
                "expected_case_version": case["version"],
                "expected_context_sha256": case["context_sha256"],
                "customer_id": case["customer_id"],
                "tool": "get_invoice_evidence",
                "limit": 50,
            },
        )
        assert denied.status_code == 401 and denied.json()["detail"] == "DEMO_SESSION_INVALID"
        a.api.token = original_token
        result = a.api.request(
            "POST",
            f"/cases/{case['id']}/evidence/search",
            json={
                "expected_case_version": case["version"],
                "expected_context_sha256": case["context_sha256"],
                "customer_id": case["customer_id"],
                "tool": "get_invoice_evidence",
                "limit": 50,
            },
        )
        assert result.status_code == 409
        assert result.json() == {"detail": "EVIDENCE_FINANCIAL_SOURCE_BUDGET"}
        cases, evidence, investigations = a.case_observations(a.api.collection("/receipts"), {})
        assert len(cases) == 1 and not investigations
        assert evidence[0]["outcome"] == "REVIEW_REQUIRED"
        assert evidence[0]["reason"] == "EVIDENCE_FINANCIAL_SOURCE_BUDGET"
        assert evidence[0]["search_complete"] is False and evidence[0]["http_status"] == 409
        assert "items" not in evidence[0]  # A denied search is never an empty successful search.
        assert rows(a.engine) == before
        later = message(run=initial["run_id"], cutoff="2026-01-20T12:00:00+05:30")
        cumulative = csv_bytes(
            "invoices", INVOICE, *[{**INVOICE, "invoice_number": f"unit-{n}"} for n in range(9)]
        )
        later["payload"]["imports/invoices.csv"] = base64.b64encode(cumulative).decode()
        later["manifest"]["imports/invoices.csv"] = sha(cumulative)
        later["files"] = ["imports/invoices.csv"]
        stage = a.stage(Stage(later))
        assert stage["status"] == "ABSTAIN" and not a.poisoned
        assert stage["financial_mutation_check"] == "PASS"
        assert stage["prediction"]["abstain_invoice_allocation"]
        assert not stage["prediction"]["cash_allocations"]
        assert stage["api_observations"]["evidence_outcomes"] == [
            {
                "status": 409,
                "outcome": "REVIEW_REQUIRED",
                "reason": "EVIDENCE_FINANCIAL_SOURCE_BUDGET",
                "search_complete": False,
            }
        ]
        assert stage["api_observations"]["investigation_requests"] == 0
        assert rows(a.engine) == before
    finally:
        a.close()


@pytest.mark.postgres
def test_read_authorization_missing_evidence_and_paginated_large_workload(owner_url, tmp_path):
    a = Adapter(owner_url, tmp_path / "private")
    try:
        assert a.stage(Stage(message()))["status"] == "ABSTAIN"
        case = a.api.collection("/review/cases")[0]
        scope = {
            "expected_case_version": case["version"],
            "expected_context_sha256": case["context_sha256"],
            "customer_id": case["customer_id"],
            "tool": "find_contract_clauses",
            "limit": 50,
        }
        missing = a.api.request("POST", f"/cases/{case['id']}/evidence/search", json=scope)
        assert missing.status_code == 200 and missing.json()["items"] == []
        assert missing.json()["search_complete"] is True
        with Session(a.engine) as session:
            provision(session, a.org, "unit-auditor", "AUDITOR", "isolated-unit-password-0000")
        login = a.api.client.post(
            "/review/demo/login",
            json={"username": "unit-auditor", "password": "isolated-unit-password-0000"},
        )
        assert login.status_code == 200
        auditor = {"Authorization": "ReviewDemo " + login.json()["access_token"]}
        allowed = a.api.client.post(
            f"/cases/{case['id']}/evidence/search", json=scope, headers=auditor
        )
        assert (
            allowed.status_code == 200
        )  # Evidence POST is a READ capability, not finance authority.
        denied = a.api.client.post(
            f"/cases/{case['id']}/refresh",
            json={"expected_case_version": case["version"]},
            headers={**auditor, "Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 403 and denied.json()["detail"] == "REVIEW_READ_ONLY"
        wrong_scope = a.api.request(
            "POST",
            f"/cases/{case['id']}/evidence/search",
            json={**scope, "customer_id": str(uuid4())},
        )
        assert wrong_scope.status_code == 404
        assert wrong_scope.json()["detail"] == "VERIFIED_CASE_CUSTOMER_REQUIRED"
        raw = csv_bytes(
            "invoices", *[{**INVOICE, "invoice_number": f"unit-{n}"} for n in range(51)]
        )
        imported = a.api.request(
            "POST",
            "/imports/invoices",
            content=raw,
            headers={
                "Content-Type": "text/csv",
                "X-Data-Contract-Version": "1.0",
                "X-Source-Filename": "unit.csv",
            },
        )
        assert imported.status_code == 200
        before = rows(a.engine)
        cases, evidence, investigations = a.case_observations(a.api.collection("/receipts"), {})
        assert not investigations and len(cases) == 1
        assert evidence[0]["outcome"] == "COMPLETE" and len(evidence[0]["pages"]) == 2
        hits = [h for p in evidence[0]["pages"] for h in p["response"]["items"]]
        assert len(hits) == len({h["id"] for h in hits}) == 52
        assert all(not h["source_authenticated"] and not h["financial_authority"] for h in hits)
        assert rows(a.engine) == before
        paths = [c["path"] for c in a.api.calls]
        assert any(p.startswith("/cases?receipt_id=") and "&limit=" in p for p in paths)
    finally:
        a.close()


def page(*, more=False, cursor=None, items=None):
    return {
        "items": items or [],
        "has_more": more,
        "next_after_id": cursor,
        "search_complete": not more,
        "reasons": ["MORE_RESULTS"] if more else [],
        "input_sha256": "0" * 64,
    }


def hit(n):
    return {
        "record_type": "INVOICE",
        "id": str(UUID(int=n)),
        "version": 1,
        "kind": "INVOICE",
        "document_id": None,
        "document_version": None,
        "raw_sha256": "0" * 64,
        "canonical_sha256": "1" * 64,
        "page": None,
        "start": None,
        "end": None,
        "excerpt": "unit",
        "source_authenticated": False,
        "source_integrity": True,
        "is_current": True,
        "metadata": {},
    }


def observer(tmp_path, replies):
    a = Adapter("unused", tmp_path)
    requests = []

    def request(method, path, **kwargs):
        requests.append((method, path, kwargs))
        return replies.pop(0)

    a.api = SimpleNamespace(request=request)
    return (
        a,
        {"id": str(uuid4()), "version": 1, "context_sha256": "0" * 64, "customer_id": str(uuid4())},
        requests,
    )


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "DEMO_SESSION_INVALID"),
        (403, "REVIEW_READ_ONLY"),
        (404, "VERIFIED_CASE_CUSTOMER_REQUIRED"),
        (422, "INVALID_EVIDENCE_REQUEST"),
        (503, "EVIDENCE_DATABASE_OR_QUERY_LIMIT"),
        (500, "PRIVATE_BACKEND_VALUE"),
        (409, "PRIVATE_UNKNOWN_CONFLICT"),
        (403, "EVIDENCE_FINANCIAL_SOURCE_BUDGET"),
    ],
)
def test_unexpected_denials_fail_with_safe_status_and_code(tmp_path, status, code):
    a, case, requests = observer(tmp_path, [httpx.Response(status, json={"detail": code})])
    with pytest.raises(ObservationFailure) as error:
        a.observe_evidence(case)
    value = diagnostic(error.value, "evidence_query")
    assert value["http"]["status"] == status and len(requests) == 1
    assert "PRIVATE" not in str(value)
    if not code.startswith("PRIVATE"):
        assert value["http"]["code"] == code


def test_expected_budget_denial_is_explicit_review_not_success(tmp_path):
    a, case, requests = observer(
        tmp_path, [httpx.Response(409, json={"detail": "EVIDENCE_FINANCIAL_SOURCE_BUDGET"})]
    )
    value = a.observe_evidence(case)
    assert value["outcome"] == "REVIEW_REQUIRED" and not value["search_complete"]
    assert value["pages"][0]["http_status"] == 409 and "items" not in value
    assert len(requests) == 1


def test_missing_evidence_and_incomplete_pagination_are_distinct(tmp_path):
    a, case, _ = observer(tmp_path, [httpx.Response(200, json=page())])
    assert a.observe_evidence(case)["outcome"] == "NO_EVIDENCE"
    a, case, requests = observer(
        tmp_path,
        [
            httpx.Response(200, json=page(more=True, cursor=str(UUID(int=n)), items=[hit(n)]))
            for n in range(1, 5)
        ],
    )
    result = a.observe_evidence(case)
    assert result["outcome"] == "REVIEW_REQUIRED" and result["http_status"] == 200
    assert result["reason"] == "EVIDENCE_OBSERVATION_PAGE_LIMIT" and len(requests) == 4
    assert requests[1][2]["json"]["after_id"] == str(UUID(int=1))


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"private": "PRIVATE_SOURCE"},
        page(more=True),
        {**page(), "search_complete": False},
    ],
)
def test_invalid_200_is_fatal_not_fabricated_empty_evidence(tmp_path, body):
    a, case, _ = observer(tmp_path, [httpx.Response(200, json=body)])
    with pytest.raises(ObservationFailure) as error:
        a.observe_evidence(case)
    assert diagnostic(error.value, "evidence_query")["code"] == "EVIDENCE_RESPONSE_INVALID"


@pytest.mark.parametrize("operation", ["refresh", "investigate"])
def test_neighboring_mutation_denials_remain_fatal(tmp_path, operation):
    case = {
        "id": "case",
        "receipt_ids": ["receipt"],
        "document_ids": [],
        "is_stale": operation == "refresh",
        "customer_id": None,
        "version": 1,
        "context_sha256": "0" * 64,
    }
    a = Adapter("unused", tmp_path)
    requests = []

    def collection(path):
        if path.startswith("/cases?receipt_id="):
            return [case]
        assert path.endswith("/claims")
        return [{"id": "claim", "state": "EXTRACTED"}]

    def request(method, path, **kwargs):
        requests.append(path)
        return httpx.Response(403, json={"detail": "REVIEW_READ_ONLY"})

    a.api = SimpleNamespace(collection=collection, get=lambda _: case, request=request)
    with pytest.raises(ObservationFailure) as error:
        a.case_observations([{"id": "receipt"}], {})
    assert error.value.status == 403 and len(requests) == 1
    assert error.value.api_code == "REVIEW_READ_ONLY"


def test_scoped_case_discovery_ignores_unrelated_history_and_resolved_claims(tmp_path):
    a = Adapter("unused", tmp_path)
    case = {
        "id": "case",
        "receipt_ids": ["receipt"],
        "document_ids": [],
        "is_stale": False,
        "customer_id": None,
        "version": 1,
        "context_sha256": "0" * 64,
    }
    paths = []

    def collection(path):
        paths.append(path)
        assert path != "/review/cases", "Do not revalidate an unbounded unrelated case history"
        return [case] if path.startswith("/cases?") else [{"id": "claim", "state": "RESOLVED"}]

    a.api = SimpleNamespace(collection=collection)
    cases, evidence, runs = a.case_observations([{"id": "receipt"}], {})
    assert cases == [case] and not evidence
    assert runs == [
        {
            "case_id": "case",
            "outcome": "NOT_REQUESTED",
            "reason": "CLAIM_ALREADY_RESOLVED",
            "claim_ids": ["claim"],
        }
    ]
    assert len(paths) == 2


def test_investigation_snapshot_is_reread_after_worker_updates_case(tmp_path, monkeypatch):
    a = Adapter("unused", tmp_path)
    case = {
        "id": "case",
        "receipt_ids": ["receipt"],
        "document_ids": [],
        "is_stale": False,
        "customer_id": None,
        "version": 1,
        "context_sha256": "0" * 64,
    }
    a.api = SimpleNamespace(
        collection=lambda path: (
            [case] if path.startswith("/cases?") else [{"id": "claim", "state": "EXTRACTED"}]
        ),
        get=lambda path: dict(case) if path.startswith("/review/cases/") else {"id": "run"},
        request=lambda *args, **kwargs: httpx.Response(200, json={"id": "run"}),
    )
    a.engine, a.org, a.env = None, uuid4(), {}

    def work(*args):
        case["version"] = 2

    monkeypatch.setattr(adapter_module, "drain_owned", work)
    cases, _, runs = a.case_observations([{"id": "receipt"}], {})
    assert cases[0]["version"] == 2 and len(runs) == 1
