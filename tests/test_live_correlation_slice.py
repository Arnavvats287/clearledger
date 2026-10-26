"""Offline actual-API rehearsal only; scripted extraction is not live AI evidence."""

import json
from pathlib import Path

import pytest
from test_documents import enable_fake, extract, upload
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment
from test_matching import financial_state

from clearledger.extraction_provider import ProviderReply

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("repeat_reference", [False, True])
def test_synthetic_vertical_slice_rehearsal(documents_environment, monkeypatch, repeat_reference):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from live_correlation_slice import RAW, finish, prepare

    env = documents_environment
    api = env[3]
    prepare(api, env[0], env[1], api.app.state.settings)
    before = financial_state(api)
    doc = upload(api, RAW.encode()).json()

    def span(quote):
        start = RAW.index(quote)
        return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

    result = {
        "invoice_references": [{"value": "I-1", "span": span("I-1")}],
        "utr_references": [
            {
                "value": "t",
                "span": {
                    "page": 1,
                    "start": RAW.index("UTR: t") + 5,
                    "end": RAW.index("UTR: t") + 6,
                    "quote": "t",
                },
            }
        ],
        "payer_hint": None,
        "claims": [
            {
                "category": "damage",
                "description": span("damage INR 1.01 disputed"),
                "amount_paise": 101,
                "amount_span": span("INR 1.01"),
                "reason_code": None,
            }
        ],
        "uncertainty": "review",
        "unparsed_fields": [],
    }
    if repeat_reference:
        start = RAW.rindex("I-1")
        result["invoice_references"].append(
            {"value": "I-1", "span": {"page": 1, "start": start, "end": start + 3, "quote": "I-1"}}
        )
    enable_fake(api, [ProviderReply(json.dumps(result), 100, 100, 1)])
    extracted = extract(api, doc["id"], allow_external=True).json()
    assert extracted["status"] in {"SUCCEEDED", "NEEDS_REVIEW"}
    observation = finish(env, doc, extracted)
    assert observation["same_financial_and_claim_ids"]
    assert observation["no_allocations_settlements_journals"]
    assert financial_state(api) == before
