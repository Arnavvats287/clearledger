"""Trusted TEST bootstrap, never imported by the adapter or copied into its image.

Administrator access belongs here, outside the unprivileged runner environment.
Only UUID-generated roles/databases created by this context can be removed.
"""

import re
import secrets
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@contextmanager
def owned_database(admin_url):
    admin_url = make_url(admin_url)
    name = "clearledger_chrono_" + uuid4().hex
    role = "cl_chrono_" + uuid4().hex
    password = secrets.token_hex(24)
    admin = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    made_role = made_database = False
    try:
        with admin.connect() as connection:
            # All interpolated identifiers/passwords are locally generated fixed alphabets.
            assert re.fullmatch("cl_chrono_[0-9a-f]{32}", role)
            assert re.fullmatch("clearledger_chrono_[0-9a-f]{32}", name)
            assert re.fullmatch("[0-9a-f]{48}", password)
            connection.execute(
                text(
                    f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}' "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
            )
            made_role = True
            connection.execute(text(f'CREATE DATABASE "{name}" OWNER "{role}"'))
            made_database = True
            connection.execute(text(f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC'))
        yield admin_url.set(username=role, password=password, database=name)
    finally:
        try:
            with admin.connect() as connection:
                if made_database:
                    connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
                if made_role:
                    connection.execute(text(f'DROP ROLE "{role}"'))
        finally:
            admin.dispose()
