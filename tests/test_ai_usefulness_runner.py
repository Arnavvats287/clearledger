"""Launcher privacy/offline guards, without a database or external provider."""

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess


def test_launcher_forces_offline_and_redacts_local_credentials(monkeypatch, capsys):
    path = Path(__file__).resolve().parents[1] / "scripts/evaluate_ai_usefulness.py"
    spec = importlib.util.spec_from_file_location("ai_usefulness_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    canary = "synthetic-launcher-secret-canary"
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", canary)
    monkeypatch.setenv("EXTERNAL_AI_ENABLED", "true")
    monkeypatch.setattr(
        module,
        "dotenv_values",
        lambda _: {
            "TEST_DATABASE_URL": "postgresql+psycopg://fixture.invalid/disposable",
            "GEMINI_API_KEY": canary,
        },
    )

    def child(command, **kwargs):
        env = kwargs["env"]
        assert env["GEMINI_API_KEY"] == ""
        assert env["EXTERNAL_AI_ENABLED"] == "false"
        assert env["INVESTIGATION_EXTERNAL_ENABLED"] == "false"
        assert env["EXTRACTION_PROVIDER"] == "disabled"
        assert "--require-postgres" in command
        assert kwargs["capture_output"] and kwargs["timeout"] == 300
        return CompletedProcess(command, 1, f"synthetic error {canary}", "")

    monkeypatch.setattr(module.subprocess, "run", child)
    assert module.main() == 1
    output = capsys.readouterr().out
    assert canary not in output and "<redacted>" in output
