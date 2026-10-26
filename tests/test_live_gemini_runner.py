"""Only refusal paths are exercised in CI; never an authorized live call."""

import importlib.util
from pathlib import Path

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
