"""Trusted disposable-resource verifier; reads ONLY the explicitly supplied public bridge.

No benchmark files, schedule, labels or operator modules. Uses tiny existing code-test rows.
Admin credentials stay in this trusted parent, never in bridge/adapter/API environments.
"""

import argparse
import copy
import json
import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from chronological_resources import owned_database
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_chronological_evaluation import message  # noqa: E402
from test_imports import BANK, csv_bytes  # noqa: E402


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("OWNED_DOCKER_OPERATION_FAILED")
    return result.stdout.strip()


def owned(kind, name, token):
    labels = json.loads(
        docker(
            kind,
            "inspect",
            "--format",
            "{{json .Labels}}" if kind == "network" else "{{json .Config.Labels}}",
            name,
        )
    )
    if labels.get("com.clearledger.chrono-run") != token:
        raise RuntimeError("REFUSE_UNOWNED_RESOURCE")


@contextmanager
def isolated_postgres(token, output):
    network, container = "cl_chrono_net_" + token, "cl_chrono_pg_" + token
    made_network = made_container = False
    try:
        docker(
            "network",
            "create",
            "--internal",
            "--label",
            "com.clearledger.chrono-run=" + token,
            network,
        )
        made_network = True
        password = secrets.token_hex(24)
        envfile = output / "private-postgres.env"
        envfile.write_text(
            "POSTGRES_USER=chrono_admin\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD="
            + password
            + "\n",
            encoding="utf-8",
        )
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        docker(
            "create",
            "--name",
            container,
            "--network",
            "bridge",
            "--label",
            "com.clearledger.chrono-run=" + token,
            "--env-file",
            str(envfile),
            "--publish",
            f"127.0.0.1:{port}:5432",
            "postgres:16.15-bookworm",
        )
        made_container = True
        docker("network", "connect", network, container)
        envfile.unlink()  # Generated credential file only, not user configuration.
        docker("start", container)
        for _ in range(60):
            result = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "chrono_admin", "-d", "postgres"],
                capture_output=True,
            )
            if result.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("ISOLATED_PG_NOT_READY")
        yield (
            f"postgresql+psycopg://chrono_admin:{password}@127.0.0.1:{port}/postgres",
            network,
            container,
        )
    finally:
        if made_container:
            owned("container", container, token)
            docker("rm", "--force", "--volumes", container)
        if made_network:
            owned("network", network, token)
            docker("network", "rm", network)


def verify(bridge, admin_url, output, *, network=None, postgres=None, token=None):
    from chronological_protocol import canonical

    with owned_database(admin_url) as url:
        visible = output / "current-input"
        visible.mkdir()
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "TEMP", "TMP"}
        }
        env.update(PYTHONUTF8="1", CL_INPUT_ROOT=str(visible))
        runner = None
        if network:
            runner = "cl_chrono_app_" + token
            state = output / "private-state"
            state.mkdir()
            envfile = output / "private-app.env"
            envfile.write_text(
                "DATABASE_URL="
                + url.set(host=postgres, port=5432).render_as_string(hide_password=False)
                + "\n",
                encoding="utf-8",
            )
            argv = [
                "docker",
                "run",
                "--interactive",
                "--name",
                runner,
                "--network",
                network,
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--memory=1g",
                "--cpus=2",
                "--pids-limit=128",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m,uid=10001,gid=10001",
                "--mount",
                f"type=bind,source={state},target=/state",
                "--label",
                "com.clearledger.chrono-run=" + token,
                "--env-file",
                str(envfile),
                "clearledger-chronological:local",
            ]
        else:
            env.update(
                DATABASE_URL=url.render_as_string(hide_password=False),
                CL_ADAPTER_OUTPUT=str(output / "private-provenance"),
            )
            argv = [sys.executable, "scripts/chronological_adapter.py"]
        env["CL_HARNESS_COMMAND_JSON"] = json.dumps(argv)
        responses = []
        with (output / "bridge.stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", str(bridge)],
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
                encoding="utf-8",
            )
            lines = queue.Queue()

            def receive():
                for line in process.stdout:
                    lines.put(line)
                lines.put(None)

            thread = threading.Thread(target=receive, daemon=True)
            thread.start()
            try:
                first = message()
                # Non-ASCII scope exercises bridge's Windows UTF-8 subprocess boundary.
                first["company"] = "unit-é"
                tied = copy.deepcopy(first)
                tied["request"].update(
                    request_id=str(uuid4()),
                    snapshot_id=str(uuid4()),
                    transaction={
                        **first["request"]["transaction"],
                        "external_transaction_id": "t2",
                    },
                )
                tied["nonce"] = str(uuid4())
                later = copy.deepcopy(tied)
                later["request"].update(
                    as_of="2026-01-20T12:00:00+05:30",
                    request_id=str(uuid4()),
                    snapshot_id=str(uuid4()),
                )
                later["nonce"] = str(uuid4())
                raw = csv_bytes(
                    "bank-transactions",
                    {**BANK, "payer_name": "Test Alias"},
                    {**BANK, "payer_name": "Test Alias", "external_transaction_id": "t2"},
                )
                import base64

                from application_eval_inputs import sha

                later["payload"]["imports/bank-transactions.csv"] = base64.b64encode(raw).decode()
                later["manifest"]["imports/bank-transactions.csv"] = sha(raw)
                doc = canonical(
                    {
                        "remittance_version": "1.0",
                        "invoice_references": ["i"],
                        "utr_references": ["t2"],
                        "payer_hint": None,
                        "claims": [],
                    }
                )
                name = "app_visible/correlation_sources/unit.json"
                later["payload"][name] = base64.b64encode(doc).decode()
                later["manifest"][name] = sha(doc)
                later["files"] = ["imports/bank-transactions.csv", name]
                for m in (first, tied, later, later):
                    for name, encoded in m["payload"].items():
                        target = visible / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(base64.b64decode(encoded))
                    wire = {**m, "payload": {}}
                    process.stdin.write(canonical(wire).decode() + "\n")
                    process.stdin.flush()
                    line = lines.get(timeout=120)
                    if line is None:
                        raise RuntimeError("BRIDGE_EXITED")
                    response = json.loads(line)
                    assert response["status"] == "ABSTAIN", response
                    assert response["financial_mutation_check"] == "PASS", response
                    assert response["prediction"]["as_of"] == m["request"]["as_of"]
                    assert response["nonce"] == m["nonce"] and response["mode"] == "REAL_API"
                    responses.append(response)
                assert not responses[1]["api_observations"]["receipt_available"]
                assert responses[2]["api_observations"]["receipt_available"]
                assert responses[2]["api_observations"]["imports"] == [
                    {"kind": "bank-transactions", "new_rows": 1}
                ]
                assert responses[2] == responses[3]
                process.stdin.close()
                assert process.wait(timeout=15) == 0
                thread.join(timeout=2)
                assert lines.get_nowait() is None, "Unexpected non-protocol stdout"
                (output / "responses.json").write_bytes(canonical(responses))
                if runner:
                    owned("container", runner, token)
                    assert (state / "run").is_dir()
            finally:
                if process.poll() is None:
                    process.stdin.close()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                process.stdout.close()
                if runner:
                    owned("container", runner, token)
                    docker("rm", "--force", runner)
                    envfile.unlink(missing_ok=True)
        return {
            "responses": len(responses),
            "distinct_stages": 3,
            "replay": "IDENTICAL",
            "financial_mutation_check": "PASS",
            "gemini": "DISABLED",
            "max_stage_elapsed_ns": max(r["elapsed_ns"] for r in responses),
            "scope": "minimal isolated API fixtures; no benchmark accuracy",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    token = uuid4().hex
    output = ROOT / "local-data/chronological-verification" / token
    output.mkdir(parents=True)
    try:
        if args.docker:
            with isolated_postgres(token, output) as (url, network, pg):
                result = verify(args.bridge, url, output, network=network, postgres=pg, token=token)
        else:
            url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
                "TEST_DATABASE_URL"
            )
            result = verify(args.bridge, url, output)
        (output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Chronological bridge PASS:", json.dumps(result), "logs:", output)
    except Exception as exc:
        # No SQL exception bodies/credentials in diagnostics.
        print("Chronological bridge FAILED:", type(exc).__name__, "logs:", output)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
