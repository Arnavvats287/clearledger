"""Actual API persistence of mocked failures; no external transport."""

import json

import pytest
from test_document_domain import minimal_model_result
from test_documents import documents_environment as documents_environment
from test_documents import enable_fake, extract, get, upload
from test_imports import environment as environment
from test_matching import financial_state, setup

from clearledger.document_privacy import project
from clearledger.extraction_provider import ProviderFailure, ProviderReply


@pytest.mark.postgres
@pytest.mark.parametrize(
    "fault,phase",
    [
        ("provider", "TOKEN_COUNT"),
        ("json", "RESPONSE_DECODING"),
        ("schema", "SCHEMA_VALIDATION"),
        ("span", "SOURCE_VALIDATION"),
    ],
)
def test_safe_failure_diagnostic_is_durable_without_financial_mutation(
    documents_environment, fault, phase
):
    client = documents_environment[3]
    setup(client)
    before = financial_state(client)
    source = "Invoice I-1 paid INR 1.00."
    canary = "PRIVATE-KEY-PROMPT-BODY-https://secret.invalid"
    if fault == "provider":
        reply = ProviderFailure(
            canary,
            details={
                "phase": phase,
                "exception_category": "HTTP_API",
                "http_status": 400,
                "provider_status": "FAILED_PRECONDITION",
                "body": canary,
            },
        )
    elif fault == "json":
        reply = ProviderReply("{" + canary)
    elif fault == "schema":
        reply = ProviderReply(json.dumps({"private_unknown": canary}))
    else:
        body = minimal_model_result(project([source]).pages[0])
        body["invoice_references"][0]["span"]["start"] += 1
        reply = ProviderReply(json.dumps(body))
    doc = upload(client, source.encode()).json()
    transport = enable_fake(client, [reply])
    result = extract(client, doc["id"], allow_external=True).json()
    assert result["status"] == "FAILED" and not result["result"]
    assert result["metrics"]["diagnostic"]["phase"] == phase
    if fault == "provider":
        assert result["metrics"]["diagnostic"]["http_status"] == 400
        assert result["metrics"]["diagnostic"]["provider_status"] == "FAILED_PRECONDITION"
    assert canary not in json.dumps(result)
    assert not result["financial_authority"] and result["requires_human_review"]
    assert len(transport.calls) == 1
    assert extract(client, doc["id"], allow_external=True).json() == result
    assert len(transport.calls) == 1
    assert (
        get(client, f"/documents/{doc['id']}/extractions").json()[-1]["metrics"]["diagnostic"]
        == result["metrics"]["diagnostic"]
    )
    assert financial_state(client) == before
