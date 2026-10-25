import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline_model_defaults(monkeypatch):
    """Local .env credentials must never enable paid calls in automated tests."""
    monkeypatch.setenv("EXTERNAL_AI_ENABLED", "false")
    monkeypatch.setenv("EXTRACTION_PROVIDER", "disabled")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("INVESTIGATION_EXTERNAL_ENABLED", "false")
    monkeypatch.setenv("INVESTIGATION_PROVIDER", "deterministic")


def pytest_addoption(parser):
    parser.addoption(
        "--isolated-restart-container",
        help="Only the labelled disposable container created by verify_isolated_restart.py",
    )
    parser.addoption(
        "--require-postgres", action="store_true", help="Fail instead of skipping PostgreSQL tests"
    )


@pytest.fixture
def disposable_database(request):
    """One DB per test: migration roundtrips must not consume another test's history.

    Only DROP a generated database, never the database from the supplied URL.
    """
    configured_url = os.environ.get("TEST_DATABASE_URL")
    if not configured_url:
        if request.config.getoption("--require-postgres"):
            pytest.fail("TEST_DATABASE_URL is required for PostgreSQL acceptance checks")
        pytest.skip("Set TEST_DATABASE_URL to run disposable PostgreSQL tests")
    admin_url = make_url(configured_url)
    if admin_url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use real PostgreSQL (postgresql+psycopg)")
    database_name = f"clearledger_test_{uuid4().hex}"
    admin_engine = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    created = False
    try:
        with admin_engine.connect() as connection:
            # Name consists solely of a fixed prefix and server-generated UUID hex.
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            created = True
        yield admin_url.set(database=database_name)
    finally:
        try:
            if created:
                with admin_engine.connect() as connection:
                    connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        finally:
            admin_engine.dispose()


@pytest.fixture
def migration_config():
    return Config(str(ROOT / "alembic.ini"))
