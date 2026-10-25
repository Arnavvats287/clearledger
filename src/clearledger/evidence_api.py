"""Typed ingestion and separate database-enforced read-only evidence capabilities."""

import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from clearledger.api import DB, company_scope
from clearledger.case_api import SafeCaseRoute, Scope
from clearledger.document_contract import ExtractionError
from clearledger.evidence_contract import (
    NativePointer,
    RecordInput,
    RecordView,
    ScopeInput,
    SearchInput,
    SearchResult,
    Verification,
    VerifyInput,
    validate_json_body,
)
from clearledger.evidence_ingestion import register
from clearledger.evidence_reader import (
    EvidenceReader,
    begin_readonly,
    find_contract_clauses,
    find_promotions,
    get_invoice_evidence,
    get_proof_of_delivery,
    get_remittance_evidence,
    get_tagged_tax_evidence,
    get_wms_deliveries,
)
from clearledger.matching_api import Actor, Key

MAX_JSON_BYTES = 262144
TOOLS = {
    "find_contract_clauses": find_contract_clauses,
    "find_promotions": find_promotions,
    "get_wms_deliveries": get_wms_deliveries,
    "get_proof_of_delivery": get_proof_of_delivery,
    "get_tagged_tax_evidence": get_tagged_tax_evidence,
    "get_invoice_evidence": get_invoice_evidence,
    "get_remittance_evidence": get_remittance_evidence,
}


class EvidenceRoute(SafeCaseRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            if request.method == "POST":
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > MAX_JSON_BYTES:
                        raise HTTPException(413, "Evidence JSON body limit")
                try:
                    validate_json_body(bytes(raw))
                except (ValueError, UnicodeError, IndexError, RecursionError, ExtractionError):
                    raise HTTPException(422, "INVALID_OR_EXCESSIVE_EVIDENCE_JSON") from None
                if (
                    request.headers.get("content-type", "").split(";")[0].lower()
                    != "application/json"
                ):
                    raise HTTPException(415, "Evidence requests require application/json")
                received = False

                async def receive():
                    nonlocal received
                    if received:
                        return {"type": "http.disconnect"}
                    received = True
                    return {"type": "http.request", "body": bytes(raw), "more_body": False}

                request = Request(request.scope, receive)
            try:
                response = await handler(request)
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Content-Type-Options"] = "nosniff"
                return response
            except DBAPIError:
                raise HTTPException(503, "EVIDENCE_DATABASE_OR_QUERY_LIMIT") from None
            except ValidationError:
                raise HTTPException(422, "INVALID_EVIDENCE_INPUT_OR_SOURCE") from None
            except HTTPException as error:
                if error.status_code == 422 and isinstance(error.detail, list):
                    raise HTTPException(422, "INVALID_EVIDENCE_REQUEST") from None
                error.headers = {
                    **(error.headers or {}),
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                }
                raise

        return bounded


router = APIRouter(tags=["evidence"], route_class=EvidenceRoute)


def read_scope(
    request: Request,
    session: DB,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    settings = request.app.state.settings
    write = settings.document_api_token.get_secret_value() if settings.document_api_token else ""
    read = settings.case_read_token.get_secret_value() if settings.case_read_token else ""
    if len(write) < 32 or (read and secrets.compare_digest(write.encode(), read.encode())):
        raise HTTPException(503, "Configure distinct strong evidence access credentials")
    supplied = (
        authorization.removeprefix("Bearer ")
        if authorization and authorization.startswith("Bearer ")
        else ""
    )
    if not any(
        len(token) >= 32 and secrets.compare_digest(token.encode(), supplied.encode())
        for token in (write, read)
    ):
        raise HTTPException(
            401, "Evidence authentication required", headers={"WWW-Authenticate": "Bearer"}
        )
    org = settings.organization_id
    if org is None:
        raise HTTPException(503, "Configure company before evidence retrieval")
    begin_readonly(session, org)
    return company_scope(request, session)


ReadScope = Annotated[UUID, Depends(read_scope)]


@router.get("/cases/{case_id}/evidence/native/{kind}/{record_id}", response_model=NativePointer)
def native_pointer(
    case_id: UUID,
    record_id: UUID,
    kind: Literal["INVOICE", "REMITTANCE"],
    session: DB,
    org: ReadScope,
    request: Request,
    expected_case_version: int,
    expected_context_sha256: str,
    customer_id: UUID,
    expected_record_version: Annotated[int, Query(ge=1)],
    expected_source_sha256: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")],
    invoice_id: UUID | None = None,
):
    body = ScopeInput(
        expected_case_version=expected_case_version,
        expected_context_sha256=expected_context_sha256,
        customer_id=customer_id,
        invoice_id=invoice_id,
    )
    return EvidenceReader(session, org, request.app.state.settings).native_pointer(
        case_id, record_id, kind, body, expected_record_version, expected_source_sha256
    )


@router.post("/evidence/records", response_model=RecordView)
def ingest(body: RecordInput, session: DB, org: Scope, request: Request, actor: Actor, key: Key):
    return register(session, org, body, actor, key, request.app.state.settings)


@router.post("/cases/{case_id}/evidence/search", response_model=SearchResult)
def search(case_id: UUID, body: SearchInput, session: DB, org: ReadScope, request: Request):
    return TOOLS[body.tool](EvidenceReader(session, org, request.app.state.settings), case_id, body)


@router.post("/cases/{case_id}/evidence/verify", response_model=Verification)
def verify(case_id: UUID, body: VerifyInput, session: DB, org: ReadScope, request: Request):
    return EvidenceReader(session, org, request.app.state.settings).verify(case_id, body)


@router.get("/cases/{case_id}/evidence/records/{record_id}", response_model=RecordView)
def pointer(
    case_id: UUID,
    record_id: UUID,
    session: DB,
    org: ReadScope,
    request: Request,
    expected_case_version: int,
    expected_context_sha256: str,
    customer_id: UUID,
    invoice_id: UUID | None = None,
):
    scope = ScopeInput(
        expected_case_version=expected_case_version,
        expected_context_sha256=expected_context_sha256,
        customer_id=customer_id,
        invoice_id=invoice_id,
    )
    return EvidenceReader(session, org, request.app.state.settings).pointer(
        case_id, record_id, scope
    )
