"""Exercise the documented migration and server commands against a disposable DB."""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from conftest import ROOT

pytestmark = pytest.mark.postgres


def test_cli_migration_and_live_server(disposable_database):
    env = os.environ.copy()
    env["DATABASE_URL"] = disposable_database.render_as_string(hide_password=False)
    for arguments in (("upgrade", "head"), ("current",), ("check",)):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        print(f"alembic {' '.join(arguments)}: {result.stdout.strip() or 'exit 0'}")

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "clearledger.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=1, trust_env=False
        ) as client:
            deadline = time.monotonic() + 15
            while True:
                assert server.poll() is None, "Uvicorn exited during startup"
                try:
                    response = client.get("/health")
                    break
                except httpx.TransportError:
                    if time.monotonic() >= deadline:
                        pytest.fail("Uvicorn failed to start within 15 seconds")
                    time.sleep(0.1)
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ready"}
            print('live HTTP: /health 200 {"status":"ok"}; /ready 200 {"status":"ready"}')
    finally:
        server.terminate()
        try:
            server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate(timeout=5)
