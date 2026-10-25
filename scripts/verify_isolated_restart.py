"""Run the G2 restart test on a new labelled PostgreSQL container and named volume.

Never invokes Compose, restarts the shared development container or reuses .env.
Only resources created by this invocation and bearing its UUID labels are removed.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "postgres:16.15-bookworm"
PURPOSE = "restart-verification"


def docker(*arguments, timeout=30):
    return subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    ).stdout.strip()


def assert_owned(resource, name, token):
    template = "{{json .Config.Labels}}" if resource == "container" else "{{json .Labels}}"
    labels = json.loads(docker(resource, "inspect", "--format", template, name))
    if (
        labels.get("com.clearledger.test-run") != token
        or labels.get("com.clearledger.purpose") != PURPOSE
    ):
        raise RuntimeError("Refusing to change/remove an unowned Docker resource")


def main():
    # Require an available engine/cached image. Failure is explicit, never a skip
    # or an automatic fallback to the development container.
    docker("info", "--format", "{{.ServerVersion}}")
    docker("image", "inspect", IMAGE, "--format", "{{.Id}}")
    token = uuid4().hex
    container = f"clearledger_restart_test_{token}"
    volume = f"{container}_data"
    password = secrets.token_hex(24)
    created_container = created_volume = False
    logs = ROOT / "local-data" / "verification"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / (
        "isolated-restart-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".log"
    )
    try:
        # UUID namespace plus explicit absence/label checks protect existing data.
        existing = subprocess.run(
            ["docker", "volume", "inspect", volume], capture_output=True, timeout=15
        )
        if existing.returncode == 0:
            raise RuntimeError("Refusing to reuse an existing volume")
        docker(
            "volume",
            "create",
            "--label",
            f"com.clearledger.test-run={token}",
            "--label",
            f"com.clearledger.purpose={PURPOSE}",
            volume,
        )
        created_volume = True
        assert_owned("volume", volume, token)
        # Choose a free port once, then bind it explicitly. Docker's empty host
        # port syntax may assign a different port on container restart.
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            host_port = reservation.getsockname()[1]
        # Credentials never appear in command arguments, output or repository files.
        with tempfile.TemporaryDirectory(prefix="clearledger-restart-env-") as directory:
            env_file = Path(directory) / "postgres.env"
            env_file.write_text(
                f"POSTGRES_USER=clearledger_restart\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD={password}\n",
                encoding="utf-8",
            )
            docker(
                "create",
                "--name",
                container,
                "--label",
                f"com.clearledger.test-run={token}",
                "--label",
                f"com.clearledger.purpose={PURPOSE}",
                "--env-file",
                str(env_file),
                "--mount",
                f"type=volume,source={volume},target=/var/lib/postgresql/data",
                "--publish",
                f"127.0.0.1:{host_port}:5432",
                "--health-cmd",
                "pg_isready -U clearledger_restart -d postgres",
                "--health-interval",
                "1s",
                "--health-timeout",
                "3s",
                "--health-retries",
                "30",
                IMAGE,
            )
            created_container = True
        assert_owned("container", container, token)
        docker("start", container)
        deadline = time.monotonic() + 60
        while docker("inspect", "--format", "{{.State.Health.Status}}", container) != "healthy":
            if time.monotonic() >= deadline:
                raise RuntimeError("Isolated PostgreSQL failed to become healthy")
            time.sleep(0.2)
        binding = json.loads(
            docker(
                "inspect",
                "--format",
                '{{json (index .NetworkSettings.Ports "5432/tcp")}}',
                container,
            )
        )
        if len(binding) != 1 or binding[0]["HostIp"] != "127.0.0.1":
            raise RuntimeError("Expected a single IPv4 loopback port")
        url = f"postgresql+psycopg://clearledger_restart:{password}@127.0.0.1:{binding[0]['HostPort']}/postgres"
        env = {**os.environ, "TEST_DATABASE_URL": url}
        print(
            "Owned isolated PostgreSQL is healthy; running real process/container restart test",
            flush=True,
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_restart_persistence.py",
                "tests/test_finance_restart.py",
                "tests/test_review_restart.py",
                "-q",
                "--require-postgres",
                "--isolated-restart-container",
                container,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        log_path.write_text(
            (result.stdout + result.stderr)
            .replace(url, "<redacted>")
            .replace(password, "<redacted>")
            + f"\nexit={result.returncode}\n",
            encoding="utf-8",
        )
        if result.returncode:
            raise SystemExit(f"Isolated restart verification FAILED. Detailed log: {log_path}")
        print(f"Isolated restart verification PASS. Detailed log: {log_path}")
    finally:
        if created_container:
            assert_owned("container", container, token)
            docker("rm", "--force", container)
        if created_volume:
            assert_owned("volume", volume, token)
            docker("volume", "rm", volume)
        if created_container or created_volume:
            print("Only this invocation's labelled disposable resources were removed", flush=True)


if __name__ == "__main__":
    main()
