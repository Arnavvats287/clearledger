"""Cross-platform complete verification: uv run --frozen python scripts/verify.py.

Runs the full suite against disposable PostgreSQL databases, never downgrading
the configured development database. Full output is saved locally, not streamed.
"""

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    env.setdefault("TEST_DATABASE_URL", dotenv_values(ROOT / ".env").get("TEST_DATABASE_URL") or "")
    if not env["TEST_DATABASE_URL"]:
        raise SystemExit(
            "Set TEST_DATABASE_URL to a local PostgreSQL role with CREATEDB permission"
        )
    # Avoid accessing the user's global cache on restricted local hosts.
    env.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache-clean"))
    logs = ROOT / "local-data" / "verification"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".log")
    uv = shutil.which("uv") or str(
        Path(sys.executable).with_name("uv.exe" if os.name == "nt" else "uv")
    )
    commands = [
        ("lock", [uv, "lock", "--check", "--offline"]),
        ("dependencies", [uv, "pip", "check"]),
        ("lint", [sys.executable, "-m", "ruff", "check", "."]),
        ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
        ("types", [sys.executable, "-m", "mypy"]),
        ("tests/migrations", [sys.executable, "-m", "pytest", "-ra", "--require-postgres"]),
    ]
    # Redact local connection strings/passwords if a failing tool echoes one.
    redactions = [env["TEST_DATABASE_URL"]]
    values = dotenv_values(ROOT / ".env")
    redactions.extend(
        value for key, value in values.items() if value and ("PASSWORD" in key or "URL" in key)
    )
    with log_path.open("w", encoding="utf-8") as log:
        for name, command in commands:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
            output = result.stdout + result.stderr
            for secret in redactions:
                output = output.replace(secret, "<redacted>")
            log.write(f"\n## {name}: {' '.join(command)}\n{output}\nexit={result.returncode}\n")
            log.flush()
            print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
            if result.returncode:
                raise SystemExit(f"Verification failed; inspect {log_path}")
    print(f"All required checks passed. Detailed log: {log_path}")


if __name__ == "__main__":
    main()
