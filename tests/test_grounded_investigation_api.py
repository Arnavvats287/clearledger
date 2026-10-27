"""Existing graph with source-ID synthesis, authenticated evidence and no finance mutation."""

import pytest
from test_ai_investigator import ScriptedAR
from test_cases import pump
from test_documents import get
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_evidence import fixture_case, manifest, register
from test_investigations import run, start
from test_matching import financial_state

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("invalid", [False, True])
def test_authenticated_graph_span_validation_and_financial_boundary(documents_environment, invalid):
    env = documents_environment
    case, claim = fixture_case(
        env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
    )
    for kind in ("WMS", "POD"):
        assert register(env, manifest(env, kind=kind, damaged=1, trusted=True)).status_code == 200
    pump(env)
    before = financial_state(env[3])

    class Grounded(ScriptedAR):
        span_grounded = True

        def reason(self, payload):
            value = super().reason(payload)
            if value["synthesis"] is not None:
                value["synthesis"]["evidence_span_ids"] = [
                    r["span_id"] for r in payload["evidence_spans"]
                ]
                if invalid:
                    value["synthesis"]["evidence_span_ids"] = ["invented-source-span"]
            return value

    provider = Grounded()
    env[3].app.state.investigation_provider = provider
    response = start(env, case, claim)
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    assert run(env, identifier, provider) == "DELIVERED"
    trace = get(env[3], f"/investigations/{identifier}/trace").json()
    synthesis = next(t for t in trace if t["node"] == "investigator_synthesize")["metadata"]
    assert synthesis["fallback"] == invalid
    if not invalid:
        assert synthesis["synthesis"]["evidence_span_ids"]
    findings = get(env[3], f"/investigations/{identifier}/findings").json()
    assert findings[0]["requires_human_review"] and not findings[0]["financial_authority"]
    assert findings[0]["state"] == ("INSUFFICIENT_EVIDENCE" if invalid else "SUPPORTED")
    assert financial_state(env[3]) == before
