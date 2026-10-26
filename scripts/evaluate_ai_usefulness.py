"""Offline-only actual-API synthetic evaluation; never runs a benchmark or Gemini.

Connection credentials are read locally and never emitted. pytest creates and drops
only its generated disposable databases. Results contain synthetic API observations
under ignored local-data/ai-usefulness; no independent evaluation files are read.
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def run_tests(targets):
    env = os.environ.copy()
    local = dotenv_values(ROOT / ".env")
    env["TEST_DATABASE_URL"] = env.get("TEST_DATABASE_URL") or (
        local.get("TEST_DATABASE_URL") or ""
    )
    if not env["TEST_DATABASE_URL"]:
        raise SystemExit("TEST_DATABASE_URL required; no test was executed")
    env.update(
        EXTERNAL_AI_ENABLED="false",
        INVESTIGATION_EXTERNAL_ENABLED="false",
        EXTRACTION_PROVIDER="disabled",
        INVESTIGATION_PROVIDER="deterministic",
        GEMINI_API_KEY="",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            "--require-postgres",
            "-q",
            "--tb=short",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    output = completed.stdout + completed.stderr
    for key, value in [*local.items(), *os.environ.items(), *env.items()]:
        if value and any(
            tag in key.upper() for tag in ("URL", "PASSWORD", "TOKEN", "KEY", "SECRET")
        ):
            output = output.replace(value, "<redacted>")
    print(output, end="")
    return completed.returncode


def main():
    return run_tests(["tests/test_ai_usefulness.py"])


if __name__ == "__main__":
    raise SystemExit(main())
