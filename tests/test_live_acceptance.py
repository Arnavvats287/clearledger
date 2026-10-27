"""Offline full-scope rehearsal; these scripted outputs are never live AI evidence."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr
from test_ai_investigator import ScriptedAR
from test_evidence import documents_environment as documents_environment
from test_evidence import environment as environment

from clearledger.extraction_provider import Gateway, GeminiTransport, ProviderReply


def test_rebalanced_request_cost_reservation_and_output_boundary():
    from clearledger.extraction_provider import ProviderRunError

    assert (2048 * 3960 + 768 * 33000 + 999999) // 1000000 == 34

    class Offline:
        def __init__(self, tokens):
            self.tokens = tokens

        def generate(self, pages):
            return ProviderReply("{}", 100, self.tokens, 100 + self.tokens)

    for tokens in (768, 769):
        gateway = Gateway(Offline(tokens), attempts=1, max_input_tokens=2048, max_output_tokens=768)
        if tokens == 768:
            reply, _ = gateway.generate(["synthetic"])
            assert reply.output_tokens == 768
        else:
            with pytest.raises(ProviderRunError):
                gateway.generate(["synthetic"])


@pytest.mark.parametrize("include_context", [False, True])
def test_supported_synthesis_requires_contextual_remittance_citation(include_context):
    from clearledger.case_domain import CaseError
    from clearledger.investigation_ai import validate_synthesis
    from clearledger.investigation_ai_contract import Synthesis

    records = [uuid4() for _ in range(3)]
    summaries = [
        {"record_id": str(r), "kind": k, "facts": {"damaged_quantity": 1}}
        for r, k in zip(records, ["WMS", "POD", "REMITTANCE"], strict=True)
    ]
    value = Synthesis(
        amount_paise=101,
        state="SUPPORTED",
        next_action="HUMAN_REVIEW",
        uncertainty="NONE",
        rationale="Verified required evidence supports the claimed amount.",
        confidence="HIGH",
        record_ids=records if include_context else records[:2],
        observations=[{"record_id": records[0], "field": "damaged_quantity", "value": 1}],
        missing_evidence_types=[],
        financial_authority=False,
    )
    objective = SimpleNamespace(question="DELIVERY_DAMAGE", amount_paise=101)
    finding = SimpleNamespace(
        state="SUPPORTED",
        contradictions=[],
        unknowns=[],
        citations=[SimpleNamespace(record_id=r) for r in records],
    )
    if include_context:
        validate_synthesis(value, objective, finding, summaries)
    else:
        with pytest.raises(CaseError, match="INVALID_AI_SYNTHESIS"):
            validate_synthesis(value, objective, finding, summaries)


@pytest.mark.postgres
@pytest.mark.parametrize("spent", [0, 8, 15, 20])
def test_combined_acceptance_rehearsal(documents_environment, monkeypatch, tmp_path, spent):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import live_acceptance
    import live_investigator_smoke

    env = documents_environment
    api, settings = env[3], env[3].app.state.settings
    model = ScriptedAR()
    calls = []

    def generate(self, pages):
        calls.append(self.task)
        if self.task == "investigation_ar":
            value = model.reason(json.loads(pages[0]))
        else:
            page = pages[0]

            def span(quote):
                start = page.index(quote)
                return {"page": 1, "start": start, "end": start + len(quote), "quote": quote}

            value = {
                "invoice_references": [{"value": "I-1", "span": span("I-1")}],
                "utr_references": [],
                "payer_hint": None,
                "claims": [],
                "uncertainty": "none",
                "unparsed_fields": [],
            }
            if "UTR: t" in page:
                start = page.index("UTR: t") + 5
                value["utr_references"] = [
                    {
                        "value": "t",
                        "span": {"page": 1, "start": start, "end": start + 1, "quote": "t"},
                    }
                ]
            if "damage" in page or "rebate" in page:
                category = "rebate" if "rebate" in page else "damage"
                amount = 101 if "INR 1.01" in page else None
                value["claims"] = [
                    {
                        "category": category,
                        "description": {"page": 1, "start": 0, "end": len(page), "quote": page},
                        "amount_paise": amount,
                        "amount_span": span("INR 1.01") if amount else None,
                        "reason_code": None,
                    }
                ]
        return ProviderReply(json.dumps(value), 100, 100, 200)

    monkeypatch.setattr(GeminiTransport, "generate", generate)
    monkeypatch.setattr(live_investigator_smoke.time, "sleep", lambda _: None)
    settings.external_ai_enabled = True
    settings.privacy_review_reference = "unit-approved-synthetic"
    settings.gemini_api_key = SecretStr("isolated-unit-key")
    settings.gemini_model = "isolated-unit-model"
    settings.extraction_provider = "gemini"
    settings.llm_max_input_tokens = 2048
    settings.llm_max_output_tokens = 768
    settings.llm_input_paise_per_million_tokens = 3960
    settings.llm_output_paise_per_million_tokens = 33000
    settings.llm_max_cost_paise_per_attempt = 34
    settings.llm_daily_requests = 60
    settings.llm_daily_input_tokens = 61440
    settings.llm_daily_output_tokens = 10240
    settings.llm_shared_requests_per_minute = 60
    settings.llm_requests_per_minute = 60
    api.app.state.extraction_gateway = Gateway(
        GeminiTransport(
            "isolated-unit-key",
            "isolated-unit-model",
            30000,
            max_input_tokens=2048,
            max_output_tokens=768,
        ),
        attempts=1,
        requests_per_minute=60,
        input_rate=3960,
        output_rate=33000,
        max_input_tokens=2048,
        max_output_tokens=768,
    )
    output = tmp_path / "observations"
    output.mkdir()
    report = {
        "provider": "offline-control",
        "maximum_attempts": 20,
        "attempt_cost_cap_paise": 34,
        "maximum_reserved_paise": 600,
        "remaining_authorized_cap_paise": 600,
    }
    budget = tmp_path / "budget.json"
    if spent:
        budget.write_text(
            json.dumps(
                {
                    "cap_paise": 600,
                    "cap_attempts": 20,
                    "reservations": [
                        {
                            "ordinal": i + 1,
                            "paise": 34 if spent == 15 and i >= 8 else 30,
                            "report_id": "prior",
                        }
                        for i in range(spent)
                    ],
                }
            )
        )
    passed = live_acceptance.acceptance(
        api,
        env[0],
        env[1],
        settings,
        report,
        output,
        ledger_path=budget,
        variations_only=spent == 15,
    )
    if spent == 20:
        assert not passed and calls == [] and report["global_reserved_attempts"] == 20
        assert report["financial_nonmutation"]
        return
    assert passed, report
    if spent == 15:
        assert len(calls) == 3 and report["global_reserved_attempts"] == 18
        assert report["financial_nonmutation"]
        assert report["global_reserved_paise"] == 580
        assert "investigation_cases" not in report and "automation" not in report
        return
    assert len(calls) == 9 and report["global_reserved_attempts"] == 9 + spent
    assert report["global_reserved_paise"] == 306 + spent * 30
    assert report["confirmation_replay_same_id_no_work"]
    assert report["financial_nonmutation"]
    assert [c["expected_result_correct"] for c in report["investigation_cases"]] == [True] * 3


def test_new_authorization_cannot_be_mixed_with_old_mode_before_key(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import live_gemini_smoke as runner

    def prohibited(*args, **kwargs):
        pytest.fail("Invalid mixed scope must refuse before credentials or external calls")

    monkeypatch.setattr(runner, "dotenv_values", prohibited)
    monkeypatch.setattr(runner.httpx, "Client", prohibited)
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "live_gemini_smoke.py",
            "--authorized-live",
            "--model",
            "gemini-3.5-flash-lite",
            "--confirmed-rpm",
            "15",
            "--confirmed-tpm",
            "250000",
            "--remaining-rpd",
            "480",
            "--remaining-budget-paise",
            "600",
            "--acceptance-campaign",
            "--investigator-campaign",
        ],
    )
    with pytest.raises(SystemExit):
        runner.main()
