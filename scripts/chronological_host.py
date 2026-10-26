"""Frozen real application/worker host. Never reads local .env or admin credentials."""

import json
import re
import secrets
import subprocess
import sys
import time
from collections import Counter
from contextlib import redirect_stdout
from uuid import UUID, uuid5

from alembic import command
from alembic.config import Config
from application_eval_host import API, ROOT, application, environment
from chronological_diagnostics import (
    ObservationFailure,
    WorkerFailure,
    diagnostic,
    worker_diagnostic,
)
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from clearledger.case_models import OutboxEvent
from clearledger.case_outbox import drain
from clearledger.config import Settings
from clearledger.main import create_app
from clearledger.models import Organization
from clearledger.review_users import provision


def frozen_settings():
    settings = Settings(_env_file=None)
    if (
        settings.external_ai_enabled
        or settings.investigation_external_enabled
        or settings.extraction_provider != "disabled"
        or settings.investigation_provider != "deterministic"
        or (settings.gemini_api_key and settings.gemini_api_key.get_secret_value())
        or settings.gemini_model
        or settings.privacy_review_reference
        or not settings.review_demo_enabled
        or not settings.review_access_enabled
        or settings.llm_daily_requests != 0
        or settings.llm_daily_input_tokens != 0
        or settings.llm_daily_output_tokens != 0
        or settings.llm_shared_requests_per_minute != 0
        or not settings.evidence_trusted_sources_json
        or settings.evidence_trusted_sources_json.get_secret_value() != "[]"
    ):
        raise ValueError("FROZEN_OFFLINE_CONFIGURATION_MISMATCH")
    return settings


def factory():
    app = create_app(frozen_settings())
    if app.state.finance_identity_verifier is not None:
        raise ValueError("FINANCIAL_AUTHORITY_FORBIDDEN")
    return app


def initialize_owned(url, company, run_id):
    """The privileged owner/bootstrap is OUTSIDE this process and its credentials."""
    parsed = make_url(url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or not re.fullmatch(r"clearledger_chrono_[0-9a-f]{32}", parsed.database or "")
        or parsed.query
    ):
        raise ValueError("FRESH_UNPRIVILEGED_OWNED_DATABASE_REQUIRED")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=25000 -c lock_timeout=3000",
        },
    )
    try:
        with engine.connect() as connection:
            role = connection.execute(
                text("""
                SELECT r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
                       OR r.rolbypassrls AS privileged,
                       d.datdba = r.oid AND session_user = current_user AS owned,
                       d.datname ~ '^clearledger_chrono_[0-9a-f]{32}$' AS disposable
                FROM pg_roles r JOIN pg_database d ON d.datname = current_database()
                WHERE r.rolname = current_user
            """)
            ).one()
            memberships = connection.scalar(
                text("""
                SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                WHERE r.rolname=current_user
            """)
            )
            if role.privileged or not role.owned or not role.disposable or memberships:
                raise ValueError("FRESH_UNPRIVILEGED_OWNED_DATABASE_REQUIRED")
            if (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='public'"
                    )
                )
                or connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_proc p "
                        "JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='public'"
                    )
                )
                or connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_namespace WHERE nspname NOT IN "
                        "('public','information_schema','pg_catalog','pg_toast')"
                    )
                )
            ):
                raise ValueError("PRIOR_RUN_DATABASE_REJECTED")
            cfg = Config(str(ROOT / "alembic.ini"), stdout=sys.stderr)
            cfg.attributes["connection"] = connection
            with redirect_stdout(sys.stderr):
                command.upgrade(cfg, "head")
                command.check(cfg)
            connection.commit()
        org = uuid5(UUID(run_id), company)
        password = secrets.token_urlsafe(32)
        with Session(engine) as session:
            session.add(Organization(id=org, name="Isolated chronological evaluation"))
            session.commit()
            with redirect_stdout(sys.stderr):
                provision(session, org, "snapshot-operator", "AR_ANALYST", password)
        return engine, org, password
    except BaseException:
        engine.dispose()
        raise


def host_environment(url, org, output):
    env = environment(url, org, output / "originals")
    env.update(
        LLM_SHARED_REQUESTS_PER_MINUTE="0",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(ROOT / "scripts"),
    )
    return env


class BoundedAPI(API):
    def __init__(self, client, password, run_id):
        super().__init__(client, password)
        self.run_id = UUID(run_id)
        self.deadline = time.monotonic() + 100
        self.observations = []

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("STAGE_DEADLINE")
        return left

    def get(self, path):
        response = self.request("GET", path)
        if response.status_code != 200:
            raise ObservationFailure("OBSERVATION_READ_API_ERROR", response)
        return response.json()

    def request(self, method, path, *, key=None, **kwargs):
        from chronological_protocol import canonical

        identity = method.encode() + path.encode() + canonical(kwargs.get("json"))
        identity += canonical(kwargs.get("headers"))
        identity += kwargs.get("content", b"")
        key = key or uuid5(self.run_id, __import__("hashlib").sha256(identity).hexdigest())
        kwargs["timeout"] = min(20, self.remaining())
        # Also bound first login/token renewal (the reused API client authenticates internally).
        self.client.timeout = kwargs["timeout"]
        started = time.perf_counter_ns()
        try:
            response = super().request(method, path, key=key, **kwargs)
        except Exception as error:
            from chronological_diagnostics import route

            self.observations.append(
                {
                    "method": method,
                    "route": route(path),
                    "status": None,
                    "elapsed_ns": time.perf_counter_ns() - started,
                    "failure": diagnostic(error, "api_request"),
                }
            )
            raise
        # Private provenance, never log authorization headers or login responses.
        try:
            body = response.json()
        except ValueError:
            body = {
                "bytes": len(response.content),
                "sha256": __import__("hashlib").sha256(response.content).hexdigest(),
            }
        self.observations.append({**self.calls[-1], "response": body})
        self.remaining()
        return response


def drain_owned(engine, org, env, api):
    count = 0
    for _ in range(50):
        api.remaining()
        with engine.connect() as connection:
            pending = list(
                connection.execute(
                    select(OutboxEvent.status, OutboxEvent.last_error_code).where(
                        OutboxEvent.organization_id == org, OutboxEvent.status != "DELIVERED"
                    )
                )
            )
        states = [row[0] for row in pending]
        if not states:
            return count
        if any(state != "PENDING" for state in states):
            allowed_codes = {
                "CASE_ANALYSIS_LIMIT",
                "CASE_MEMBERSHIP_LIMIT",
                "CASE_GRAPH_LIMIT",
                "DOCUMENT_INTEGRITY_FAILURE",
                "ORIGINAL_NOT_FOUND",
                "CASE_EVENT_FAILED",
            }
            raise WorkerFailure(
                "OUTBOX_RETRY_OR_FAILURE_DISCARD_RUN",
                {
                    "states": dict(
                        Counter(
                            s if s in {"PENDING", "LEASED", "RETRY", "DEAD"} else "UNKNOWN"
                            for s in states
                        )
                    ),
                    "error_codes": sorted(
                        {
                            row[1] if row[1] in allowed_codes else "UNKNOWN"
                            for row in pending
                            if row[1] is not None
                        }
                    ),
                },
            )
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/chronological_host.py")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=min(30, api.remaining()),
        )
        if result.returncode:
            details = None
            if len(result.stderr) <= 16384:
                try:
                    details = worker_diagnostic(json.loads(result.stderr).get("worker_error"))
                except (ValueError, AttributeError, TypeError):
                    pass
            raise WorkerFailure("BOUNDED_WORKER_FAILED", details)
        value = json.loads(result.stdout)
        count += value.get("DELIVERED", 0)
    raise RuntimeError("OUTBOX_DRAIN_BUDGET")


__all__ = [
    "ROOT",
    "application",
    "host_environment",
    "initialize_owned",
    "BoundedAPI",
    "frozen_settings",
    "drain_owned",
]


def worker_main():
    # Worker RPC is a dedicated, bounded child. No .env fallback.
    from clearledger.db import build_engine

    engine = None
    status = 0
    try:
        settings = frozen_settings()
        engine = build_engine(settings.database_url)
        print(json.dumps(drain(engine, settings.organization_id, settings, 100)))
    except Exception as error:
        print(json.dumps({"worker_error": diagnostic(error, "worker")}), file=sys.stderr)
        status = 1
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception as error:
                print(json.dumps({"worker_error": diagnostic(error, "worker")}), file=sys.stderr)
                status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(worker_main())
