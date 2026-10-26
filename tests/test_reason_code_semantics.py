"""Source category/status/explicit code are different facts; no live provider."""

import json

import pytest
from test_document_domain import STRUCTURED, minimal_model_result

from clearledger.document_contract import Extraction, ExtractionError, validate_semantics
from clearledger.document_privacy import project
from clearledger.remittance_parser import structured


def prose_result(source, reason=None):
    def span(quote):
        start = source.index(quote)
        return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

    body = minimal_model_result(source)
    body["claims"] = [
        {
            "category": "damage",
            "description": span(source),
            "amount_paise": 101,
            "amount_span": span("INR 1.01"),
            "reason_code": {"value": reason, "span": span(reason)} if reason else None,
        }
    ]
    return body


@pytest.mark.parametrize("reason", ["disputed", "damage"])
def test_category_and_dispute_word_cannot_be_promoted_to_reason_code(reason):
    source = "Invoice I-1: damage INR 1.01 disputed."
    with pytest.raises(ExtractionError, match="REASON_CODE_LABEL_REQUIRED"):
        validate_semantics(Extraction.model_validate(prose_result(source, reason)), [source])
    valid = Extraction.model_validate(prose_result(source))
    validate_semantics(valid, [source])
    assert valid.claims[0].category == "damage" and valid.claims[0].reason_code is None
    assert "disputed" in valid.claims[0].description.quote


@pytest.mark.parametrize(
    "label,code",
    [
        ("Reason code:", "DMG-01"),
        ("reason_code =", "R.2"),
        ("reason-code#", "D_03"),
        ("reason code:", "disputed"),
    ],
)
def test_explicit_codes_survive_projection_and_validation(label, code):
    source = f"Invoice I-1: damage INR 1.01; {label} {code}"
    visible = project([source]).pages[0]
    assert code in visible
    result = Extraction.model_validate(prose_result(visible, code))
    validate_semantics(result, [visible])
    assert result.claims[0].reason_code.value == code


def test_partial_code_and_sensitive_identifier_still_fail_closed():
    source = "Invoice I-1: damage INR 1.01; reason code: DMG-01"
    with pytest.raises(ExtractionError, match="REASON_CODE_LABEL_REQUIRED"):
        validate_semantics(Extraction.model_validate(prose_result(source, "DMG")), [source])
    with pytest.raises(ExtractionError, match="PRIVACY_ESSENTIAL_IDENTIFIER_CONFLICT"):
        project(["Invoice I-1: reason code: ABCDE1234F"])


def test_json_explicit_reason_field_is_preserved_even_for_status_word():
    source = {
        **STRUCTURED,
        "claims": [{"category": "damage", "amount_paise": 101, "reason_code": "disputed"}],
    }
    assert structured(json.dumps(source)).claims[0].reason_code.value == "disputed"


def test_automatic_extraction_investigations_are_opt_in():
    from clearledger.config import Settings

    assert Settings.model_fields["case_auto_investigate_extractions"].default is False


def test_code_label_must_bind_the_exact_occurrence_not_an_earlier_status():
    source = "Invoice I-1: damage INR 1.01 disputed; reason code: disputed"
    result = Extraction.model_validate(prose_result(source, "disputed"))
    with pytest.raises(ExtractionError, match="REASON_CODE_LABEL_REQUIRED"):
        validate_semantics(result, [source])
    start = source.rindex("disputed")
    result.claims[0].reason_code.span.start = start
    result.claims[0].reason_code.span.end = start + len("disputed")
    validate_semantics(result, [source])
    assert result.claims[0].reason_code.value == "disputed"
