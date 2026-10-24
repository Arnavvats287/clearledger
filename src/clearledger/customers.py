"""Minimal tenant-scoped persistence reads; no public customer API yet."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from clearledger.models import Customer


def get_customer(session: Session, *, organization_id: UUID, customer_id: UUID) -> Customer | None:
    return session.scalar(
        select(Customer).where(
            Customer.organization_id == organization_id, Customer.id == customer_id
        )
    )
