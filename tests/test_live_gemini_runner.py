"""Only refusal paths are exercised in CI; never an authorized live call."""

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    "arguments",
    [
        ["--confirmed-rpm", "15", "--confirmed-tpm", "250000", "--remaining-rpd", "500"],
        [
            "--authorized-live",
            "--confirmed-rpm",
            "2",
            "--confirmed-tpm",
            "250000",
            "--remaining-rpd",
            "500",
        ],
        [
            "--authorized-live",
            "--confirmed-rpm",
            "15",
            "--confirmed-tpm",
            "1024",
            "--remaining-rpd",
            "500",
        ],
        [
            "--authorized-live",
            "--confirmed-rpm",
            "15",
            "--confirmed-tpm",
            "250000",
            "--remaining-rpd",
            "3",
        ],
    ],
)
def test_no_authorization_or_insufficient_quota_never_reads_key_or_calls_provider(
    monkeypatch, arguments
):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "live_smoke_refusal", scripts / "live_gemini_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def prohibited(*args, **kwargs):
        pytest.fail("Refusal must occur before credential access or any HTTP call")

    monkeypatch.setattr(module, "dotenv_values", prohibited)
    monkeypatch.setattr(module.httpx, "Client", prohibited)
    monkeypatch.setattr(module.sys, "argv", ["live_gemini_smoke.py", *arguments])
    with pytest.raises(SystemExit):
        module.main()


@pytest.mark.parametrize("provider_status", ["INVALID_ARGUMENT", "FAILED_PRECONDITION"])
def test_metadata_failure_reports_only_safe_provider_status(
    monkeypatch, tmp_path, capsys, provider_status
):
    from google import genai
    from google.genai.errors import APIError

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "live_smoke_status", scripts / "live_gemini_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    canary = "PRIVATE-KEY-PROMPT-BODY-https://secret.invalid"

    class ReviewedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 27)

    class PublicFX:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                content=(
                    b'<root><Cube time="2026-10-27"><Cube currency="INR" rate="95"/>'
                    b'<Cube currency="USD" rate="1"/></Cube></root>'
                ),
            )

    class Metadata(PublicFX):
        def __init__(self, **kwargs):
            self.models = self

        def get(self, **kwargs):
            raise APIError(400, {"error": {"status": provider_status, "message": canary}})

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "date", ReviewedDate)
    monkeypatch.setattr(
        module,
        "dotenv_values",
        lambda _: {
            "GEMINI_API_KEY": canary,
            "TEST_DATABASE_URL": "postgresql+psycopg://unused/unused",
        },
    )
    monkeypatch.setenv("GEMINI_API_KEY", canary)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(module.httpx, "Client", PublicFX)
    monkeypatch.setattr(genai, "Client", Metadata)
    monkeypatch.setattr(module.logging, "disable", lambda _: None)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "live_gemini_smoke.py",
            "--authorized-live",
            "--confirmed-rpm",
            "15",
            "--confirmed-tpm",
            "250000",
            "--remaining-rpd",
            "492",
        ],
    )
    assert module.main() == 1
    report = json.loads(
        next((tmp_path / "local-data/live-gemini").glob("*/observations.json")).read_text()
    )
    assert report["preflight_diagnostic"] == {
        "phase": "MODEL_LOOKUP",
        "exception_category": "HTTP_API",
        "http_status": 400,
        "provider_status": provider_status,
    }
    assert report["cases"] == [] and report["external_settings_disabled"]
    assert canary not in json.dumps(report) + capsys.readouterr().out
