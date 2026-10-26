"""Preflight wiring regressions; real restricted image checks run after every build."""

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_chronological_image import SCRIPTS  # noqa: E402
from verify_chronological_startup import MODULES, OPERATOR_ARGV, TRANSITIVE, verify  # noqa: E402


def test_exact_operator_startup_and_transitive_probe(monkeypatch):
    commands = []

    def execute(argv, **kwargs):
        assert kwargs["input"] == "" and kwargs["timeout"] == 45
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv and "--cap-drop=ALL" in argv
        commands.append(argv)
        return CompletedProcess(
            argv,
            0,
            "" if len(commands) == 1 else json.dumps({"isolated": True, "module_origins": {}}),
            "",
        )

    monkeypatch.setattr("verify_chronological_startup.subprocess.run", execute)
    assert OPERATOR_ARGV == [
        "/app/.venv/bin/python",
        "-X",
        "utf8",
        "-I",
        "-B",
        "/app/scripts/chronological_adapter.py",
    ]
    assert verify()["eof_startup"] == "PASS"
    index = commands[0].index("--entrypoint")
    assert commands[0][index + 1] == OPERATOR_ARGV[0]
    assert commands[0][index + 3 :] == OPERATOR_ARGV[1:]
    assert all(name in commands[1][-1] for name in MODULES + TRANSITIVE)


@pytest.mark.parametrize("status,stdout", [(1, ""), (0, "unexpected output")])
def test_preflight_fails_closed_without_running_later_probe(monkeypatch, status, stdout):
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        return CompletedProcess(argv, status, stdout, "missing transitive dependency")

    monkeypatch.setattr("verify_chronological_startup.subprocess.run", execute)
    with pytest.raises(RuntimeError):
        verify()
    assert len(calls) == 1


def test_preflight_covers_every_allowlisted_helper():
    assert set(MODULES) == {Path(name).stem for name in SCRIPTS}
    assert "chronological_resources" not in MODULES
