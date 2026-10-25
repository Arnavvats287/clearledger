"""Trusted orchestrator admission only: durable shared quotas, never passed to a worker."""

import hashlib
from datetime import UTC, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from clearledger.config import Settings
from clearledger.document_contract import ExtractionError
from clearledger.models import ProviderReservation


def reserve(
    engine: Engine, organization_id: UUID, provider: Literal["gemini", "fake"], settings: Settings
) -> dict[str, object]:
    if not isinstance(engine, Engine):
        raise ExtractionError("PROVIDER_BUDGET_UNAVAILABLE")
    # Independent transaction: outer document rollback/crash cannot refund possible API use.
    # Different namespace from the outer company lock avoids self-deadlock.
    key = int.from_bytes(
        hashlib.sha256(f"provider-quota:{organization_id}:{provider}".encode()).digest()[:8],
        signed=True,
    )
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        now = session.scalar(text("SELECT clock_timestamp()"))
        day = now.astimezone(UTC).date()
        if settings.llm_max_cost_paise_per_attempt is not None:
            input_rate = settings.llm_input_paise_per_million_tokens
            output_rate = settings.llm_output_paise_per_million_tokens
            if input_rate is None or output_rate is None:
                raise ExtractionError("PROVIDER_PRICE_UNVERIFIED")
            estimate = (
                settings.llm_max_input_tokens * input_rate
                + settings.llm_max_output_tokens * output_rate
                + 999999
            ) // 1000000
            if estimate > settings.llm_max_cost_paise_per_attempt:
                raise ExtractionError("PROVIDER_COST_LIMIT")
        daily = session.execute(
            select(
                func.coalesce(func.sum(ProviderReservation.requests), 0),
                func.coalesce(func.sum(ProviderReservation.input_tokens), 0),
                func.coalesce(func.sum(ProviderReservation.output_tokens), 0),
            ).where(
                ProviderReservation.organization_id == organization_id,
                ProviderReservation.provider == provider,
                ProviderReservation.quota_day == day,
            )
        ).one()
        requested = (3, settings.llm_max_input_tokens, settings.llm_max_output_tokens)
        caps = (
            settings.llm_daily_requests,
            settings.llm_daily_input_tokens,
            settings.llm_daily_output_tokens,
        )
        if any(
            used + needed > limit
            for used, needed, limit in zip(daily, requested, caps, strict=True)
        ):
            raise ExtractionError("PROVIDER_DAILY_BUDGET_EXHAUSTED")
        minute = session.scalar(
            select(func.coalesce(func.sum(ProviderReservation.requests), 0)).where(
                ProviderReservation.organization_id == organization_id,
                ProviderReservation.provider == provider,
                ProviderReservation.created_at > now - timedelta(seconds=60),
            )
        )
        if minute is None or minute + 3 > settings.llm_shared_requests_per_minute:
            raise ExtractionError("PROVIDER_SHARED_RATE_LIMIT")
        row = ProviderReservation(
            organization_id=organization_id,
            provider=provider,
            quota_day=day,
            requests=3,
            input_tokens=requested[1],
            output_tokens=requested[2],
            created_at=now,
        )
        session.add(row)
        session.flush()
        identifier = str(row.id)
    return {
        "reservation_id": identifier,
        "scope": "company/provider/PostgreSQL",
        "quota_day": day.isoformat(),
        "reserved_requests": 3,
        "reserved_input_tokens": requested[1],
        "reserved_output_tokens": requested[2],
    }
