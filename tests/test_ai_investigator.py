"""Actual graph/API safety controls; these scripted replies are never live accuracy."""

from uuid import uuid4

import pytest
from test_cases import pump
from test_documents import get
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_evidence import fixture_case, manifest, register
from test_investigations import run, start
from test_matching import financial_state

from clearledger.case_domain import CaseError
from clearledger.investigation_ai import RATIONALES, default_plan, validate_plan, validate_synthesis
from clearledger.investigation_ai_contract import Synthesis
from clearledger.investigation_contract import Finding, Objective


class ScriptedAR:
    name = "fake"
    phased = True

    def __init__(self, fault=None):
        self.calls, self.fault = [], fault

    def reason(self, payload):
        self.calls.append(payload)
        if payload["phase"] == "investigator_plan":
            value = default_plan(
                Objective.model_validate(
                    {
                        **{k: v for k, v in payload["objective"].items() if k != "contract"},
                        "claim_version": 1,
                        "basis_sha256": "0" * 64,
                        "unknowns": [],
                    },
                )
            ).model_dump(mode="json")
            if self.fault == "tool":
                value["tools"] = ["execute_sql"]
            return {"plan": value, "synthesis": None}
        a = payload["verified_assessment"]
        conflict = any("CONFLICT" in r or "CONTRADICT" in r for r in a["reasons"])
        state = (
            "CONFLICTING_EVIDENCE"
            if conflict
            else "SUPPORTED"
            if a["outcomes"] == ["SUPPORTED"]
            else "INSUFFICIENT_EVIDENCE"
        )
        a = {
            "state": state,
            "next_action": "ESCALATE_CONFLICT"
            if conflict
            else "HUMAN_REVIEW"
            if state == "SUPPORTED"
            else "REQUEST_EVIDENCE",
            "uncertainty": "CONFLICTING_EVIDENCE"
            if conflict
            else "NONE"
            if state == "SUPPORTED"
            else "MISSING_EVIDENCE",
        }
        i = {"SUPPORTED": 0, "INSUFFICIENT_EVIDENCE": 1, "CONFLICTING_EVIDENCE": 2}[a["state"]]
        value = {
            "evidence_span_ids": [row["span_id"] for row in payload.get("evidence_spans", [])],
            "amount_paise": payload["objective"]["amount_paise"],
            "state": a["state"],
            "next_action": a["next_action"],
            "uncertainty": a["uncertainty"],
            "record_ids": payload["record_ids"],
            "observations": [
                {
                    "record_id": r["record_id"],
                    "field": "damaged_quantity",
                    "value": r["facts"]["damaged_quantity"],
                }
                for r in payload["evidence"]
                if "damaged_quantity" in r["facts"]
            ],
            "missing_evidence_types": sorted(
                {"WMS", "POD"} - {r["kind"] for r in payload["evidence"]}
            ),
            "rationale": RATIONALES[i],
            "confidence": "LOW" if i else "HIGH",
            "financial_authority": False,
        }
        if self.fault == "amount":
            value["amount_paise"] += 1
        if self.fault == "citation":
            value["record_ids"] = [str(uuid4())]
        if self.fault == "authority":
            value["financial_authority"] = True
        if self.fault == "unsupported":
            value.update(
                state="SUPPORTED",
                next_action="HUMAN_REVIEW",
                uncertainty="NONE",
                rationale=RATIONALES[0],
            )
        if self.fault == "quantity":
            value["observations"][0]["value"] += 1
        if self.fault == "missing_types":
            value["missing_evidence_types"] = []
        return {"plan": None, "synthesis": value}


@pytest.mark.postgres
@pytest.mark.parametrize("mode", ["missing", "supported", "conflict", "unsigned"])
def test_actual_phased_graph_and_unchanged_finances(documents_environment, mode):
    env = documents_environment
    case, claim = fixture_case(
        env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
    )
    if mode != "missing":
        for kind in ("WMS", "POD"):
            body = manifest(
                env,
                kind=kind,
                damaged=2 if mode == "conflict" and kind == "WMS" else 1,
                trusted=mode != "unsigned",
            )
            assert register(env, body).status_code == 200
        pump(env)
    before = financial_state(env[3])
    provider = ScriptedAR()
    env[3].app.state.investigation_provider = provider
    response = start(env, case, claim)
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    assert run(env, identifier, provider) == "DELIVERED"
    finding = get(env[3], f"/investigations/{identifier}/findings").json()[0]
    trace = get(env[3], f"/investigations/{identifier}/trace").json()
    assert finding["state"] == ("SUPPORTED" if mode == "supported" else "INSUFFICIENT_EVIDENCE"), (
        finding,
        trace,
        provider.calls,
    )
    expected = (
        "ESCALATE_CONFLICT"
        if mode == "conflict"
        else "HUMAN_REVIEW"
        if mode == "supported"
        else "REQUEST_EVIDENCE"
    )
    assert (
        next(t for t in trace if t["node"] == "human_review_or_request_evidence")["metadata"][
            "next_action"
        ]
        == expected
    )
    assert finding["requires_human_review"] and not finding["financial_authority"]
    assert len(provider.calls) == 2
    assert all("excerpt" not in str(p) and "secret" not in str(p) for p in provider.calls)
    if mode == "unsigned":
        assert provider.calls[-1]["record_ids"] == [] and provider.calls[-1]["evidence"] == []
    assert financial_state(env[3]) == before


@pytest.mark.postgres
@pytest.mark.parametrize(
    "fault", ["tool", "amount", "citation", "authority", "unsupported", "quantity", "missing_types"]
)
def test_invalid_model_facts_never_authorize_and_fallback(documents_environment, fault):
    env = documents_environment
    case, claim = fixture_case(
        env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
    )
    provider = ScriptedAR(fault)
    if fault == "quantity":
        for kind in ("WMS", "POD"):
            assert register(env, manifest(env, kind=kind, damaged=1)).status_code == 200
        pump(env)
    env[3].app.state.investigation_provider = provider
    response = start(env, case, claim)
    assert run(env, response.json()["id"], provider) == "DELIVERED"
    finding = get(env[3], f"/investigations/{response.json()['id']}/findings").json()[0]
    assert finding["state"] == "INSUFFICIENT_EVIDENCE"
    assert "PROVIDER_FAILURE" in finding["unknowns"]
    assert not finding["financial_authority"]


@pytest.mark.postgres
def test_plan_cache_refreshes_evidence_not_conclusions(documents_environment):
    env = documents_environment
    case, claim = fixture_case(
        env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
    )
    provider = ScriptedAR()
    env[3].app.state.investigation_provider = provider
    first = start(env, case, claim).json()
    assert run(env, first["id"], provider) == "DELIVERED"
    for kind in ("POD", "WMS"):
        assert register(env, manifest(env, kind=kind, damaged=1)).status_code == 200
    # Automatic deterministic refresh is consumed first; explicit AI run still revalidates.
    pump(env)
    second = start(env, case, claim).json()
    assert run(env, second["id"], provider) == "DELIVERED"
    assert [c["phase"] for c in provider.calls] == [
        "investigator_plan",
        "investigator_synthesize",
        "investigator_synthesize",
    ]
    result = get(env[3], f"/investigations/{second['id']}/findings").json()[0]
    assert result["state"] == "SUPPORTED" and result["citations"]


def test_strict_plan_and_synthesis_contracts():
    o = Objective(
        claim_id=uuid4(),
        claim_version=1,
        category="damage",
        amount_paise=100,
        basis_sha256="0" * 64,
        invoice_id=uuid4(),
        question="DELIVERY_DAMAGE",
        tools=["get_wms_deliveries", "get_proof_of_delivery"],
        unknowns=[],
    )
    p = default_plan(o)
    validate_plan(p, o)
    with pytest.raises(CaseError):
        validate_plan(p.model_copy(update={"amount_paise": 101}), o)
    with pytest.raises(CaseError):
        validate_plan(p.model_copy(update={"tools": ["get_proof_of_delivery"]}), o)
    finding = Finding(
        claim_id=o.claim_id,
        classification="damage",
        state="INSUFFICIENT_EVIDENCE",
        source_facts=[],
        citations=[],
        inference="NO_BACKED_CONCLUSION",
        contradictions=[],
        unknowns=["MISSING_EVIDENCE"],
        next_action="REQUEST_EVIDENCE",
    )
    s = Synthesis(
        amount_paise=100,
        state="INSUFFICIENT_EVIDENCE",
        next_action="REQUEST_EVIDENCE",
        record_ids=[],
        observations=[],
        missing_evidence_types=["WMS", "POD"],
        rationale=RATIONALES[1],
        confidence="LOW",
        uncertainty="MISSING_EVIDENCE",
        financial_authority=False,
    )
    validate_synthesis(s, o, finding)
    with pytest.raises(CaseError):
        validate_synthesis(s.model_copy(update={"amount_paise": 101}), o, finding)


@pytest.mark.postgres
@pytest.mark.parametrize("limit", ["spend", "round"])
def test_phased_budget_exhaustion_never_calls_provider(documents_environment, limit):
    env = documents_environment
    case, claim = fixture_case(env, amount="1.00")
    provider = ScriptedAR()
    provider.reserved_cost_paise = 1 if limit == "spend" else 0
    if limit == "round":
        settings = env[3].app.state.settings
        settings.investigation_limits = settings.investigation_limits.model_copy(
            update={"max_rounds": 1}
        )
    env[3].app.state.investigation_provider = provider
    identifier = start(env, case, claim).json()["id"]
    assert run(env, identifier, provider) == "DELIVERED"
    finding = get(env[3], f"/investigations/{identifier}/findings").json()[0]
    assert len(provider.calls) == (0 if limit == "spend" else 1)
    assert "BUDGET_EXHAUSTED" in finding["unknowns"]
    assert finding["state"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.postgres
def test_phased_stale_source_never_becomes_current(documents_environment):
    from sqlalchemy import text

    env = documents_environment
    case, claim = fixture_case(env, amount="1.00")
    provider = ScriptedAR()
    original = provider.reason

    def change(payload):
        value = original(payload)
        with env[0].begin() as connection:
            connection.execute(
                text("UPDATE invoices SET version=version+1 WHERE organization_id=:org"),
                {"org": env[1]},
            )
        return value

    provider.reason = change
    env[3].app.state.investigation_provider = provider
    identifier = start(env, case, claim).json()["id"]
    assert run(env, identifier, provider) == "DELIVERED"
    result = get(env[3], f"/investigations/{identifier}").json()
    assert result["status"] == "STALE" and result["is_stale"]


@pytest.mark.postgres
@pytest.mark.parametrize("invalid_schema", [False, True])
def test_real_provider_adapter_with_offline_gateway(
    documents_environment, monkeypatch, invalid_schema
):
    import json

    from pydantic import SecretStr

    from clearledger import investigation_provider
    from clearledger.extraction_provider import Gateway, ProviderReply

    env = documents_environment
    case, claim = fixture_case(env, amount="1.00")
    scripted = ScriptedAR()

    class Offline:
        def generate(self, pages):
            if invalid_schema:
                return ProviderReply(
                    '{"plan":{"amount_paise":"PRIVATE-CANARY"},"synthesis":null}', 100, 100, 200
                )
            return ProviderReply(json.dumps(scripted.reason(json.loads(pages[0]))), 100, 100, 200)

    gateway = Gateway(Offline(), attempts=1, input_rate=1, output_rate=1)
    monkeypatch.setattr(investigation_provider, "shared_gateway", lambda *args: gateway)
    settings = env[3].app.state.settings
    settings.external_ai_enabled = settings.investigation_external_enabled = True
    settings.investigation_provider = "gemini"
    settings.privacy_review_reference = "isolated-unit-synthetic"
    settings.gemini_api_key = SecretStr("isolated-unit-key")
    settings.gemini_model = "isolated-unit-model"
    settings.llm_input_paise_per_million_tokens = settings.llm_output_paise_per_million_tokens = 1
    settings.investigation_limits = settings.investigation_limits.model_copy(
        update={"max_spend_paise": 100}
    )
    identifier = start(env, case, claim, allow_external=True).json()["id"]
    assert run(env, identifier) == "DELIVERED"
    trace = get(env[3], f"/investigations/{identifier}/trace").json()
    synthesis = next(t for t in trace if t["node"] == "investigator_synthesize")["metadata"]
    assert synthesis["fallback"] == invalid_schema, trace
    if invalid_schema:
        error = next(t for t in trace if t["node"] == "PROVIDER")["metadata"]
        assert error["diagnostic"]["phase"] == "SCHEMA_VALIDATION"
        assert error["usage"]["input_tokens"] == 100
        assert "PRIVATE-CANARY" not in json.dumps(trace)
