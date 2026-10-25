"""Authenticated local document boundary, separate from financial CSV interfaces."""

import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from clearledger.api import DB, company_scope
from clearledger.document_contract import (
    MAX_DOCUMENT_BYTES,
    ExtractionError,
    Span,
    StrictModel,
    span_text,
)
from clearledger.document_runtime import LocalOriginals
from clearledger.documents import (
    association_context,
    correlate,
    extract_document,
    ingest_document,
    integrity,
)
from clearledger.matching import digest, owned
from clearledger.matching_api import Actor, Key
from clearledger.matching_schemas import Version
from clearledger.models import Document, DocumentAssociation, DocumentEvent, DocumentExtraction
from clearledger.views import RecordView

router = APIRouter(prefix="/documents", tags=["documents"])


def document_scope(
    request: Request,
    session: DB,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    configured = request.app.state.settings.document_api_token
    if configured is None or len(configured.get_secret_value()) < 32:
        raise HTTPException(503, "Configure a strong DOCUMENT_API_TOKEN for local document access")
    supplied = (
        authorization.removeprefix("Bearer ")
        if authorization and authorization.startswith("Bearer ")
        else ""
    )
    if not secrets.compare_digest(supplied.encode(), configured.get_secret_value().encode()):
        raise HTTPException(
            401, "Document authentication required", headers={"WWW-Authenticate": "Bearer"}
        )
    return company_scope(request, session)


DocScope = Annotated[UUID, Depends(document_scope)]


class ExtractInput(StrictModel):
    expected_document_version: Version
    revision_label: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")] = "initial"
    allow_external: bool = False


class CorrelateInput(StrictModel):
    extraction_id: UUID
    expected_document_version: Version
    verified_utr_values: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=20)
    ] = Field(default_factory=list)
    expected_receipt_versions: Annotated[dict[UUID, Version], Field(max_length=100)] = Field(
        default_factory=dict
    )

    # UUIDs arrive as JSON strings; all non-identifier fields remain strictly typed.
    model_config = {**StrictModel.model_config, "strict": False}


class DocumentView(RecordView):
    content_sha256: str
    canonical_sha256: str
    source_name: str
    mime: str
    document_type: str
    size_bytes: int
    synthetic_approved: bool
    parser_version: str
    parse_status: str
    parse_error: str | None


class ExtractionView(RecordView):
    document_id: UUID
    extraction_version: int
    input_sha256: str
    schema_version: str
    route: str
    reason: str
    provider: str
    model: str | None
    status: str
    error_code: str | None
    result: dict
    metrics: dict
    financial_authority: Literal[False] = False
    source_authenticity: Literal["UNVERIFIED"] = "UNVERIFIED"
    requires_human_review: Literal[True] = True
    layout_verified: Literal[False] = False


class AssociationView(RecordView):
    document_id: UUID
    extraction_id: UUID
    receipt_id: UUID | None
    status: str
    input_sha256: str
    result: dict
    is_stale: bool = False


def storage(request):
    return LocalOriginals(request.app.state.settings.document_root)


@router.post("", response_model=DocumentView)
async def upload(
    request: Request,
    session: DB,
    org: DocScope,
    actor: Actor,
    key: Key,
    filename: Annotated[str, Header(alias="X-Source-Filename", min_length=1, max_length=128)],
    synthetic: Annotated[Literal["true", "false"], Header(alias="X-Synthetic-Data")] = "false",
):
    mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
    extensions = {
        "application/pdf": ".pdf",
        "message/rfc822": ".eml",
        "text/plain": ".txt",
        "application/json": ".json",
    }
    if mime not in extensions:
        raise HTTPException(415, "Unsupported document MIME")
    if (
        any(ord(c) < 32 or c in "/\\:" for c in filename)
        or filename.startswith(".")
        or not filename.lower().endswith(extensions[mime])
    ):
        raise HTTPException(422, "Invalid document basename/type")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, "Document exceeds 2 MiB")
        raw.extend(chunk)
    if not raw:
        raise HTTPException(422, "Empty document")
    try:
        doc = await run_in_threadpool(
            ingest_document,
            session,
            org,
            key,
            actor,
            bytes(raw),
            filename,
            mime,
            synthetic == "true",
            storage(request),
        )
        if doc.parse_status == "PARSE_FAILED":
            return JSONResponse(
                status_code=422, content={"document_id": str(doc.id), "code": doc.parse_error}
            )
        return doc
    except ExtractionError:
        raise HTTPException(409, "DOCUMENT_INTEGRITY_OR_STORAGE_FAILURE") from None


@router.get("", response_model=list[DocumentView])
def document_list(
    session: DB,
    org: DocScope,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return session.scalars(
        select(Document)
        .where(Document.organization_id == org)
        .order_by(Document.created_at, Document.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/{document_id}", response_model=DocumentView)
def document_get(document_id: UUID, session: DB, org: DocScope):
    return owned(session, Document, org, document_id)


@router.get("/{document_id}/original")
def original(document_id: UUID, session: DB, org: DocScope, request: Request):
    doc = owned(session, Document, org, document_id)
    try:
        raw = integrity(doc, storage(request))
    except ExtractionError:
        raise HTTPException(409, "DOCUMENT_INTEGRITY_FAILURE") from None
    # Never render active source content or use its untrusted filename in response headers.
    return Response(
        raw,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.id}.bin"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{document_id}/text")
def text(document_id: UUID, session: DB, org: DocScope, request: Request):
    doc = owned(session, Document, org, document_id)
    try:
        integrity(doc, storage(request))
    except ExtractionError:
        raise HTTPException(409, "DOCUMENT_INTEGRITY_FAILURE") from None
    return {
        "document_id": doc.id,
        "document_version": doc.version,
        "raw_sha256": doc.content_sha256,
        "canonical_sha256": doc.canonical_sha256,
        "parser_version": doc.parser_version,
        "pages": doc.pages,
        "parse_status": doc.parse_status,
    }


@router.post("/{document_id}/verify-span")
def verify_span(document_id: UUID, span: Span, session: DB, org: DocScope, request: Request):
    doc = owned(session, Document, org, document_id)
    try:
        integrity(doc, storage(request))
        span_text(doc.pages, span)
    except ExtractionError:
        raise HTTPException(422, "INVALID_DOCUMENT_EVIDENCE") from None
    return {
        "source_consistent": True,
        "source_authenticity": "UNVERIFIED",
        "financial_authority": False,
        "document_id": doc.id,
        "document_version": doc.version,
        "raw_sha256": doc.content_sha256,
        "canonical_sha256": doc.canonical_sha256,
        "span": span.model_dump(),
    }


@router.post("/{document_id}/extract", response_model=ExtractionView)
def extract(
    document_id: UUID,
    body: ExtractInput,
    session: DB,
    org: DocScope,
    request: Request,
    actor: Actor,
    key: Key,
):
    try:
        return extract_document(
            session,
            org,
            document_id,
            key,
            actor,
            body,
            request.app.state.settings,
            storage(request),
            request.app.state.extraction_gateway,
        )
    except ExtractionError:
        raise HTTPException(409, "DOCUMENT_INTEGRITY_FAILURE") from None


@router.get("/{document_id}/extractions", response_model=list[ExtractionView])
def extractions(
    document_id: UUID,
    session: DB,
    org: DocScope,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    owned(session, Document, org, document_id)
    return session.scalars(
        select(DocumentExtraction)
        .where(
            DocumentExtraction.organization_id == org, DocumentExtraction.document_id == document_id
        )
        .order_by(DocumentExtraction.extraction_version)
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("/{document_id}/correlate", response_model=AssociationView)
def correlate_document(
    document_id: UUID,
    body: CorrelateInput,
    session: DB,
    org: DocScope,
    request: Request,
    actor: Actor,
    key: Key,
):
    try:
        return correlate(session, org, document_id, key, actor, body, storage(request))
    except ExtractionError:
        raise HTTPException(409, "DOCUMENT_INTEGRITY_FAILURE") from None


@router.get("/{document_id}/associations", response_model=list[AssociationView])
def associations(
    document_id: UUID,
    session: DB,
    org: DocScope,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    doc = owned(session, Document, org, document_id)
    rows = session.scalars(
        select(DocumentAssociation)
        .where(
            DocumentAssociation.organization_id == org,
            DocumentAssociation.document_id == document_id,
        )
        .order_by(DocumentAssociation.created_at, DocumentAssociation.id)
        .limit(limit)
        .offset(offset)
    ).all()
    result = []
    for row in rows:
        extraction = owned(session, DocumentExtraction, org, row.extraction_id)
        try:
            current, _, _, _ = association_context(
                session, org, doc, extraction, row.inputs["verified_utr_values"], storage(request)
            )
            stale = digest(current) != row.input_sha256
        except ExtractionError:
            stale = True
        view = AssociationView.model_validate(row)
        view.is_stale = stale
        result.append(view)
    return result


@router.get("/{document_id}/events")
def events(
    document_id: UUID,
    session: DB,
    org: DocScope,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    owned(session, Document, org, document_id)
    rows = session.scalars(
        select(DocumentEvent)
        .where(DocumentEvent.organization_id == org, DocumentEvent.document_id == document_id)
        .order_by(DocumentEvent.created_at, DocumentEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor_id": row.actor_id,
            "created_at": row.created_at,
            "entity_id": row.entity_id,
            "details": row.details,
        }
        for row in rows
    ]
