from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, defer
from starlette.concurrency import run_in_threadpool

from clearledger.data_contract import MAX_BYTES
from clearledger.db import get_session
from clearledger.imports import ingest
from clearledger.models import (
    AuditEvent,
    BankTransaction,
    Customer,
    Invoice,
    Organization,
    PayerAlias,
    Receipt,
    SourceImport,
)
from clearledger.views import (
    AliasView,
    AuditView,
    BankView,
    CustomerView,
    ImportView,
    InvoiceView,
    ReceiptView,
)

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]


def company_scope(request: Request, session: DB) -> UUID:
    session.info["source_correlation_settings"] = request.app.state.settings
    organization_id = request.app.state.settings.organization_id
    if (
        organization_id is None
        or session.scalar(select(Organization.id).where(Organization.id == organization_id)) is None
    ):
        raise HTTPException(
            503, "Configure and provision ORGANIZATION_ID before using business APIs"
        )
    reviewer = getattr(request.state, "review_reviewer", None)
    if reviewer is not None and request.state.review_readonly:
        import hashlib

        from sqlalchemy import text

        from clearledger.review_service import current_reviewer

        if not session.info.get("evidence_readonly"):
            session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
            session.execute(text("SET LOCAL statement_timeout = '10000ms'"))
        key = int.from_bytes(hashlib.sha256(organization_id.bytes).digest()[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": key})
        current_reviewer(session, organization_id, reviewer, "READ")
    return organization_id


Scope = Annotated[UUID, Depends(company_scope)]


@router.post("/imports/{kind}")
async def import_csv(
    kind: Literal["customers", "payer-aliases", "invoices", "bank-transactions"],
    request: Request,
    session: DB,
    organization_id: Scope,
    actor: Annotated[
        str, Header(alias="X-Actor-ID", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.@-]+$")
    ],
    key: Annotated[UUID, Header(alias="Idempotency-Key")],
    contract: Annotated[str, Header(alias="X-Data-Contract-Version", min_length=1, max_length=20)],
    filename: Annotated[str, Header(alias="X-Source-Filename", min_length=1, max_length=128)],
):
    if request.headers.get("content-type", "").split(";")[0].lower() != "text/csv":
        raise HTTPException(
            415, "Content-Type must be text/csv; send raw UTF-8 bytes, not multipart"
        )
    if any(c in filename for c in ("/", "\\", "\x00")) or not filename.lower().endswith(".csv"):
        raise HTTPException(422, "X-Source-Filename must be a CSV basename")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "Maximum file size is 2097152 bytes")
    # Run blocking SQL on a worker thread, like the synchronous read endpoints.
    result = await run_in_threadpool(
        ingest,
        session,
        organization_id=organization_id,
        actor_id=actor,
        kind=kind,
        raw=bytes(raw),
        source_name=filename,
        idempotency_key=key,
        contract_version=contract,
    )
    return JSONResponse(
        {k: v for k, v in result.items() if k != "http_status"}, status_code=result["http_status"]
    )


def read_routes(path, model, view):
    def scoped_query(organization_id):
        statement = select(model).where(model.organization_id == organization_id)
        if model is SourceImport:
            statement = statement.options(defer(SourceImport.raw_bytes, raiseload=True))
        return statement

    def collection(
        session: DB,
        organization_id: Scope,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        return session.scalars(
            scoped_query(organization_id)
            .order_by(model.created_at, model.id)
            .offset(offset)
            .limit(limit)
        ).all()

    def detail(record_id: UUID, session: DB, organization_id: Scope):
        record = session.scalar(scoped_query(organization_id).where(model.id == record_id))
        if record is None:
            raise HTTPException(404, "Record not found")
        return record

    router.add_api_route(
        path,
        collection,
        methods=["GET"],
        response_model=list[view],
        name=f"list_{model.__tablename__}_{path}",
    )
    router.add_api_route(
        path + "/{record_id}",
        detail,
        methods=["GET"],
        response_model=view,
        name=f"get_{model.__tablename__}_{path}",
    )


for path, model, view in (
    ("/customers", Customer, CustomerView),
    ("/payer-aliases", PayerAlias, AliasView),
    ("/invoices", Invoice, InvoiceView),
    ("/bank-transactions", BankTransaction, BankView),
    ("/receipts", Receipt, ReceiptView),
    ("/payments", Receipt, ReceiptView),
    ("/imports", SourceImport, ImportView),
    ("/audit/events", AuditEvent, AuditView),
):
    read_routes(path, model, view)
