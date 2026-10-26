"""Offline campaign guard tests; no key, database or external HTTP."""

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("status,expected_calls", [(400, 1), (503, 3), (429, 3), (200, 1)])
def test_campaign_counts_reservations_and_bounds_retries(
    monkeypatch, tmp_path, status, expected_calls
):
    from google import genai
    from google.genai import errors

    spec = importlib.util.spec_from_file_location(
        "campaign_under_test", Path(__file__).resolve().parents[1] / "scripts/diagnose_gemini.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STORE = tmp_path
    calls = []

    class ReviewedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 27)

    class Public:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                content=b'<root><Cube time="2026-10-27"><Cube currency="INR" rate="95"/>'
                b'<Cube currency="USD" rate="1"/></Cube></root>',
            )

    class Fake(Public):
        def __init__(self, **kwargs):
            assert kwargs["http_options"].retry_options.attempts == 1
            self.models = self

        def get(self, **kwargs):
            return SimpleNamespace(
                name="models/" + module.MODEL,
                supported_actions=["generateContent"],
                input_token_limit=2048,
                output_token_limit=512,
            )

        def count_tokens(self, **kwargs):
            return SimpleNamespace(total_tokens=100)

        def generate_content(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["config"].automatic_function_calling.disable
            assert kwargs["config"].tools == []
            ledger = json.loads((tmp_path / "ledger.json").read_text())
            assert len(ledger["attempts"]) == len(calls)
            assert ledger["attempts"][-1]["reserved_paise"] == 17
            if status != 200:
                raise errors.APIError(
                    status,
                    {
                        "error": {
                            "status": {
                                400: "INVALID_ARGUMENT",
                                503: "UNAVAILABLE",
                                429: "RESOURCE_EXHAUSTED",
                            }[status],
                            "message": "PRIVATE-RAW-BODY-DO-NOT-STORE",
                        }
                    },
                )
            return SimpleNamespace(text="OK", usage_metadata=None)

    monkeypatch.setattr(module, "date", ReviewedDate)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-key-not-a-secret")
    monkeypatch.setattr(module.httpx, "Client", Public)
    monkeypatch.setattr(genai, "Client", Fake)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module.logging, "disable", lambda _: None)
    monkeypatch.setattr(module.sys, "argv", ["campaign", "--authorized-live", "--stage", "1"])
    assert module.main() == (0 if status == 200 else 1)
    assert len(calls) == expected_calls
    stored = (tmp_path / "ledger.json").read_text()
    assert "PRIVATE-RAW-BODY" not in stored and "offline-key-not-a-secret" not in stored
    assert not (tmp_path / "active.lock").exists()
    # Reinvocation cannot repeat a rejected request, a successful stage or an outage.
    with pytest.raises(SystemExit):
        module.main()
    assert len(calls) == expected_calls


def test_matrix_changes_only_mime_then_schema(monkeypatch):
    import sys

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import diagnose_gemini

    contents2, config2 = diagnose_gemini.request(2)
    contents3, config3 = diagnose_gemini.request(3)
    contents4, config4 = diagnose_gemini.request(4)
    assert contents2 == contents3 == contents4
    assert config3 == {**config2, "response_mime_type": "application/json"}
    assert config4 == {**config3, "response_json_schema": diagnose_gemini.SIMPLE_SCHEMA}
    assert diagnose_gemini.request(5)[1]["response_json_schema"]
    assert sys.modules["diagnose_gemini"]


def test_alternative_has_own_prices_timeout_and_fails_before_key_without_quota(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import diagnose_gemini as module

    class ReviewedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 27)

    monkeypatch.setattr(module, "date", ReviewedDate)

    for stage, reservation in [(1, 13), (2, 26), (5, 26)]:
        input_rate, output_rate, output, timeout, previous, attempts = module.profile(
            "gemini-3.5-flash-lite", stage
        )
        assert (input_rate, output_rate, timeout, previous, attempts) == (
            3960,
            33000,
            30000,
            102,
            17,
        )
        assert (2048 * input_rate + output * output_rate + 999999) // 1000000 == reservation
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["campaign", "--authorized-live", "--stage", "1", "--model", "gemini-3.5-flash-lite"],
    )

    def prohibited(*args, **kwargs):
        pytest.fail("No credential access or network before model-specific quota gate")

    monkeypatch.setattr(module, "dotenv_values", prohibited)
    monkeypatch.setattr(module.httpx, "Client", prohibited)
    with pytest.raises(SystemExit, match="MODEL_SPECIFIC_QUOTA_CONFIRMATION_REQUIRED"):
        module.main()


def test_prompt_distinguishes_page_number_from_character_offset():
    from clearledger.gemini_schema import PROVIDER_SCHEMA_VERSION
    from clearledger.gemini_worker import SYSTEM_INSTRUCTION

    assert "first supplied page is page 1" in SYSTEM_INSTRUCTION
    assert "zero-based Unicode positions; end is exclusive" in SYSTEM_INSTRUCTION
    assert "inside description on the same page" in SYSTEM_INSTRUCTION
    assert PROVIDER_SCHEMA_VERSION == "gemini-remittance-shape-v4"


def test_token_boundaries_are_exact_unicode_slices_of_projected_pages():
    from clearledger.document_privacy import project
    from clearledger.gemini_schema import remittance_contents

    pages = project(["Invoice I-1: damage INR 1.01; review required."]).pages
    body = json.loads(remittance_contents(pages))
    assert body["untrusted_pages"] == pages
    assert body["source_token_boundaries"]
    for page, start, end, quote in body["source_token_boundaries"]:
        assert pages[page - 1][start:end] == quote
    assert [1, 8, 11, "I-1"] in body["source_token_boundaries"]
    assert "review" not in json.dumps(body)
    assert (
        len(json.loads(remittance_contents(["Invoice I-1 " * 600]))["source_token_boundaries"])
        == 512
    )


def test_stopped_alternative_campaign_refuses_before_credential_access(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import diagnose_gemini as module

    class ReviewedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 27)

    monkeypatch.setattr(module, "date", ReviewedDate)
    monkeypatch.setattr(module, "STORE", tmp_path)
    store = tmp_path / "alternative-35"
    store.mkdir()
    (store / "ledger.json").write_text(json.dumps({"campaign_stopped": "DONE", "attempts": []}))
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "campaign",
            "--authorized-live",
            "--stage",
            "1",
            "--model",
            "gemini-3.5-flash-lite",
            "--confirmed-rpm",
            "15",
            "--confirmed-tpm",
            "250000",
            "--confirmed-rpd",
            "500",
        ],
    )
    monkeypatch.setattr(module, "dotenv_values", lambda *_: pytest.fail("Credential access"))
    with pytest.raises(SystemExit, match="CAMPAIGN_STOPPED"):
        module.main()
