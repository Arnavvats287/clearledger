"""Deployment-only session and admission counters. No document or provider data."""

import hashlib
import re
import secrets

from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url

DAILY = {"sessions": 1000, "uploads": 300, "included": 20, "byok": 40}
PER_SESSION = {"uploads": 15, "included": 1, "byok": 3}
DAY = "(transaction_timestamp() AT TIME ZONE 'UTC')::date"
LOCK = 36715039


class AdmissionError(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status, self.code = status, code


def setup(engine: Engine, runtime_url: str) -> None:
    username = make_url(runtime_url).username
    if username is None:
        raise RuntimeError("PORTFOLIO_RUNTIME_ROLE_REQUIRED")
    role = engine.dialect.identifier_preparer.quote_identifier(username)
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK})
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS portfolio_demo")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS portfolio_demo.sessions (
              token_hash char(64) PRIMARY KEY,
              expires_at timestamptz NOT NULL,
              uploads integer NOT NULL DEFAULT 0 CHECK (uploads BETWEEN 0 AND 15),
              included integer NOT NULL DEFAULT 0 CHECK (included BETWEEN 0 AND 1),
              byok integer NOT NULL DEFAULT 0 CHECK (byok BETWEEN 0 AND 3)
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS portfolio_demo.daily (
              day date PRIMARY KEY,
              sessions integer NOT NULL DEFAULT 0 CHECK (sessions BETWEEN 0 AND 1000),
              uploads integer NOT NULL DEFAULT 0 CHECK (uploads BETWEEN 0 AND 300),
              included integer NOT NULL DEFAULT 0 CHECK (included BETWEEN 0 AND 20),
              byok integer NOT NULL DEFAULT 0 CHECK (byok BETWEEN 0 AND 40)
            )
        """)
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA portfolio_demo TO {role}")
        conn.exec_driver_sql(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_demo.sessions, "
            f"portfolio_demo.daily TO {role}"
        )


def token_hash(token: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise AdmissionError(401, "DEMO_SESSION_REQUIRED")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class Sessions:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _daily(self, conn, name: str) -> None:
        # Names come only from the fixed internal actions. The row update
        # serializes simultaneous requests across processes and restarts.
        maximum = DAILY[name]
        conn.execute(
            text(f"INSERT INTO portfolio_demo.daily (day) VALUES ({DAY}) ON CONFLICT DO NOTHING")
        )
        changed = conn.execute(
            text(
                f"UPDATE portfolio_demo.daily SET {name} = {name} + 1 "
                f"WHERE day = {DAY} AND {name} < :maximum RETURNING day"
            ),
            {"maximum": maximum},
        ).scalar()
        if changed is None:
            raise AdmissionError(429, f"DEMO_{name.upper()}_DAILY_LIMIT")

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM portfolio_demo.sessions WHERE expires_at <= now()"))
            self._daily(conn, "sessions")
            conn.execute(text(f"DELETE FROM portfolio_demo.daily WHERE day < {DAY} - 7"))
            conn.execute(
                text(
                    "INSERT INTO portfolio_demo.sessions (token_hash, expires_at) "
                    "VALUES (:hash, now() + interval '2 hours')"
                ),
                {"hash": token_hash(token)},
            )
        return token

    def check(self, token: str) -> str:
        identifier = token_hash(token)
        with self.engine.connect() as conn:
            active = conn.scalar(
                text(
                    "SELECT token_hash FROM portfolio_demo.sessions "
                    "WHERE token_hash = :hash AND expires_at > now()"
                ),
                {"hash": identifier},
            )
        if active is None:
            raise AdmissionError(401, "DEMO_SESSION_REQUIRED")
        return identifier

    def revoke(self, token: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM portfolio_demo.sessions WHERE token_hash = :hash"),
                {"hash": token_hash(token)},
            )

    def reserve(self, identifier: str, action: str) -> None:
        maximum = PER_SESSION[action]
        with self.engine.begin() as conn:
            changed = conn.execute(
                text(
                    f"UPDATE portfolio_demo.sessions SET {action} = {action} + 1 "
                    f"WHERE token_hash = :hash AND expires_at > now() AND {action} < :maximum "
                    "RETURNING token_hash"
                ),
                {"hash": identifier, "maximum": maximum},
            ).scalar()
            if changed is None:
                raise AdmissionError(429, f"DEMO_{action.upper()}_SESSION_LIMIT")
            if action in DAILY:
                self._daily(conn, action)
