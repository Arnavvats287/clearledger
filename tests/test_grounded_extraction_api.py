"""Actual ingestion/extraction API; synthetic source, mocked SDK process, exact host checks."""

import pytest
from test_documents import documents_environment as documents_environment
from test_documents import extract, upload
from test_imports import environment as environment
from test_matching import financial_state, setup

from clearledger.extraction_provider import Gateway, GeminiTransport
from clearledger.grounded_extraction import RemittanceSelection, catalog, resolve_selection

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("fault", [None, "invented_id", "amount"])
def test_actual_api_grounding_and_unchanged_finances(documents_environment, monkeypatch, fault):
    from clearledger import document_runtime

    client = documents_environment[3]
    setup(client)
    before = financial_state(client)
    source = "Invoice I-1 payment includes a disputed damage deduction of INR 1.01."
    calls = []
    actual = document_runtime.run_worker

    def worker(module, body, timeout=10):
        if module != "clearledger.gemini_worker":
            return actual(module, body, timeout)
        calls.append(body)
        assert body["task"] == "remittance_grounded"
        assert body["source_context"]["source_id"].count("/") == 1
        c = catalog(body["pages"], **body["source_context"])
        invoice = next(i for i in c.items if i.value == "I-1")
        description = next(s for s in c.source.spans if s.text == body["pages"][0])
        amount = next(s for s in c.source.spans if s.text == "INR 1.01")
        choice = RemittanceSelection(
            invoice_candidate_ids=[invoice.candidate_id if fault != "invented_id" else "unknown"],
            utr_span_ids=[],
            claims=[
                dict(
                    category="damage",
                    description_span_id=description.span_id,
                    amount_paise=102 if fault == "amount" else 101,
                    amount_span_id=amount.span_id,
                    reason_code_span_id=None,
                )
            ],
            uncertainty="review",
            unparsed_span_ids=[],
        )
        try:
            resolved = resolve_selection(choice, c)
        except ValueError:
            return {"error": "PROVIDER_FAILED"}
        return {"json_text": resolved.model_dump_json(), "input_tokens": 100, "output_tokens": 100}

    monkeypatch.setattr(document_runtime, "run_worker", worker)
    settings = client.app.state.settings
    settings.external_ai_enabled = True
    settings.extraction_provider = "gemini"
    settings.privacy_review_reference = "approved-isolated-test"
    client.app.state.extraction_gateway = Gateway(
        GeminiTransport("unit-only-key", "gemini-3.5-flash-lite", task="remittance_grounded"),
        attempts=1,
    )
    document = upload(client, source.encode()).json()
    response = extract(client, document["id"], allow_external=True)
    assert response.status_code == 200, response.text
    result = response.json()
    if fault is None:
        assert result["status"] == "NEEDS_REVIEW"
        facts = result["result"]
        assert facts["invoice_references"][0]["value"] == "I-1"
        assert facts["claims"][0]["amount_paise"] == 101
        assert facts["claims"][0]["reason_code"] is None
    else:
        assert result["status"] == "FAILED"
    assert len(calls) == 1 and financial_state(client) == before
