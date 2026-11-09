"""Read-only public synthetic deployment over the existing loopback application."""

import asyncio
import json
import os
import re
import secrets
import socket
import threading
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

import certifi
import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from serve_frontend_demo import (
    ROOT,
    SOURCE_SECRET,
    SYNTHETIC_REVIEW_REFERENCE,
    ScriptedAR,
    populate,
)
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.document_contract import ExtractionError, Span, span_text
from clearledger.document_runtime import LocalOriginals
from clearledger.main import create_app
from clearledger.models import Document, Organization
from clearledger.review_models import DemoUser
from clearledger.review_users import provision

READY = "ClearLedger synthetic portfolio v1"
PENDING = "ClearLedger synthetic portfolio seed incomplete"
DATABASE = "clearledger_portfolio"
UUID_PATH = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
READ_PATHS = tuple(
    re.compile(pattern.format(id=UUID_PATH))
    for pattern in (
        r"/(?:health|ready|review/me)",
        r"/(?:customers|invoices|receipts|bank-transactions)(?:/{id})?",
        r"/cases(?:/{id}(?:/(?:claims|investigations|events|reevaluations|review-actions)|/evidence/records/{id})?)?",
        r"/documents(?:/{id}(?:/(?:text|original|extractions))?)?",
        r"/investigations/{id}/(?:findings|trace)",
        r"/review/cases/{id}/correlation-tasks",
        r"/review/correlation-tasks/{id}/(?:decisions|proof)",
    )
)
VERIFY_PATH = re.compile(rf"(/documents/{UUID_PATH})/verify-span")


def neon_url(value):
    url = make_url(value)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg"}
        or not url.host
        or not url.host.endswith(".neon.tech")
        or "-pooler." in url.host
        or url.database != DATABASE
        or not url.username
        or not url.password
        or set(url.query) - {"sslmode", "channel_binding"}
        or url.query.get("sslmode") not in {"require", "verify-full"}
    ):
        raise ValueError("DIRECT_NEON_TLS_URL_REQUIRED")
    return url.set(
        drivername="postgresql+psycopg",
        query={
            "sslmode": "verify-full",
            "sslrootcert": certifi.where(),
            "channel_binding": "require",
        },
    ).render_as_string(hide_password=False)


def public_origin(value):
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or not url.hostname
        or not url.hostname.endswith(".onrender.com")
        or value != f"https://{url.hostname}"
    ):
        raise ValueError("EXACT_RENDER_ORIGIN_REQUIRED")
    return value


def originals(session, settings):
    store = LocalOriginals(settings.document_root)
    for doc in session.scalars(
        select(Document).where(Document.organization_id == settings.organization_id)
    ):
        if not doc.synthetic_approved or doc.mime != "text/plain" or len(doc.pages) != 1:
            raise RuntimeError("UNEXPECTED_PORTFOLIO_SOURCE")
        raw = doc.pages[0].encode()
        if store.put(settings.organization_id, raw) != doc.content_sha256:
            raise RuntimeError("PORTFOLIO_ORIGINAL_RESTORE_MISMATCH")


def bootstrap(database_url, work):
    engine = build_engine(database_url)
    try:
        # Session-level lock stays held across the fixture's existing transactions.
        with engine.connect() as control:
            if not control.scalar(text("SELECT pg_try_advisory_lock(36715038)")):
                raise RuntimeError("PORTFOLIO_BOOTSTRAP_BUSY")
            try:
                if control.scalar(text("SELECT to_regclass('public.organizations')")):
                    names = list(
                        control.scalars(text("SELECT name FROM public.organizations LIMIT 2"))
                    )
                    if names != [READY]:
                        raise RuntimeError("PORTFOLIO_DATABASE_NOT_EMPTY_OR_SEED_INCOMPLETE")
                elif control.scalar(
                    text("""
                    SELECT EXISTS (
                      SELECT 1 FROM pg_tables WHERE schemaname = 'public'
                    )
                """)
                ):
                    raise RuntimeError("PORTFOLIO_DATABASE_NOT_EMPTY")
                cfg = Config(str(ROOT / "alembic.ini"))
                cfg.set_main_option("script_location", str(ROOT / "infra/migrations"))
                cfg.attributes["connection"] = control
                command.upgrade(cfg, "head")
                command.check(cfg)
                control.commit()
                with Session(engine) as session:
                    organizations = list(session.scalars(select(Organization).limit(2)))
                    if organizations and (
                        len(organizations) != 1 or organizations[0].name != READY
                    ):
                        raise RuntimeError("PORTFOLIO_DATABASE_NOT_EMPTY_OR_SEED_INCOMPLETE")
                    org = organizations[0].id if organizations else uuid4()
                    if not organizations:
                        session.add(Organization(id=org, name=PENDING))
                        session.commit()
                settings = Settings(
                    _env_file=None,
                    database_url=database_url,
                    organization_id=org,
                    document_root=work / "originals",
                    document_api_token=SecretStr(secrets.token_urlsafe(40)),
                    case_read_token=None,
                    evidence_trusted_sources_json=SecretStr(
                        json.dumps(
                            [
                                {
                                    "organization_id": str(org),
                                    "source_system": "test-origin",
                                    "key_id": "test-key",
                                    "secret": SOURCE_SECRET,
                                    "allowed_kinds": ["REMITTANCE", "WMS", "POD"],
                                }
                            ]
                        )
                    ),
                    extraction_provider="disabled",
                    external_ai_enabled=False,
                    investigation_provider="deterministic",
                    investigation_external_enabled=False,
                    gemini_api_key=None,
                    gemini_model="",
                    privacy_review_reference=SYNTHETIC_REVIEW_REFERENCE,
                    # The existing seed fixture uses the bounded in-process fake
                    # transport. The public runtime gets zero admission budget.
                    llm_daily_requests=0 if organizations else 30,
                    llm_daily_input_tokens=0 if organizations else 100000,
                    llm_daily_output_tokens=0 if organizations else 30000,
                    llm_shared_requests_per_minute=0 if organizations else 30,
                    case_auto_correlate_extractions=not organizations,
                    case_auto_investigate_extractions=not organizations,
                    review_access_enabled=bool(organizations),
                    review_demo_enabled=bool(organizations),
                )
                if not organizations:
                    seed = create_app(settings)
                    seed.state.investigation_provider = ScriptedAR()
                    with TemporaryDirectory(dir=work) as private_output, TestClient(seed) as client:
                        populate(client, engine, org, settings, Path(private_output))
                    with Session(engine) as session:
                        originals(session, settings)
                        session.get(Organization, org).name = READY
                        session.commit()
                else:
                    with Session(engine) as session:
                        originals(session, settings)
                settings.case_auto_correlate_extractions = False
                settings.case_auto_investigate_extractions = False
                settings.llm_daily_requests = 0
                settings.llm_daily_input_tokens = 0
                settings.llm_daily_output_tokens = 0
                settings.llm_shared_requests_per_minute = 0
                password = secrets.token_urlsafe(32)
                with Session(engine) as session:
                    auditor = session.scalar(
                        select(DemoUser).where(
                            DemoUser.organization_id == org, DemoUser.username == "auditor"
                        )
                    )
                    provision(
                        session,
                        org,
                        "auditor",
                        "AUDITOR",
                        password,
                        expected_version=auditor.version,
                    )
                return settings, password
            finally:
                control.rollback()
                control.execute(text("SELECT pg_advisory_unlock(36715038)"))
    finally:
        engine.dispose()


class Loopback:
    def __init__(self, settings, password):
        self.app = create_app(settings)
        self.use_readonly = ContextVar("portfolio_readonly", default=False)
        self.app.middleware("http")(self.read_boundary)
        application_lifespan = self.app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app):
            async with application_lifespan(app):
                normal = app.state.session_factory
                readonly = sessionmaker(
                    normal.kw["bind"].execution_options(postgresql_readonly=True),
                    info={"evidence_readonly": True},
                )
                app.state.session_factory = lambda: (
                    readonly if self.use_readonly.get() else normal
                )()
                yield

        self.app.router.lifespan_context = lifespan
        self.password = password
        self.token = ""
        self.valid_until = 0.0
        self.login_lock = asyncio.Lock()

    async def read_boundary(self, request, call_next):
        # Keep the existing demo login writable and all loopback GETs read-only.
        # The app's evidence mode uses the company lock without row-level write grants.
        token = self.use_readonly.set(request.method == "GET")
        try:
            return await call_next(request)
        finally:
            self.use_readonly.reset(token)

    @asynccontextmanager
    async def serve(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.server = uvicorn.Server(
                uvicorn.Config(
                    self.app,
                    log_level="critical",
                    access_log=False,
                    proxy_headers=False,
                )
            )
            thread = threading.Thread(
                target=self.server.run, kwargs={"sockets": [listener]}, daemon=True
            )
            thread.start()
            try:
                for _ in range(100):
                    if self.server.started:
                        break
                    await asyncio.sleep(0.05)
                if not self.server.started:
                    raise RuntimeError("PORTFOLIO_INTERNAL_API_UNAVAILABLE")
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
                    trust_env=False,
                    timeout=12,
                ) as client:
                    self.client = client
                    yield
            finally:
                self.server.should_exit = True
                await asyncio.to_thread(thread.join, 15)

    async def get(self, path, query=""):
        if path not in {"/health", "/ready"}:
            async with self.login_lock:
                if time.monotonic() >= self.valid_until:
                    response = await self.client.post(
                        "/review/demo/login",
                        json={"username": "auditor", "password": self.password},
                    )
                    response.raise_for_status()
                    self.token = response.json()["access_token"]
                    self.valid_until = time.monotonic() + 25 * 60
        return await self.client.get(
            path + (f"?{query}" if query else ""),
            headers={"Authorization": f"ReviewDemo {self.token}"} if self.token else {},
        )


def make_gateway(inner, origin):
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lambda _: inner.serve(),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.api_route("/{path:path}", methods=["GET", "POST"], include_in_schema=False)
    async def dispatch(path: str, request: Request):
        path = f"/{path}"
        verify = VERIFY_PATH.fullmatch(path) if request.method == "POST" else None
        if not verify and (
            request.method != "GET" or not any(rule.fullmatch(path) for rule in READ_PATHS)
        ):
            return JSONResponse({"detail": "PORTFOLIO_READ_ONLY"}, status_code=404)
        if len(request.url.query) > 2048:
            return JSONResponse({"detail": "INVALID_QUERY"}, status_code=400)
        try:
            if verify:
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 16384:
                        return JSONResponse(
                            {"detail": "INVALID_DOCUMENT_EVIDENCE"}, status_code=422
                        )
                    body.extend(chunk)
                span = Span.model_validate_json(body)
                result = await inner.get(f"{verify[1]}/text")
                if result.is_success:
                    source = result.json()
                    span_text(source["pages"], span)
                    return JSONResponse(
                        {
                            "source_consistent": True,
                            "source_authenticity": "UNVERIFIED",
                            "financial_authority": False,
                            "span": span.model_dump(),
                            **{
                                k: source[k]
                                for k in (
                                    "document_id",
                                    "document_version",
                                    "raw_sha256",
                                    "canonical_sha256",
                                )
                            },
                        }
                    )
            else:
                result = await inner.get(path, request.url.query)
            if result.status_code < 500:
                return Response(
                    result.content,
                    status_code=result.status_code,
                    headers={
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                        **{
                            k: result.headers[k]
                            for k in ("Content-Type", "Content-Disposition")
                            if k in result.headers
                        },
                    },
                )
        except (ValidationError, ExtractionError):
            return JSONResponse({"detail": "INVALID_DOCUMENT_EVIDENCE"}, status_code=422)
        except (httpx.HTTPError, KeyError, ValueError):
            pass
        return JSONResponse({"detail": "PORTFOLIO_API_UNAVAILABLE"}, status_code=503)

    return app


def main():
    try:
        url = neon_url(connection_value("DATABASE_URL"))
        migration = connection_value("PORTFOLIO_MIGRATION_DATABASE_URL", optional=True)
        migration_url = neon_url(migration) if migration else url
        runtime_target, migration_target = make_url(url), make_url(migration_url)
        if (runtime_target.host, runtime_target.port, runtime_target.database) != (
            migration_target.host,
            migration_target.port,
            migration_target.database,
        ):
            raise ValueError("PORTFOLIO_DATABASE_TARGET_MISMATCH")
        origin = public_origin(os.environ["PORTFOLIO_ORIGIN"])
        port = int(os.environ["PORT"])
        with TemporaryDirectory(prefix="clearledger-portfolio-") as directory:
            settings, password = bootstrap(migration_url, Path(directory))
            settings.database_url = url
            print("PORTFOLIO_SCHEMA_AND_SYNTHETIC_SOURCE_READY", flush=True)
            uvicorn.run(
                make_gateway(Loopback(settings, password), origin),
                host="0.0.0.0",
                port=port,
                access_log=False,
                log_level="warning",
            )
    except Exception as error:
        raise SystemExit(f"PORTFOLIO_STARTUP_FAILED: {type(error).__name__}") from None


def connection_value(name, *, optional=False):
    value = os.environ.get(name)
    if value:
        return value
    path = Path("/etc/secrets") / name
    if optional and not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


if __name__ == "__main__":
    main()
