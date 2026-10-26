"""Actual APIs/outbox/LangGraph with offline model replies, never a live accuracy claim."""

import json
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_ai_usefulness import PROSE
from test_cases import pump
from test_document_domain import STRUCTURED
from test_documents import documents_environment as documents_environment
from test_documents import enable_fake, extract, get, upload
from test_imports import environment as environment
from test_matching import financial_state, setup
from test_reason_code_semantics import prose_result

from clearledger.case_models import ClaimSource, DomainEvent
from clearledger.document_privacy import project
from clearledger.extraction_provider import ProviderReply
from clearledger.investigation_contract import Limits

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("automatic", [False, True])
def test_extraction_to_first_investigation_without_recreating_facts(
    documents_environment, automatic
):
    env = documents_environment
    client = env[3]
    client.app.state.settings.case_auto_investigate_extractions = automatic
    # Automatic investigation must stay deterministic even when the configured manual mode differs.
    client.app.state.settings.investigation_provider = "gemini"
    client.app.state.settings.investigation_external_enabled = False
    setup(client)
    before = financial_state(client)
    doc = upload(client, PROSE.encode()).json()
    body = prose_result(project([PROSE]).pages[0])
    transport = enable_fake(client, [ProviderReply(json.dumps(body))])
    response = extract(client, doc["id"], allow_external=True)
    assert response.status_code == 200
    extracted = response.json()
    assert extracted["status"] == "NEEDS_REVIEW" and extracted["requires_human_review"]
    pump(env)
    cases = [c for c in get(client, "/cases").json() if doc["id"] in c["document_ids"]]
    assert len(cases) == 1
    case = cases[0]
    claims = get(client, f"/cases/{case['id']}/claims").json()
    assert len(claims) == 1 and claims[0]["category"] == "damage"
    assert claims[0]["amount_paise"] == 101 and claims[0]["state"] == "EXTRACTED"
    assert not case["receipt_ids"]  # PROSE has no UTR; never manufacture an association.
    assert case["customer_id"] is None
    investigations = get(client, f"/cases/{case['id']}/investigations").json()
    if automatic:
        assert len(investigations) == 1
        run = investigations[0]
        assert run["provider"] == "deterministic" and run["status"] == "COMPLETED"
        findings = get(client, f"/investigations/{run['id']}/findings").json()
        assert len(findings) == 1 and findings[0]["state"] == "INSUFFICIENT_EVIDENCE"
        assert findings[0]["requires_human_review"] and not findings[0]["financial_authority"]
        assert findings[0]["is_current"]
        with Session(env[0]) as session:
            event = session.scalar(
                select(DomainEvent).where(
                    DomainEvent.organization_id == env[1],
                    DomainEvent.event_type == "investigation.requested",
                )
            )
            cause = session.get(DomainEvent, UUID(event.payload["cause_event_id"]))
            assert cause.event_type == "case.reevaluation.requested"
            assert event.payload["include_extracted"]
    else:
        assert investigations == []
    with Session(env[0]) as session:
        source = session.scalar(
            select(ClaimSource).where(
                ClaimSource.organization_id == env[1], ClaimSource.claim_id == UUID(claims[0]["id"])
            )
        )
        assert str(source.extraction_id) == extracted["id"]
    assert extract(client, doc["id"], allow_external=True).json()["id"] == extracted["id"]
    assert pump(env) == {}
    assert len(get(client, f"/cases/{case['id']}/claims").json()) == 1
    assert len(get(client, f"/cases/{case['id']}/investigations").json()) == int(automatic)
    assert len(transport.calls) == 1
    assert get(env[4], f"/cases/{case['id']}").status_code == 404
    assert financial_state(client) == before


def test_false_reason_code_fails_before_case_creation(documents_environment):
    env = documents_environment
    client = env[3]
    client.app.state.settings.case_auto_investigate_extractions = True
    doc = upload(client, PROSE.encode()).json()
    enable_fake(
        client, [ProviderReply(json.dumps(prose_result(project([PROSE]).pages[0], "disputed")))]
    )
    result = extract(client, doc["id"], allow_external=True).json()
    assert result["status"] == "FAILED" and result["error_code"] == "REASON_CODE_LABEL_REQUIRED"
    assert result["result"] == {}
    pump(env)
    assert not get(client, "/cases").json()


def test_initial_investigation_limit_abstains_without_dropping_claims(documents_environment):
    env = documents_environment
    client = env[3]
    client.app.state.settings.case_auto_investigate_extractions = True
    client.app.state.settings.investigation_limits = Limits(max_claims=1)
    body = {
        **STRUCTURED,
        "claims": [
            {"category": "damage", "amount_paise": 101, "reason_code": None},
            {"category": "short_shipment", "amount_paise": 202, "reason_code": None},
        ],
    }
    doc = upload(
        client, json.dumps(body).encode(), mime="application/json", name="unit.json"
    ).json()
    assert extract(client, doc["id"]).json()["status"] == "SUCCEEDED"
    pump(env)
    case = get(client, "/cases").json()[0]
    assert case["state"] == "AWAITING_REVIEW"
    assert len(get(client, f"/cases/{case['id']}/claims").json()) == 2
    assert get(client, f"/cases/{case['id']}/investigations").json() == []
    with Session(env[0]) as session:
        event = session.scalar(
            select(DomainEvent).where(
                DomainEvent.organization_id == env[1],
                DomainEvent.event_type == "investigation.limit_reached",
            )
        )
        assert event.payload["code"] == "INVESTIGATION_CLAIM_LIMIT"


def test_superseded_extraction_does_not_start_initial_investigation(documents_environment):
    env = documents_environment
    client = env[3]
    client.app.state.settings.case_auto_investigate_extractions = True
    doc = upload(client, PROSE.encode()).json()
    visible = project([PROSE]).pages[0]
    enable_fake(client, [ProviderReply(json.dumps(prose_result(visible)))])
    assert extract(client, doc["id"], allow_external=True).json()["status"] == "NEEDS_REVIEW"
    # A changed configuration creates a new immutable extraction snapshot, not an edit.
    client.app.state.settings.llm_max_output_tokens -= 1
    enable_fake(client, [ProviderReply(json.dumps(prose_result(visible, "disputed")))])
    assert extract(client, doc["id"], allow_external=True).json()["status"] == "FAILED"
    pump(env)
    case = get(client, "/cases").json()[0]
    assert get(client, f"/cases/{case['id']}/investigations").json() == []
    claims = get(client, f"/cases/{case['id']}/claims").json()
    assert len(claims) == 1 and not claims[0]["source_current"]
