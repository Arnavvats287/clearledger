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
