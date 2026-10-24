"""Verify CLI migrations and normal-restart persistence in a disposable Docker DB.

Run from the repository root. Restarts only this project's Compose db service.
Never downgrades the configured development database or touches portable PostgreSQL.
"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from clearledger.config import Settings
from clearledger.db import build_engine

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        arguments, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=True
    )
    return result.stdout.strip()


def main() -> None:
    values = dotenv_values(ROOT / ".env")
    url = Settings().database_url
    container = run("docker", "compose", "ps", "-q", "db")
    if not container:
        raise RuntimeError("Start this project's Compose db service first")
    expected_identity = run(
        "docker",
        "compose",
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        values["POSTGRES_USER"],
        "-d",
        values["POSTGRES_DB"],
        "-Atc",
        "SELECT system_identifier FROM pg_control_system()",
    )
    admin = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    database_name = f"clearledger_test_{uuid4().hex}"
    created = False
    engine = None
    try:
        with admin.connect() as connection:
            identity = str(
                connection.scalar(text("SELECT system_identifier FROM pg_control_system()"))
            )
            if identity != expected_identity:
                raise RuntimeError(
                    "DATABASE_URL does not point to this project's Docker PostgreSQL"
                )
            print(
                "Windows DATABASE_URL verified against Docker PostgreSQL cluster identity",
                flush=True,
            )
            # Only generated identifiers are interpolated into DDL.
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            created = True
        disposable_url = admin.url.set(database=database_name)
        env = os.environ.copy()
        env["DATABASE_URL"] = disposable_url.render_as_string(hide_password=False)
        for arguments in (
            ("upgrade", "head"),
            ("downgrade", "base"),
            ("upgrade", "head"),
            ("current",),
            ("check",),
        ):
            output = run(sys.executable, "-m", "alembic", *arguments, env=env)
            print(f"alembic {' '.join(arguments)}: {output or 'exit 0'}", flush=True)

        marker_id = uuid4()
        engine = build_engine(env["DATABASE_URL"])
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
                {"id": marker_id, "name": "Disposable Docker persistence probe"},
            )
        engine.dispose()
        admin.dispose()
        run("docker", "compose", "restart", "db")
        run("docker", "compose", "up", "-d", "--wait", "--wait-timeout", "45", "db")
        if run("docker", "compose", "ps", "-q", "db") != container:
            raise RuntimeError("Expected a normal restart of the same container")
        health = run("docker", "inspect", "--format", "{{.State.Health.Status}}", container)
        if health != "healthy":
            raise RuntimeError("Database health check did not pass after restart")
        with engine.connect() as connection:
            name = connection.scalar(
                text("SELECT name FROM organizations WHERE id = :id"), {"id": marker_id}
            )
            if name != "Disposable Docker persistence probe":
                raise RuntimeError("Committed probe row did not survive container restart")
        print(
            "Normal container restart: healthy; committed row persisted; same container", flush=True
        )
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.connect() as connection:
                    connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
                print("Generated disposable verification database removed", flush=True)
        finally:
            admin.dispose()


if __name__ == "__main__":
    main()
