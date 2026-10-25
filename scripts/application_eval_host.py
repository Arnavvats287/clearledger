"""Owned disposable host and real role-authenticated HTTP, with no financial adapter."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from uuid import uuid4

import httpx
from alembic import command
from alembic.config import Config
from pilot_runtime import ROOT, disposable_database, fingerprint, rows
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from clearledger.case_models import OutboxEvent
from clearledger.models import Organization
from clearledger.review_users import provision


def initialize(url):
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            cfg = Config(str(ROOT / "alembic.ini"))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            command.check(cfg)
            connection.commit()
        org, password = uuid4(), secrets.token_urlsafe(32)
        with Session(engine) as session:
            session.add(Organization(id=org, name="Disposable application evaluation"))
            session.commit()
            provision(session, org, "snapshot-operator", "AR_ANALYST", password)
        return engine, org, password
    except BaseException:
        engine.dispose()
        raise


def environment(url, org, store):
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "TEMP", "TMP"}
    }
    env.update(
        DATABASE_URL=url,
        ORGANIZATION_ID=str(org),
        DOCUMENT_ROOT=str(store),
        DOCUMENT_API_TOKEN=secrets.token_urlsafe(40),
        CASE_READ_TOKEN="",
        REVIEW_DEMO_ENABLED="true",
        REVIEW_ACCESS_ENABLED="true",
        EVIDENCE_TRUSTED_SOURCES_JSON="[]",
        EXTRACTION_PROVIDER="disabled",
        EXTERNAL_AI_ENABLED="false",
        INVESTIGATION_PROVIDER="deterministic",
        INVESTIGATION_EXTERNAL_ENABLED="false",
        GEMINI_API_KEY="",
        GEMINI_MODEL="",
        PRIVACY_REVIEW_REFERENCE="",
        LLM_DAILY_REQUESTS="0",
        LLM_DAILY_INPUT_TOKENS="0",
        LLM_DAILY_OUTPUT_TOKENS="0",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    return env


class API:
    def __init__(self, client, password):
        self.client, self.password = client, password
        self.token = ""
        self.logged_at = 0
        self.calls = []

    def request(self, method, path, *, key=None, **kwargs):
        if not self.token or time.monotonic() - self.logged_at > 1200:
            response = self.client.post(
                "/review/demo/login",
                json={"username": "snapshot-operator", "password": self.password},
            )
            if response.status_code != 200:
                raise RuntimeError("Evaluation role login failed")
            self.token = response.json()["access_token"]
            self.logged_at = time.monotonic()
        start = time.perf_counter_ns()
        response = self.client.request(
            method,
            path,
            headers={
                "Authorization": "ReviewDemo " + self.token,
                "Idempotency-Key": str(key or uuid4()),
                **kwargs.pop("headers", {}),
            },
            **kwargs,
        )
        self.calls.append(
            {
                "method": method,
                "path": path,
                "status": response.status_code,
                "elapsed_ns": time.perf_counter_ns() - start,
            }
        )
        return response

    def get(self, path):
        response = self.request("GET", path)
        if response.status_code != 200:
            raise RuntimeError(f"Read failed: {path} HTTP {response.status_code}")
        return response.json()

    def collection(self, path):
        result = []
        for _ in range(100):
            page = self.get(f"{path}?limit=100&offset={len(result)}")
            result.extend(page)
            if len(page) < 100:
                return result
        raise RuntimeError("Pagination budget exceeded")


@contextmanager
def application(env, password, output):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with (output / "api.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
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
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=60, trust_env=False
            ) as client:
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("API exited before readiness")
                    try:
                        if client.get("/ready").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("API readiness deadline")
                    time.sleep(0.1)
                yield API(client, password)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def drain(engine, org, env, output):
    attempts = []
    for _ in range(50):
        with engine.connect() as connection:
            states = list(
                connection.execute(
                    select(OutboxEvent.status).where(
                        OutboxEvent.organization_id == org, OutboxEvent.status != "DELIVERED"
                    )
                ).scalars()
            )
        if not states or "DEAD" in states:
            break
        result = subprocess.run(
            [sys.executable, "-m", "clearledger.case_worker", "--once", "--limit", "100"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        if result.returncode:
            raise RuntimeError("Bounded case worker failed")
        attempts.append(json.loads(result.stdout))
        if any(s in {"RETRY", "LEASED"} for s in states):
            time.sleep(1)
    (output / "worker-counts.json").write_text(json.dumps(attempts), encoding="utf-8")
    return {
        "pending_by_state": {state: states.count(state) for state in set(states)},
        "drains": len(attempts),
    }


__all__ = [
    "ROOT",
    "API",
    "initialize",
    "application",
    "environment",
    "drain",
    "disposable_database",
    "fingerprint",
    "rows",
]
