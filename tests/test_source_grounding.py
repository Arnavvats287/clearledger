"""Independent source locations, candidate admission and evidence-first safety invariants."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clearledger.document_contract import ExtractionError, validate_semantics
from clearledger.grounded_extraction import RemittanceSelection, catalog, resolve_selection
from clearledger.source_candidates import discover, select
from clearledger.source_ocr import from_ocr
from clearledger.source_retrieval import assertion_gate, retrieve
from clearledger.source_spans import GroundingError, Page, Token, build, digest, text_source


def test_stable_hash_bound_spans_and_unknown_rejection():
    source = text_source("company/document", ["same text\nsame text"])
    copy = text_source("company/document", ["same text\nsame text"])
    assert source == copy
    assert source.spans[0].span_id != source.spans[1].span_id
    for span in source.spans:
        assert (
            source.resolve(
                span.span_id, expected_hash=source.source_hash, expected_version="1"
            ).text
            == "same text"
        )
    with pytest.raises(GroundingError, match="STALE_SOURCE"):
        source.resolve(source.spans[0].span_id, expected_hash="0" * 64, expected_version="1")
    with pytest.raises(GroundingError, match="UNKNOWN_SPAN"):
        source.resolve("invented", expected_hash=source.source_hash, expected_version="1")
    changed = replace(source, pages=(Page(1, "tampered text\nsame text"),))
    with pytest.raises(GroundingError, match="SOURCE_SPAN_INTEGRITY"):
        changed.resolve(
            source.spans[0].span_id, expected_hash=source.source_hash, expected_version="1"
        )


def test_duplicate_values_resolve_to_selected_bbox_not_string_search():
    text = "Invoice number: INV-001\nInvoice number: INV-001"
    tokens = (
        Token("first", 16, 23, (0.1, 0.1, 0.3, 0.2)),
        Token("second", 40, 47, (0.1, 0.7, 0.3, 0.8)),
    )
    # Offsets are independently derived from literal fixture positions.
    left = text.index("INV-001")
    right = text.rindex("INV-001")
    tokens = (
        replace(tokens[0], start=left, end=left + 7),
        replace(tokens[1], start=right, end=right + 7),
    )
    source = build("company/document", (Page(1, text, tokens),), source_hash=digest(text))
    choices = discover(source)
    matches = [c for c in choices.items if c.value == "INV-001"]
    assert len(matches) == 2
    spans = select(choices, [c.candidate_id for c in matches])
    assert spans[0].bbox != spans[1].bbox
    assert {s.token_ids for s in spans} == {("first",), ("second",)}
    with pytest.raises(GroundingError, match="UNKNOWN_CANDIDATE"):
        select(choices, ["invented"])
    assert select(choices, []) == []


@pytest.mark.parametrize("label", ["Invoice number", "Document no.", "Bill number"])
def test_invoice_label_adjacent_value_and_exact_leading_zeroes(label):
    c = discover(text_source("doc", ["Tax invoice\n" + label + ":\n0001042"]))
    assert any(item.value == "0001042" for item in c.items)


def test_multi_token_reference_preserves_spaces_and_zeroes():
    c = discover(text_source("doc", ["Tax invoice\nInvoice number: 0012 0042"]))
    assert any(item.value == "0012 0042" for item in c.items)


@pytest.mark.parametrize(
    "title", ["Purchase order", "Bank statement", "Delivery note", "Quotation"]
)
def test_non_invoice_admission(title):
    c = discover(text_source("doc", [title + "\nInvoice number: INV-001"]))
    assert c.admission == "OUT_OF_SCOPE" and not c.items


def test_retrieval_prioritizes_exact_financial_keys_and_includes_context():
    source = text_source(
        "doc",
        [
            "Damage to goods discussed.\nInvoice INV-0042 damage INR 30.01.\n"
            "Signed POD missing.\nInvoice INV-9999 damage INR 30.00."
        ],
    )
    found = retrieve(source, "INV-0042 INR 30.01 damage", limit=1)
    assert source.spans[1] in found
    assert source.spans[2] in found


def test_missing_is_not_contradiction_and_mismatched_exact_facts_abstain():
    source = text_source("doc", ["Invoice INV-0042 damage INR 30.01 remains unverified."])
    check = assertion_gate(
        source,
        [source.spans[0].span_id],
        "Invoice INV-0042 damage",
        source_hash=source.source_hash,
        source_version="1",
        relation="CONFLICT",
    )
    assert not check.admitted and not check.financial_authority
    check = assertion_gate(
        source,
        [source.spans[0].span_id],
        "Invoice INV-0042 damage",
        source_hash=source.source_hash,
        source_version="1",
        relation="SUPPORT",
        required_atoms=("30.02",),
    )
    assert "EXACT_FACT_MISMATCH" in check.reasons


def test_explicit_conflict_and_currentness_are_separate():
    source = text_source("doc", ["Disclosure to employees is not permitted."])
    args = dict(source_hash=source.source_hash, source_version="1", relation="CONFLICT")
    assert assertion_gate(
        source, [source.spans[0].span_id], "Disclosure to employees", **args
    ).admitted
    assert not assertion_gate(
        source, [source.spans[0].span_id], "Disclosure to employees", current=False, **args
    ).admitted
    assert not assertion_gate(source, [], "Disclosure to employees", **args).admitted


def test_explicit_permission_can_conflict_with_a_prohibition_not_with_absence():
    source = text_source("doc", ["Disclosure to employees is permitted."])
    check = assertion_gate(
        source,
        [source.spans[0].span_id],
        "Disclosure to employees is not permitted.",
        source_hash=source.source_hash,
        source_version="1",
        relation="CONFLICT",
    )
    assert check.admitted and not check.financial_authority


def test_ocr_fallback_never_fabricates_coordinates_and_records_provenance():
    raw = {
        "pages": [
            {
                "blocks": [
                    {
                        "lines": [
                            {
                                "words": [
                                    {"value": "Invoice", "geometry": [[0.1, 0.1], [0.2, 0.2]]},
                                    {"value": "INV-001", "geometry": [[0.3, 0.1], [2, 0.2]]},
                                ]
                            }
                        ]
                    }
                ]
            },
            {"blocks": []},
        ]
    }
    source = from_ocr("doc", raw, source_hash="a" * 64, alternatives={2: "Valid alternative text"})
    assert source.pages[0].tokens[1].bbox is None
    assert source.spans[0].bbox is None
    assert source.fallbacks[0].reason == "INVALID_OCR_GEOMETRY"
    assert source.fallbacks[1].method == "ALTERNATE_TEXT_LAYER_NO_COORDINATES"
    assert all(f.source_hash == "a" * 64 for f in source.fallbacks)
    assert source.pages[1].tokens == ()


@pytest.mark.parametrize("declared", [7, 0.0, False])
def test_ocr_declared_wrong_page_never_invents_page_mapping(declared):
    source = from_ocr(
        "doc", {"pages": [{"page_idx": declared, "blocks": []}]}, source_hash="b" * 64
    )
    assert not source.spans
    assert source.fallbacks[0].reason == "INVALID_OCR_PAGE_ORDER"


def test_candidate_remittance_produces_unchanged_strict_financial_semantics():
    text = "Invoice I-1 payment has a disputed damage deduction of INR 1.01."
    c = catalog([text])
    invoice = next(i for i in c.items if i.value == "I-1")
    description = next(s for s in c.source.spans if s.text == text)
    amount = next(s for s in c.source.spans if s.text == "INR 1.01")
    value = RemittanceSelection(
        invoice_candidate_ids=[invoice.candidate_id],
        utr_span_ids=[],
        claims=[
            dict(
                category="damage",
                description_span_id=description.span_id,
                amount_paise=101,
                amount_span_id=amount.span_id,
                reason_code_span_id=None,
            )
        ],
        uncertainty="review",
        unparsed_span_ids=[],
    )
    result = resolve_selection(value, c)
    validate_semantics(result, [text])
    assert result.claims[0].amount_paise == 101 and result.claims[0].reason_code is None
    result.claims[0].amount_paise = 102
    with pytest.raises(ExtractionError, match="AMOUNT_SOURCE_MISMATCH"):
        validate_semantics(result, [text])


@given(st.integers(min_value=0, max_value=10**18))
def test_integer_paise_atoms_never_round(value):
    from clearledger.source_retrieval import exact_atoms

    assert str(value) in exact_atoms(f"Claim {value} paise")
