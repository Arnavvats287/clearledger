from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from clearledger.evidence_contract import Clause, Delivery, Finding, Money
from clearledger.evidence_domain import aggregate, predicate, trust_sources


def span(value):
    return {"page": 1, "start": 0, "end": len(value), "quote": value}


@given(st.integers(0, 2**63 - 1), st.integers(0, 2**63 - 1))
def test_exact_integer_cap_uses_independent_order_oracle(amount, cap):
    fact = Clause(
        type="CONTRACT",
        limit=Money(value=cap, span=span(f"{cap} paise")),
        conditions="NO_ADDITIONAL_CONDITIONS",
    )
    result = predicate("CLAUSE_LIMIT", amount, fact, uuid4())
    assert (result.outcome == "SUPPORTED") == (amount - cap <= 0)


@given(st.integers(0, 100), st.integers(0, 2**63 - 1), st.integers(0, 2**63 - 1))
def test_delivery_paise_no_float_or_overflow(units, price, amount):
    fact = Delivery(
        type="WMS",
        shipment={"value": "s", "span": span("s")},
        shipped={"value": units, "span": span(str(units))},
        delivered={"value": 0, "span": span("0")},
        damaged={"value": 0, "span": span("0")},
        unit_value={"value": price, "span": span(f"{price} paise")},
        unit="EACH",
    )
    result = predicate("DELIVERY_SHORTAGE", amount, fact, uuid4())
    # Repeated addition provides an oracle independent of the multiplication path.
    total = sum(price for _ in range(units))
    assert result.outcome == (
        "INSUFFICIENT" if total > 2**63 - 1 else "SUPPORTED" if total == amount else "CONTRADICTED"
    )


@given(
    st.lists(
        st.sampled_from(["SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "NOT_APPLICABLE"]),
        max_size=20,
    )
)
def test_incomplete_search_never_supports_and_conflicts_abstain(states):
    findings = [Finding(outcome=s, reasons=[], record_ids=[]) for s in states]
    assert aggregate(findings, False)[0] == "INSUFFICIENT"
    if "SUPPORTED" in states and "CONTRADICTED" in states:
        assert aggregate(findings, True)[0] == "INSUFFICIENT"


@pytest.mark.parametrize("value", [True, 1.01, "101", -1, 2**63])
def test_typed_fact_rejects_non_paise(value):
    with pytest.raises(ValidationError):
        Money(value=value, span=span("101 paise"))


@pytest.mark.parametrize(
    "raw", ["{}", '[{"secret":"sensitive-test-secret"}]', "null", "[1]", '["x"]']
)
def test_invalid_source_configuration_errors_never_include_secret(raw):
    from clearledger.case_domain import CaseError

    with pytest.raises(CaseError) as error:
        trust_sources(raw)
    assert str(error.value) == "INVALID_EVIDENCE_TRUST_CONFIGURATION"


def test_missing_condition_assessment_is_not_proof_of_eligibility():
    fact = Clause(type="CONTRACT", limit=Money(value=101, span=span("101 paise")))
    assert predicate("CLAUSE_LIMIT", 100, fact, uuid4()).outcome == "INSUFFICIENT"


def test_source_parse_cache_is_bounded_and_hash_changes_are_not_hidden(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from test_imports import BANK, csv_bytes

    from clearledger import matching
    from clearledger.data_contract import BankInput

    session = SimpleNamespace(info={"evidence_readonly": True})
    raw = csv_bytes("bank-transactions", BANK)
    source = SimpleNamespace(
        id=uuid4(),
        content_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=raw,
        status="ACCEPTED",
        kind="bank-transactions",
    )
    first = matching.source_rows(session, source, "bank-transactions")
    assert matching.source_rows(session, source, "bank-transactions") is first
    for _ in range(7):
        source.id = uuid4()
        matching.source_rows(session, source, "bank-transactions")
    source.id = uuid4()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        matching.source_rows(session, source, "bank-transactions")
    assert error.value.detail == "EVIDENCE_FINANCIAL_SOURCE_BUDGET"
    source.raw_bytes = b"altered source"
    monkeypatch.setattr(matching, "owned", lambda *args: source)
    record = SimpleNamespace(source_import_id=source.id, source_row=2, payload_sha256="0" * 64)
    actual = BankInput.model_validate({**BANK, "amount_paise": 100})
    assert not matching.source_valid(session, uuid4(), record, "bank-transactions", actual)


def test_original_cache_is_request_local_and_byte_bounded(tmp_path, monkeypatch):
    from clearledger.case_domain import CaseError
    from clearledger.document_runtime import LocalOriginals
    from clearledger.evidence_runtime import EvidenceOriginals

    calls = []

    def read(_, org, sha):
        calls.append((org, sha))
        return b"1234"

    monkeypatch.setattr(LocalOriginals, "get", read)
    store = EvidenceOriginals(tmp_path)
    store.MAX_BYTES = 8
    org = uuid4()
    assert store.get(org, "a" * 64) == store.get(org, "a" * 64)
    assert len(calls) == 1
    store.get(org, "b" * 64)
    with pytest.raises(CaseError, match="EVIDENCE_ORIGINAL_BYTE_BUDGET"):
        store.get(org, "c" * 64)
    assert EvidenceOriginals(tmp_path).get(org, "a" * 64) == b"1234"
    assert len(calls) == 4  # No successful proof/cache survives another operation.
