"""Independent financial-authority and abstention properties."""

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from clearledger.evidence_contract import Verification
from clearledger.investigation_contract import InvestigatorReply, Objective, Proposal, ProviderInput
from clearledger.investigation_director import consistency
from clearledger.investigation_provider import DeterministicInvestigator


def objective(category="damage", amount=101):
    return Objective(
        claim_id=uuid4(),
        claim_version=1,
        category=category,
        amount_paise=amount,
        basis_sha256="0" * 64,
        invoice_id=uuid4(),
        question="DELIVERY_DAMAGE",
        tools=["get_wms_deliveries"],
        unknowns=[],
    )


@given(
    st.integers(min_value=0, max_value=2**63 - 1),
    st.sampled_from(
        ["TIMEOUT", "FORGED_CITATION", "PROVIDER_FAILURE", "TOOL_LIMIT", "STALE_INPUTS"]
    ),
)
def test_failures_never_have_financial_authority(amount, error):
    original = objective(amount=amount)
    finding = consistency(original, None, None, [], error=error)
    assert finding.state == "INSUFFICIENT_EVIDENCE"
    assert finding.requires_human_review and not finding.financial_authority
    assert original.amount_paise == amount
    assert not finding.citations and not finding.source_facts


@given(
    st.sampled_from(["SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "NOT_APPLICABLE"]), st.booleans()
)
def test_unbacked_positive_model_assertions_cannot_be_supported(verdict, incomplete):
    original = objective()
    verification = Verification(
        outcome=verdict,
        reasons=[],
        findings=[],
        input_sha256="1" * 64,
        search_complete=not incomplete,
    )
    hypothesis = Proposal(
        classification="damage",
        suggested_state="SUPPORTED",
        citations=[],
        unknowns=[],
        inference="PREDICATE_MAY_APPLY",
        next_action="HUMAN_REVIEW",
    )
    finding = consistency(original, hypothesis, verification, [], incomplete=incomplete)
    assert finding.state == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize(
    "tool", ["execute_sql", "read_file", "http_get", "approve", "post_journal"]
)
def test_capability_schema_excludes_privileged_tools(tool):
    with pytest.raises(ValidationError):
        InvestigatorReply(action="SEARCH", tool=tool)


@pytest.mark.parametrize("value", [True, 1, "true"])
def test_financial_authority_cannot_be_requested(value):
    with pytest.raises(ValidationError):
        Proposal(
            classification="damage",
            suggested_state="SUPPORTED",
            citations=[],
            unknowns=[],
            inference="NO_BACKED_CONCLUSION",
            next_action="HUMAN_REVIEW",
            financial_authority=value,
        )


def test_deterministic_replay_is_identical_and_typed():
    request = ProviderInput(objective=objective(), hits=[], offered=[], searched_tools=[])
    provider = DeterministicInvestigator()
    assert provider.generate(request) == provider.generate(request)
    assert provider.generate(request).tool == "get_wms_deliveries"


def test_tax_is_review_even_with_model_supported_assertion():
    result = consistency(objective("tax"), None, None, [])
    assert result.state == "NEEDS_TAX_REVIEW" and result.next_action == "TAX_REVIEW"


@given(
    st.sampled_from(
        [
            "UNKNOWN_CUSTOMER",
            "UNKNOWN_AMOUNT",
            "AMBIGUOUS_INVOICE",
            "UNCERTAIN_EXTRACTION",
            "MISSING_EVIDENCE",
        ]
    )
)
def test_unknowns_override_positive_source_predicate_with_real_pointer(unknown):
    from clearledger.investigation_contract import OfferedPointer

    pointer = OfferedPointer(
        record_id=uuid4(),
        document_id=uuid4(),
        document_version=1,
        raw_sha256="0" * 64,
        canonical_sha256="1" * 64,
        page=1,
        start=0,
        end=10,
        excerpt="100 paise",
    )
    hypothesis = Proposal(
        classification="damage",
        suggested_state="SUPPORTED",
        citations=[pointer],
        unknowns=[unknown],
        inference="PREDICATE_MAY_APPLY",
        next_action="HUMAN_REVIEW",
    )
    verified = Verification(
        outcome="SUPPORTED", reasons=[], findings=[], input_sha256="2" * 64, search_complete=True
    )
    result = consistency(objective(), hypothesis, verified, [pointer])
    assert result.state == "INSUFFICIENT_EVIDENCE" and unknown in result.unknowns


def test_optional_transport_reuses_gateway_without_external_call():
    from clearledger.investigation_provider import shared_gateway

    gateway = shared_gateway(
        "isolated-unit-key", "unvalidated-unit-model", 1000, 100, 100, 10, 1, 1
    )
    again = shared_gateway("isolated-unit-key", "unvalidated-unit-model", 1000, 100, 100, 10, 1, 1)
    assert gateway is again and gateway.attempts == 1
    assert gateway.transport.task == "investigation"
    # Holding the slot rejects concurrent work before any transport execution.
    assert gateway._slot.acquire(blocking=False)
    from clearledger.document_contract import ExtractionError

    try:
        with pytest.raises(ExtractionError, match="PROVIDER_BUSY"):
            gateway.generate(["untrusted text"])
    finally:
        gateway._slot.release()


def test_investigation_transport_selects_only_fixed_schema_task(monkeypatch):
    from clearledger.extraction_provider import GeminiTransport

    calls = []

    def fake_worker(module, payload, timeout):
        calls.append(payload)
        return {"json_text": "{}"}

    monkeypatch.setattr("clearledger.document_runtime.run_worker", fake_worker)
    GeminiTransport("isolated-unit-key", "unvalidated-unit-model", task="investigation").generate(
        ["projected"]
    )
    assert calls[0]["task"] == "investigation"
    assert "database_url" not in calls[0] and "tools" not in calls[0]
