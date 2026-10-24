from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clearledger.config import Settings
from clearledger.customers import get_customer
from clearledger.db import build_engine
from clearledger.main import create_app
from clearledger.models import Customer, Organization

pytestmark = pytest.mark.postgres


def test_migration_roundtrip_and_persistence(disposable_database, migration_config):
    engine = build_engine(disposable_database.render_as_string(hide_password=False))
    try:
        with engine.connect() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
            assert set(inspect(connection).get_table_names()) == {
                "alembic_version",
                "organizations",
                "customers",
            }
            command.check(migration_config)
            command.downgrade(migration_config, "base")
            assert inspect(connection).get_table_names() == ["alembic_version"]
            command.upgrade(migration_config, "head")
            command.check(migration_config)
            connection.commit()

        with Session(engine) as session:
            first = Organization(name="Synthetic distributor")
            other = Organization(name="Isolation test only")
            session.add_all([first, other])
            session.flush()
            customer = Customer(
                organization_id=first.id, external_reference="C-01", name="Customer"
            )
            session.add(customer)
            session.commit()
            assert customer.created_at.utcoffset().total_seconds() == 0
            assert customer.version == 1
            assert (
                get_customer(session, organization_id=first.id, customer_id=customer.id) == customer
            )
            assert get_customer(session, organization_id=other.id, customer_id=customer.id) is None
            first_id, other_id = first.id, other.id

        with Session(engine) as session:
            session.add(
                Customer(organization_id=first_id, external_reference="C-01", name="Duplicate")
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            session.add(Customer(organization_id=other_id, external_reference="C-01", name="Other"))
            session.commit()
            session.add(Customer(organization_id=uuid4(), external_reference="C-02", name="Orphan"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        app = create_app(
            Settings(database_url=disposable_database.render_as_string(hide_password=False))
        )
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ready"}

        # A real PostgreSQL connection rejection must not affect liveness.
        missing_url = disposable_database.set(database=f"missing_{uuid4().hex}")
        unavailable_app = create_app(
            Settings(database_url=missing_url.render_as_string(hide_password=False))
        )
        with TestClient(unavailable_app) as client:
            assert client.get("/ready").status_code == 503
            assert client.get("/health").status_code == 200
    finally:
        engine.dispose()
