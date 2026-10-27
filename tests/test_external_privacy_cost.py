"""Offline privacy/cost tests with tiny synthetic strings, never public corpus contents."""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from external_eval.source import docile_packet, write_json  # noqa: E402
from external_privacy_cost import (  # noqa: E402
    PATTERNS,
    REFERENCES,
    combine,
    cost_row,
    cost_spec,
    encoded,
    make_costs,
    privacy_only_ocr,
    request_estimate,
    screen,
    usd,
)

PRICES = {"input_per_million_usd": "0.30", "output_per_million_usd": "2.50"}


@pytest.mark.parametrize(
    "text,category",
    [
        ("Name: Example Person", "personal_name_context"),
        ("unit@example.invalid", "email_address"),
        ("Phone: 212-555-0100", "phone_number"),
        ("Address: Synthetic street", "physical_address_context"),
        ("Signed by: Example Person", "signatory_information"),
        ("Bank account number", "account_payment_context"),
        ("Tax ID", "tax_identifier_candidate"),
        ("Password: synthetic-placeholder", "payment_credentials_context"),
        ("Confidential information", "confidential_business_context"),
        ("Customer list", "company_sensitive_context"),
        ("Passport", "other_identifier_context"),
    ],
)
def test_candidate_categories_never_emit_source_values(text, category):
    result = screen("fixture", text, "contract-nli", "scored", "a" * 64)
    assert category in result["categories_detected"]
    assert result["candidate_occurrence_counts"][category] >= 1
    assert text not in json.dumps(result)
    assert result["manual_review_needed"] is True
    assert result["source_changed"] is False


def test_empty_candidate_set_is_not_automatic_clearance():
    result = screen("fixture", "An ordinary unit clause.", "contract-nli", "scored", "a" * 64)
    assert result["categories_detected"] == []
    assert result["proposed_transmission_decision"] == "MANUAL_REVIEW_REQUIRED"


def test_rights_block_and_redaction_requires_v2_not_silent_replacement():
    original = "Contact unit@example.invalid"
    redaction = screen("fixture", original, "contract-nli", "scored", "a" * 64)
    assert redaction["proposed_transmission_decision"] == "REQUIRE_REDACTION"
    assert redaction["protocol_v2_required_if_redacted"] is True
    assert redaction["source_changed"] is False
    denied = screen("fixture", "No risk indicator.", "docile", "scored", "a" * 64)
    assert denied["proposed_transmission_decision"] == "DENY"


def test_no_gold_or_production_module_dependency_in_fresh_process():
    import subprocess

    code = (
        "import sys;sys.path.insert(0,sys.argv[1]);import external_privacy_cost;"
        "assert 'external_eval.gold' not in sys.modules;"
        "assert not any(k.startswith(('clearledger','google.genai')) for k in sys.modules)"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SCRIPTS)], capture_output=True, check=False
    )
    assert done.returncode == 0, done.stderr.decode()


def test_privacy_empty_page_does_not_relax_frozen_adapter(tmp_path):
    path = tmp_path / "ocr.json"
    write_json(path, {"pages": [{"page_idx": 0, "blocks": []}]})
    view = privacy_only_ocr(path, "fixture")
    assert view["pages"] == [{"page": 0, "text": ""}]
    with pytest.raises(ValueError, match="EMPTY_OCR_PAGE"):
        docile_packet(path, "fixture")


def test_privacy_empty_word_retains_source_but_adapter_still_rejects(tmp_path):
    path = tmp_path / "ocr.json"
    write_json(
        path,
        {
            "pages": [
                {
                    "page_idx": 0,
                    "blocks": [
                        {
                            "lines": [
                                {"words": [{"value": "", "geometry": [[0.1, 0.1], [0.2, 0.2]]}]}
                            ]
                        }
                    ],
                }
            ]
        },
    )
    assert privacy_only_ocr(path, "fixture")["pages"][0]["text"] == "\n"
    with pytest.raises(ValueError, match="INVALID_OCR_WORD"):
        docile_packet(path, "fixture")


def test_costs_are_exact_decimals_and_caps_include_thinking():
    nli = cost_row(131661, 786432, 36864, 98304, 24, PRICES)
    docile = cost_row(64853, 409600, 12800, 51200, 50, PRICES)
    total = combine([nli, docile], PRICES)
    assert Decimal(nli["maximum_bounded_total_usd"]) == Decimal("0.4816896")
    assert Decimal(docile["maximum_bounded_total_usd"]) == Decimal("0.25088")
    assert Decimal(total["maximum_bounded_total_usd"]) == Decimal("0.7325696")
    assert total["generation_attempts"] == 74
    assert Decimal(total["expected_total_usd"]) == Decimal("0.1831142")
    assert not any(isinstance(v, float) for v in total.values())


@pytest.mark.parametrize(
    "tokens,price",
    [(-1, "0.3"), (True, "0.3"), (1.5, "0.3"), (1, "NaN"), (1, "Infinity"), (1, "-0.1"), (1, 0.3)],
)
def test_invalid_cost_inputs_rejected(tokens, price):
    with pytest.raises(ValueError):
        usd(tokens, price)


def test_estimate_does_not_masquerade_as_tokenizer_or_write_payload():
    spec = cost_spec()
    body = {"document_id": "fixture", "text": "Private synthetic marker"}
    first = request_estimate(body, "plan", spec)
    second = request_estimate(body, "synthesis", spec)
    assert first["fixed_overhead_bytes"] > 0
    assert second["prior_plan_expected_tokens"] == 1024
    assert "Private synthetic marker" not in json.dumps(first)
    assert "not exact tokenization" in spec["estimator"]
    assert len(encoded(body)) > len(body["text"])
    assert "OMITTED" in spec["sampling_parameters"]


def test_cap_violation_never_increases_frozen_limits():
    with pytest.raises(ValueError, match="EXCEEDS_FROZEN_CAP"):
        cost_row(8193, 8192, 256, 1024, 1, PRICES)
    assert Decimal(usd(1, "0.30")) == Decimal("0.0000003")


def test_scenario_totals_have_no_retries_or_sample_changes():
    plan = {
        "datasets": {
            "contract-nli": {
                "ids": {"scored": list(range(12))},
                "workload": {"per_request_input_limit": 32768, "per_request_output_limit": 4096},
            },
            "docile": {
                "ids": {"adapter": list(range(8)), "scored": list(range(50))},
                "workload": {"per_request_input_limit": 8192, "per_request_output_limit": 1024},
            },
        }
    }
    rows = []
    for tier, count in (("adapter", 3), ("scored", 12)):
        rows.extend(
            {
                "dataset": "contract-nli",
                "tier": tier,
                "plan": {"estimated_input_tokens": 1000},
                "synthesis": {"estimated_input_tokens": 2000},
            }
            for _ in range(count)
        )
    rows.extend(
        {"dataset": "docile", "tier": "scored", "extraction": {"estimated_input_tokens": 1000}}
        for _ in range(50)
    )
    costs = make_costs(rows, plan, cost_spec(), PRICES)
    assert costs["adapter_plus_scored"]["generation_attempts"] == 88
    assert costs["adapter_plus_scored"]["capped_input_tokens"] == 1458176
    assert costs["adapter_plus_scored"]["capped_output_tokens_including_thinking"] == 182272
    assert Decimal(costs["adapter_plus_scored"]["maximum_bounded_total_usd"]) == Decimal(
        "0.8931328"
    )
    assert costs["optional_full"]["combined"]["generation_attempts"] == 746


def test_provider_records_do_not_include_non_google_provider_sources():
    from urllib.parse import urlsplit

    for key, title, url, interpretation in REFERENCES:
        assert title and interpretation
        if key not in {"contract_rights", "docile_rights", "docile_notice"}:
            assert urlsplit(url).hostname in {"ai.google.dev", "business.safety.google"}
    assert len(PATTERNS) == 11
