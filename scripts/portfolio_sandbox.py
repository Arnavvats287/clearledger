"""Public, ephemeral document and fixed-fixture AI boundary."""

import asyncio
import json
import re
from hashlib import sha256
from threading import BoundedSemaphore
from urllib.parse import unquote
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from portfolio_sessions import AdmissionError, Sessions
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from clearledger.case_domain import CaseError
from clearledger.document_contract import (
    MAX_DOCUMENT_BYTES,
    Extraction,
    ExtractionError,
    validate_semantics,
)
from clearledger.document_privacy import project, restore
from clearledger.document_runtime import parse_bounded
from clearledger.extraction_provider import GeminiTransport, ProviderFailure, decode_output
from clearledger.investigation_ai import basis, default_plan, validate_synthesis
from clearledger.investigation_ai_contract import ARReply
from clearledger.investigation_contract import Objective, OfferedPointer
from clearledger.investigation_director import consistency
from clearledger.investigation_grounding import validate_span_selection
from clearledger.remittance_parser import deterministic
from clearledger.source_presentations import canonical, investigation_packet
from clearledger.source_spans import GroundingError, span_packet, text_source

MODEL = "gemini-3.5-flash-lite"
MIME = {
    ".txt": "text/plain",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".eml": "message/rfc822",
}
HEADERS = [
    "Content-Type",
    "Authorization",
    "X-Portfolio-Filename",
    "X-Portfolio-Consent",
    "X-Portfolio-Gemini-Consent",
    "X-Portfolio-Gemini-Key",
]
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MAX_AI_CHARS = 6000
SLOTS = BoundedSemaphore(1)


def response(data, status=200):
    return JSONResponse(data, status_code=status, headers=NO_STORE)


def transport(key, task):
    # A new isolated worker per invocation. No gateway cache, DB config or retry.
    return GeminiTransport(
        key, MODEL, 8000, max_input_tokens=8192, max_output_tokens=2048, task=task
    )


def extract_upload(raw, mime, filename, key, reserve):
    parsed = parse_bounded(raw, mime)
    pages, status = parsed["pages"], parsed["status"]
    if key is not None and any(key in page for page in pages):
        raise AdmissionError(422, "DOCUMENT_CONTAINS_CREDENTIAL")
    offline = None
    if status == "READY":
        try:
            offline = deterministic(pages, mime)
        except (ExtractionError, ValidationError, ValueError):
            pass
    result = {
        "filename": filename,
        "mime": mime,
        "pages": pages,
        "parse_status": status,
        "deterministic_status": "SOURCE_CHECKED" if offline is not None else "ABSTAINED",
        "extraction": offline.model_dump(mode="json") if offline is not None else None,
        "ai": None,
        "financial_authority": False,
    }
    if key is None or status != "READY":
        return result
    ai = {"model": MODEL, "proposal": None, "validated": None, "status": "BLOCKED"}
    result["ai"] = ai
    if sum(map(len, pages)) > MAX_AI_CHARS:
        return result
    try:
        projected = project(pages)
        if any(mask.kind != "UNNECESSARY_CONTENT" for mask in projected.masks):
            return result
    except ExtractionError:
        return result
    reserve()
    try:
        reply = transport(key, "remittance_grounded").generate_for_source(
            projected.pages,
            {"source_id": "sandbox-upload", "source_hash": sha256(raw).hexdigest(), "version": "1"},
        )
        proposal = Extraction.model_validate(decode_output(reply.json_text))
        ai["proposal"] = proposal.model_dump(mode="json")
        verified = restore(proposal, projected.pages, pages)
        validate_semantics(verified, pages)
        ai["validated"] = verified.model_dump(mode="json")
        ai["status"] = "SOURCE_CHECKED" if verified.uncertainty == "none" else "ABSTAINED"
    except ProviderFailure:
        ai["status"] = "PROVIDER_UNAVAILABLE"
    except (ExtractionError, ValidationError, GroundingError, ValueError, TypeError):
        ai["status"] = "REJECTED"
    return result


def included_run(key):
    # Code-owned demo source only. The absent POD is part of this fixed case.
    raw = "Invoice INV-2026-1042. Warehouse record: 3 damaged units at INR 1000.00 per unit."
    source = text_source(
        "portfolio-bundled-warehouse", [raw], source_hash=sha256(raw.encode()).hexdigest()
    )
    record_id, document_id, claim_id = (UUID(int=i) for i in (1, 2, 3))
    record = str(record_id)
    objective = Objective(
        claim_id=claim_id,
        claim_version=1,
        category="damage",
        amount_paise=300000,
        basis_sha256=source.source_hash,
        invoice_id=None,
        question="DELIVERY_DAMAGE",
        tools=["get_wms_deliveries", "get_proof_of_delivery"],
        unknowns=[],
    )
    pointer = OfferedPointer(
        record_id=record_id,
        document_id=document_id,
        document_version=1,
        raw_sha256=source.source_hash,
        canonical_sha256=source.source_hash,
        page=1,
        start=0,
        end=len(raw),
        excerpt=raw,
    )
    finding = consistency(objective, None, None, [pointer])
    summaries = [
        {
            "record_id": record,
            "kind": "WMS",
            "facts": {"damaged_quantity": 3, "unit_value_paise": 100000},
        }
    ]
    catalog = [{"record_id": record, **span_packet(span)} for span in source.spans]
    packet, aliases = investigation_packet(
        {
            "phase": "investigator_synthesize",
            "objective": basis(objective),
            "plan": default_plan(objective).model_dump(mode="json"),
            "required_evidence_types": ["WMS", "POD"],
            "verified_assessment": {"outcomes": [], "reasons": ["MISSING_SIGNED_POD"]},
            "evidence": summaries,
            "evidence_spans": catalog,
            "record_ids": [record],
            "document_ids": [str(document_id)],
        }
    )
    offers = [
        {"alias": row["span_id"], "quote": row["text"], "page": row["page"]}
        for row in packet["evidence_spans"]
    ]
    result = {
        "model": MODEL,
        "status": "PROVIDER_UNAVAILABLE",
        "proposal": None,
        "offered": offers,
        "citations": [],
        "finding": finding.state,
        "next_action": finding.next_action,
        "amount_paise": objective.amount_paise,
        "financial_authority": False,
    }
    try:
        reply = transport(key, "investigation_ar").generate([json.dumps(packet)])
        # Decode with the existing duplicate-key guard before validating the
        # JSON representation of typed UUID fields.
        value = ARReply.model_validate_json(json.dumps(decode_output(reply.json_text)))
        if value.synthesis is None or value.plan is not None:
            raise CaseError("INVALID_AI_SYNTHESIS")
        synthesis = value.synthesis
        result["proposal"] = {"state": synthesis.state, "next_action": synthesis.next_action}
        resolved = synthesis.model_copy(
            update={
                "evidence_span_ids": [
                    canonical(alias, aliases) for alias in synthesis.evidence_span_ids
                ]
            }
        )
        validate_span_selection(resolved, {record: source}, catalog, required=True)
        validate_synthesis(resolved, objective, finding, summaries)
        result["citations"] = [row for row in offers if row["alias"] in synthesis.evidence_span_ids]
        result["status"] = "SOURCE_CHECKED"
    except ProviderFailure:
        pass
    except (CaseError, ExtractionError, GroundingError, ValidationError, ValueError):
        result["status"] = "REJECTED"
    return result


def mount(app: FastAPI, sessions: Sessions, origin: str, included_key: str | None):
    def token(request):
        value = request.headers.get("authorization", "")
        return value[len("Portfolio ") :] if value.startswith("Portfolio ") else ""

    def origin_required(request):
        if request.headers.get("origin") != origin:
            raise AdmissionError(403, "PORTFOLIO_ORIGIN_REQUIRED")

    @app.exception_handler(AdmissionError)
    async def admission_error(_request, error):
        return response({"detail": error.code}, error.status)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, _error):
        return response({"detail": "PORTFOLIO_API_UNAVAILABLE"}, 503)

    @app.post("/portfolio/session")
    async def sign_in(request: Request):
        origin_required(request)
        await bounded_body(request, 0)
        return response({"access_token": await run_in_threadpool(sessions.create)})

    @app.get("/portfolio/session")
    def who(request: Request):
        sessions.check(token(request))
        return response(
            {
                "subject": "portfolio-analyst",
                "role": "AUDITOR",
                "authority": "LOCAL_DEMO_ONLY",
                "financial_authority": False,
                "included_available": included_key is not None,
            }
        )

    @app.delete("/portfolio/session")
    def sign_out(request: Request):
        origin_required(request)
        sessions.revoke(token(request))
        return response({"signed_out": True})

    @app.post("/portfolio/extract")
    async def extract(request: Request):
        origin_required(request)
        if request.headers.get("x-portfolio-consent") != "true":
            raise AdmissionError(422, "DOCUMENT_CONSENT_REQUIRED")
        header = request.headers.get("x-portfolio-filename", "")
        basename = unquote(header).replace("\\", "/").rsplit("/", 1)[-1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,119}", basename):
            raise AdmissionError(422, "INVALID_DOCUMENT_FILENAME")
        _, separator, suffix = basename.rpartition(".")
        extension = separator + suffix.lower()
        mime = MIME.get(extension)
        if mime is None or request.headers.get("content-type") != mime:
            raise AdmissionError(415, "UNSUPPORTED_DOCUMENT_TYPE")
        key = request.headers.get("x-portfolio-gemini-key")
        if key is not None and (
            request.headers.get("x-portfolio-gemini-consent") != "true"
            or not re.fullmatch(r"[A-Za-z0-9_-]{20,180}", key)
        ):
            raise AdmissionError(422, "GEMINI_KEY_OR_CONSENT_REQUIRED")
        identifier = await run_in_threadpool(sessions.check, token(request))
        if not SLOTS.acquire(blocking=False):
            raise AdmissionError(429, "SANDBOX_BUSY")
        try:
            raw = await bounded_body(request, MAX_DOCUMENT_BYTES)
            if not raw:
                raise AdmissionError(422, "EMPTY_DOCUMENT")
            if key is not None and (key.encode() in raw or key in basename):
                raise AdmissionError(422, "DOCUMENT_CONTAINS_CREDENTIAL")
            await run_in_threadpool(sessions.reserve, identifier, "uploads")
            try:
                result = await run_in_threadpool(
                    extract_upload,
                    raw,
                    mime,
                    basename,
                    key,
                    lambda: sessions.reserve(identifier, "byok"),
                )
                if key is not None and key in json.dumps(result):
                    raise AdmissionError(422, "DOCUMENT_CONTAINS_CREDENTIAL")
                return response(result)
            except ExtractionError:
                raise AdmissionError(422, "DOCUMENT_PARSE_FAILED") from None
            except (AdmissionError, SQLAlchemyError):
                raise
            except Exception:
                return response({"detail": "SANDBOX_PROCESSING_FAILED"}, 503)
        finally:
            SLOTS.release()

    @app.post("/portfolio/included")
    async def included(request: Request):
        origin_required(request)
        await bounded_body(request, 0)
        identifier = await run_in_threadpool(sessions.check, token(request))
        if included_key is None:
            raise AdmissionError(409, "DEMO_GEMINI_NOT_CONFIGURED")
        if not SLOTS.acquire(blocking=False):
            raise AdmissionError(429, "SANDBOX_BUSY")
        try:
            await run_in_threadpool(sessions.reserve, identifier, "included")
            try:
                return response(await run_in_threadpool(included_run, included_key))
            except Exception:
                return response({"detail": "SANDBOX_PROCESSING_FAILED"}, 503)
        finally:
            SLOTS.release()


async def bounded_body(request: Request, maximum: int) -> bytes:
    size = request.headers.get("content-length")
    if size is not None and (not re.fullmatch(r"[0-9]{1,10}", size) or int(size) > maximum):
        raise AdmissionError(413, "REQUEST_TOO_LARGE")
    result = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                if len(result) + len(chunk) > maximum:
                    raise AdmissionError(413, "REQUEST_TOO_LARGE")
                result.extend(chunk)
    except TimeoutError:
        raise AdmissionError(408, "UPLOAD_TIMEOUT") from None
    return bytes(result)
