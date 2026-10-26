"""Actual extraction APIs + real SDK, with HTTP fully intercepted in memory.

This verifies plumbing/validation, never live Gemini accuracy. No real key is read.
"""

import io
import json
import logging
import sys
from uuid import UUID, uuid4

import httpx
import pytest
from google import genai
from sqlalchemy.orm import Session
from test_ai_usefulness import PROSE
from test_document_domain import minimal_model_result
from test_documents import auth, extract, get, upload
from test_documents import documents_environment as documents_environment
from test_imports import environment as environment
from test_matching import financial_state, setup

from clearledger.document_privacy import project
from clearledger.extraction_provider import Gateway, GeminiTransport
from clearledger.gemini_schema import PROVIDER_SCHEMA_VERSION, remittance_response_schema
from clearledger.models import DocumentExtraction

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("none", "NEEDS_REVIEW"),
        ("alternative", "NEEDS_REVIEW"),
        ("float", "FAILED"),
        ("amount", "FAILED"),
        ("span", "FAILED"),
        ("zero_page", "FAILED"),
        ("outside_claim", "FAILED"),
        ("authority", "FAILED"),
        ("too_many", "FAILED"),
        ("uncertainty", "FAILED"),
    ],
)
def test_actual_sdk_contract_and_host_validation(
    documents_environment, monkeypatch, fault, expected
):
    from clearledger import document_runtime, gemini_worker

    client = documents_environment[3]
    setup(client)
    before = financial_state(client)
    pages = project([PROSE]).pages
    body = minimal_model_result(pages[0])

    def span(quote):
        pos = pages[0].index(quote)
        return {"page": 1, "start": pos, "end": pos + len(quote), "quote": quote}

    body["claims"] = [
        {
            "category": "damage",
            "description": {"page": 1, "start": 0, "end": len(pages[0]), "quote": pages[0]},
            "amount_paise": 101,
            "amount_span": span("INR 1.01"),
            "reason_code": None,
        }
    ]
    if fault == "float":
        body["claims"][0]["amount_paise"] = 101.0
    if fault == "amount":
        body["claims"][0]["amount_paise"] = 999
    if fault == "span":
        body["invoice_references"][0]["span"]["start"] += 1
    if fault == "zero_page":
        body["invoice_references"][0]["span"]["page"] = 0
    if fault == "outside_claim":
        body["claims"][0]["description"] = span("damage")
    if fault == "authority":
        body["financial_authority"] = True
    if fault == "too_many":
        body["invoice_references"] *= 101
    if fault == "uncertainty":
        body["uncertainty"] = "approved"
    captured = {}
    paths = []
    model = "gemini-3.5-flash-lite" if fault == "alternative" else "gemini-3.1-flash-lite"

    def local_http(request):
        path = request.url.path
        paths.append(path)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "name": f"models/{model}",
                    "supportedGenerationMethods": ["generateContent"],
                    "inputTokenLimit": 1048576,
                    "outputTokenLimit": 65536,
                    "version": "offline-unit",
                },
            )
        payload = json.loads(request.content)
        if path.endswith(":countTokens"):
            captured["count"] = payload["generateContentRequest"]
            return httpx.Response(200, json={"totalTokens": 100})
        assert path.endswith(":generateContent")
        captured["generate"] = payload
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": json.dumps(body)}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 100,
                    "totalTokenCount": 200,
                },
            },
        )

    real_client = genai.Client
    real_worker = document_runtime.run_worker

    def offline_client(**kwargs):
        kwargs["http_options"].client_args = {
            "transport": httpx.MockTransport(local_http),
            "trust_env": False,
        }
        return real_client(**kwargs)

    def worker(module, payload, timeout=10):
        if module != "clearledger.gemini_worker":
            return real_worker(module, payload, timeout)
        output = io.StringIO()
        with monkeypatch.context() as child:
            child.setattr(genai, "Client", offline_client)
            child.setattr(logging, "disable", lambda _: None)
            child.setattr("clearledger.worker_security.posix_limits", lambda: None)
            child.setattr("clearledger.worker_security.install_guard", lambda **_: None)
            child.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode())))
            child.setattr(sys, "stdout", output)
            gemini_worker.main()
        return json.loads(output.getvalue())

    settings = client.app.state.settings
    settings.external_ai_enabled = True
    settings.extraction_provider = "gemini"
    settings.gemini_model = model
    settings.privacy_review_reference = "approved-synthetic-offline-unit"
    client.app.state.extraction_gateway = Gateway(
        GeminiTransport("offline-unit-not-a-secret", settings.gemini_model), attempts=1
    )
    monkeypatch.setattr(document_runtime, "run_worker", worker)
    doc = upload(client, PROSE.encode()).json()
    assert extract(client, doc["id"]).json()["status"] == "NEEDS_REVIEW"
    assert paths == []  # Deterministic-first path did not touch even mocked SDK HTTP.
    result = extract(client, doc["id"], allow_external=True).json()
    with Session(documents_environment[0]) as session:
        assert (
            session.get(DocumentExtraction, UUID(result["id"])).inputs["provider_schema_version"]
            == PROVIDER_SCHEMA_VERSION
        )
    assert result["status"] == expected
    assert len(paths) == 3 and paths[-1].endswith(":generateContent")
    counted = captured["count"]
    assert counted.pop("model") == f"models/{model}"
    assert counted == captured["generate"]
    assert (
        captured["generate"]["generationConfig"]["responseJsonSchema"]
        == remittance_response_schema()
    )
    assert captured["generate"]["tools"] == []
    assert (
        json.loads(captured["generate"]["contents"][0]["parts"][0]["text"])["untrusted_pages"]
        == pages
    )
    assert not result["financial_authority"] and result["requires_human_review"]
    if fault in {"none", "alternative"}:
        assert result["result"]["invoice_references"][0]["value"] == "I-1"
        assert result["result"]["claims"][0]["amount_paise"] == 101
        for pointer in [
            result["result"]["invoice_references"][0]["span"],
            result["result"]["claims"][0]["amount_span"],
        ]:
            response = client.post(
                f"/documents/{doc['id']}/verify-span", headers=auth(), json=pointer
            )
            assert response.status_code == 200 and response.json()["source_consistent"]
        assert (
            get(client, f"/documents/{doc['id']}/extractions").json()[-1]["result"]
            == result["result"]
        )
    else:
        assert result["result"] == {}
    assert financial_state(client) == before


def test_disabled_extraction_keeps_legacy_request_identity(documents_environment):
    client = documents_environment[3]
    doc = upload(client, b"INVOICE: i").json()
    key = uuid4()
    first = extract(client, doc["id"], key=key).json()
    assert first["route"] == "DETERMINISTIC"
    with Session(documents_environment[0]) as session:
        assert (
            "provider_schema_version"
            not in session.get(DocumentExtraction, UUID(first["id"])).inputs
        )
    assert extract(client, doc["id"], key=key).json() == first
