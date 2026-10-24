"""Local company provisioning only. Does not create customer/financial datasets."""

import argparse

from sqlalchemy.orm import Session

from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.models import Organization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init-organization"])
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    settings = Settings()
    if settings.organization_id is None:
        parser.error("Set ORGANIZATION_ID to your company UUID in .env first")
    if not args.name.strip() or len(args.name) > 200:
        parser.error("Company name must contain 1–200 characters")
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as session, session.begin():
            record = session.get(Organization, settings.organization_id)
            if record is None:
                session.add(Organization(id=settings.organization_id, name=args.name))
            elif record.name != args.name:
                parser.error("This organization UUID already exists with a different name")
        print(f"Organization configured: {settings.organization_id}; no financial data created")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
