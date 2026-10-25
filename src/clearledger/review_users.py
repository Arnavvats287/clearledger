"""Host-console-only demo provisioning; no HTTP admin or production authority."""

import argparse
import getpass

from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.case_repository import scoped
from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.matching import lock_company
from clearledger.models import Organization
from clearledger.review_contract import Login
from clearledger.review_models import DemoAuthEvent, DemoUser
from clearledger.review_password import encode


def provision(session, org, username, role, password=None, *, enabled=True, expected_version=None):
    Login(username=username, password="validation-only")
    if role not in {"AR_ANALYST", "CONTROLLER", "AUDITOR"}:
        raise ValueError("Unknown demo role")
    lock_company(session, org)
    if session.get(Organization, org) is None:
        raise CaseError("ORGANIZATION_NOT_PROVISIONED", 503)
    row = scoped(session, DemoUser, org, username=username)
    if row is None:
        if expected_version is not None or password is None:
            raise CaseError("DEMO_USER_CREATE_REQUIRES_PASSWORD", 422)
        row = DemoUser(
            organization_id=org,
            username=username,
            role=role,
            password_hash=encode(password),
            enabled=enabled,
        )
        session.add(row)
    else:
        if expected_version != row.version:
            raise CaseError("STALE_DEMO_USER_VERSION")
        row.role, row.enabled, row.version = role, enabled, row.version + 1
        if password is not None:
            row.password_hash = encode(password)
    session.flush()
    session.add(
        DemoAuthEvent(
            organization_id=org,
            kind="USER_PROVISIONED",
            data={
                "actor": "LOCAL_HOST_CONSOLE",
                "authority": "LOCAL_DEMO_ONLY",
                "user_id": str(row.id),
                "user_version": row.version,
                "role": row.role,
                "enabled": row.enabled,
            },
        )
    )
    session.commit()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--role", required=True, choices=["AR_ANALYST", "CONTROLLER", "AUDITOR"])
    parser.add_argument("--expected-version", type=int)
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.review_demo_enabled or settings.organization_id is None:
        raise SystemExit("Explicit REVIEW_DEMO_ENABLED and configured organization required")
    password = None if args.disable else getpass.getpass("Local demo password (16–128 chars): ")
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as session:
            row = provision(
                session,
                settings.organization_id,
                args.username,
                args.role,
                password,
                enabled=not args.disable,
                expected_version=args.expected_version,
            )
            print(f"LOCAL_DEMO_ONLY user {row.id}, version {row.version}; no finance authority")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
