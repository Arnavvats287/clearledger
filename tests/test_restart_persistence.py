"""G2: real API process restart; optional owned-container restart, never shared DB."""

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from tempfile import TemporaryFile
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from alembic import command
from conftest import ROOT
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_imports import BANK, CUSTOMER, INVOICE, csv_bytes, post

from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.document_contract import ExtractionError
from clearledger.models import (
    AuditEvent,
    BankTransaction,
    Customer,
    Invoice,
    Organization,
    ProviderReservation,
    Receipt,
    SourceImport,
)
from clearledger.provider_budget import reserve

pytestmark = pytest.mark.postgres
RECORDS = (Customer, Invoice, BankTransaction, Receipt, SourceImport, AuditEvent)


def tenant_rows(engine, organization_id, models=RECORDS):
    """Compare every persisted column, including original bytes, IDs and timestamps."""
    with engine.connect() as connection:
        return {
            model.__tablename__: [
                dict(row)
                for row in connection.execute(
                    select(model.__table__)
                    .where(model.organization_id == organization_id)
                    .order_by(model.id)
                ).mappings()
            ]
            for model in models
        }


@contextmanager
def running_api(database_url, organization_id):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {**os.environ, "DATABASE_URL": database_url, "ORGANIZATION_ID": str(organization_id)}
    with TemporaryFile(mode="w+", encoding="utf-8") as output:
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
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
            ) as client:
                deadline = time.monotonic() + 20
                while True:
                    assert process.poll() is None, "API exited during startup"
                    try:
                        response = client.get("/health", timeout=1)
                        response.raise_for_status()
                        break
                    except httpx.TransportError:
                        if time.monotonic() >= deadline:
                            pytest.fail("API failed to start")
                        time.sleep(0.1)
                assert client.get("/ready").json() == {"status": "ready"}
                yield client, process.pid
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            assert process.poll() is not None


def restart_owned_container(name):
    """Fail closed before any restart if the name/ownership labels do not match."""
    match = re.fullmatch(r"clearledger_restart_test_([0-9a-f]{32})", name)
    assert match, "Refusing to restart a container outside the disposable test namespace"
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", name],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    labels = json.loads(result.stdout)
    assert labels.get("com.clearledger.test-run") == match[1]
    assert labels.get("com.clearledger.purpose") == "restart-verification"
    before_port = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            '{{json (index .NetworkSettings.Ports "5432/tcp")}}',
            name,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    subprocess.run(["docker", "restart", name], capture_output=True, check=True, timeout=30)
    deadline = time.monotonic() + 45
    while True:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", name],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        if result.stdout.strip() == "healthy":
            after_port = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{json (index .NetworkSettings.Ports "5432/tcp")}}',
                    name,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
            assert after_port == before_port, (
                f"Isolated host binding changed: {before_port} -> {after_port}"
            )
            return
        assert time.monotonic() < deadline, "Isolated PostgreSQL failed to become healthy"
        time.sleep(0.2)


def test_shared_development_container_is_rejected_before_any_docker_call(monkeypatch):
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(AssertionError, match="Refusing to restart"):
        restart_owned_container("clearledger-db-1")
    run.assert_not_called()


def test_financial_import_survives_process_restart_and_fresh_connection(
    disposable_database, migration_config, request
):
    url = disposable_database.render_as_string(hide_password=False)
    organization_id = uuid4()
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
            connection.commit()
        with Session(engine) as session, session.begin():
            session.add(Organization(id=organization_id, name="Test restart"))

        budget = Settings(database_url=url, llm_daily_requests=3)
        reserve(engine, organization_id, "fake", budget)
        quota_before = tenant_rows(engine, organization_id, (ProviderReservation,))

        payloads = {"customers": CUSTOMER, "invoices": INVOICE, "bank-transactions": BANK}
        keys = {kind: uuid4() for kind in payloads}
        results = {}
        with running_api(url, organization_id) as (client, first_pid):
            for kind, row in payloads.items():
                response = post(client, kind, row, key=keys[kind])
                assert response.status_code == 200, response.text
                results[kind] = response.json()
                assert response.json()["inserted"] == 1
            before_api = {
                path: client.get(path).json()
                for path in (
                    "/customers",
                    "/invoices",
                    "/bank-transactions",
                    "/receipts",
                    "/imports",
                    "/audit/events",
                )
            }
            before = tenant_rows(engine, organization_id)
            with engine.connect() as connection:
                first_backend = connection.scalar(text("SELECT pg_backend_pid()"))
        # Both the first API process and this verifier's complete connection pool
        # are closed. No ORM identity map or existing connection can satisfy reads.
        engine.dispose()
    finally:
        engine.dispose()

    container = request.config.getoption("--isolated-restart-container")
    if container is not None:
        restart_owned_container(container)

    fresh_engine = build_engine(url)
    try:
        assert tenant_rows(fresh_engine, organization_id, (ProviderReservation,)) == quota_before
        with pytest.raises(ExtractionError, match="PROVIDER_DAILY_BUDGET_EXHAUSTED"):
            reserve(fresh_engine, organization_id, "fake", budget)
        with fresh_engine.connect() as connection:
            if container is None:
                assert connection.scalar(text("SELECT pg_backend_pid()")) != first_backend
        assert tenant_rows(fresh_engine, organization_id) == before
        assert len(before["customers"]) == len(before["invoices"]) == 1
        assert len(before["bank_transactions"]) == len(before["receipts"]) == 1
        assert len(before["source_imports"]) == 3
        assert len(before["audit_events"]) == 7
        for source in before["source_imports"]:
            assert source["raw_bytes"] == csv_bytes(source["kind"], payloads[source["kind"]])
            assert source["content_sha256"] == hashlib.sha256(source["raw_bytes"]).hexdigest()
        assert before["invoices"][0]["open_amount_paise"] == 100
        assert before["receipts"][0]["unapplied_amount_paise"] == 100

        with running_api(url, organization_id) as (client, second_pid):
            assert second_pid != first_pid
            for path, expected in before_api.items():
                assert client.get(path).json() == expected
            for kind, row in payloads.items():
                response = post(client, kind, row, key=keys[kind], filename="renamed.csv")
                assert response.status_code == 200, response.text
                assert response.json() == results[kind]
            after_replay = tenant_rows(fresh_engine, organization_id)
            for table in before:
                if table != "audit_events":
                    assert after_replay[table] == before[table]
            previous_events = {row["id"]: row for row in before["audit_events"]}
            current_events = {row["id"]: row for row in after_replay["audit_events"]}
            assert all(current_events[key] == value for key, value in previous_events.items())
            replay_events = [
                row for key, row in current_events.items() if key not in previous_events
            ]
            assert len(replay_events) == 3
            assert {row["event_type"] for row in replay_events} == {"import.replayed"}

            # A fresh key/file name also exercises natural transaction identity.
            duplicate = post(client, "bank-transactions", BANK, filename="another-name.csv")
            assert duplicate.status_code == 200
            assert duplicate.json()["inserted"] == duplicate.json()["receipts_created"] == 0
            assert duplicate.json()["duplicates"] == 1
            final = tenant_rows(fresh_engine, organization_id)
            for model in (Customer, Invoice, BankTransaction, Receipt):
                assert final[model.__tablename__] == before[model.__tablename__]
            assert len(final["source_imports"]) == 4
            assert len(final["audit_events"]) == len(before["audit_events"]) + 5
    finally:
        fresh_engine.dispose()
