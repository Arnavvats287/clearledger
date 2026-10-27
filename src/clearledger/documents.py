"""Transactional document orchestrator. Extractors receive strings, never this DB session."""

import hashlib
import time
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select

from clearledger.document_contract import (
    SCHEMA_VERSION,
    Extraction,
    ExtractionError,
    validate_semantics,
)
from clearledger.document_parse import PARSER_VERSION
from clearledger.document_privacy import PRIVACY_VERSION, project, restore
from clearledger.document_runtime import parse_bounded
from clearledger.extraction_provider import decode_output
from clearledger.gemini_schema import PROVIDER_SCHEMA_VERSION
from clearledger.matching import (
    bank_valid,
    build_snapshot,
    digest,
    lock_company,
    owned,
    read_statement,
)
from clearledger.models import (
    BankTransaction,
    Document,
    DocumentAssociation,
    DocumentEvent,
    DocumentExtraction,
    DocumentOperation,
    Invoice,
    Receipt,
)
from clearledger.provider_budget import reserve
from clearledger.provider_diagnostics import diagnostic
from clearledger.remittance_parser import deterministic


def semantic_cache_key(inputs):
    # Operational limits/prices/revision labels do not alter already validated source facts.
    keys = (
        "document_sha256",
        "canonical_sha256",
        "document_version",
        "parser_version",
        "schema_version",
        "privacy_version",
        "provider",
        "model",
        "review_reference_sha256",
    )
    return digest(
        {
            **{key: inputs[key] for key in keys},
            "max_output_tokens": inputs.get("max_output_tokens", 4096),
            "provider_schema_version": inputs.get("provider_schema_version", "strict-domain-v1"),
        }
    )


def successful_cached(session, org, doc, inputs):
    key = semantic_cache_key(inputs)
    rows = session.scalars(
        select(DocumentExtraction)
        .where(
            DocumentExtraction.organization_id == org,
            DocumentExtraction.document_id == doc.id,
            DocumentExtraction.error_code.is_(None),
            DocumentExtraction.status.in_(["SUCCEEDED", "NEEDS_REVIEW"]),
            DocumentExtraction.route == "LLM",
        )
        .order_by(DocumentExtraction.extraction_version.desc())
    )
    for row in rows:
        if row.result and semantic_cache_key(row.inputs) == key:
            facts = Extraction.model_validate(row.result)
            validate_semantics(facts, doc.pages)
            return row, facts
    return None


def operation(session, org, key, fingerprint, kind, document_id=None):
    row = session.scalar(
        select(DocumentOperation).where(
            DocumentOperation.organization_id == org,
            DocumentOperation.idempotency_key == key,
        )
    )
    if row is not None and (
        row.request_sha256 != fingerprint
        or row.operation != kind
        or (document_id is not None and row.document_id != document_id)
    ):
        raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
    return row


def audit(session, org, doc, actor, kind, entity, **details):
    entry = DocumentEvent(
        organization_id=org,
        document_id=doc.id,
        actor_id=actor,
        event_type=kind,
        entity_id=entity,
        details=details,
    )
    session.add(entry)
    session.flush()
    from clearledger.case_events import document_changed

    document_changed(session, entry)


def integrity(doc, store):
    raw = store.get(doc.organization_id, doc.content_sha256)
    if len(raw) != doc.size_bytes or digest(doc.pages) != doc.canonical_sha256:
        raise ExtractionError("DOCUMENT_INTEGRITY_FAILURE")
    return raw


def ingest_document(session, org, key, actor, raw, filename, mime, synthetic, store):
    lock_company(session, org)
    sha = hashlib.sha256(raw).hexdigest()
    fingerprint = digest({"sha": sha, "mime": mime, "synthetic": synthetic})
    prior = operation(session, org, key, fingerprint, "UPLOAD")
    if prior:
        doc = owned(session, Document, org, prior.document_id)
        integrity(doc, store)
        return doc
    doc = session.scalar(
        select(Document).where(Document.organization_id == org, Document.content_sha256 == sha)
    )
    if doc and (doc.mime != mime or doc.synthetic_approved != synthetic):
        raise HTTPException(409, "DOCUMENT_METADATA_CONFLICT")
    if not doc:
        store.put(org, raw)
        parse_error = None
        try:
            parsed = parse_bounded(raw, mime)
        except ExtractionError as error:
            parsed = {"pages": [], "status": "PARSE_FAILED", "parser_version": PARSER_VERSION}
            parse_error = str(error)
        doc = Document(
            organization_id=org,
            content_sha256=sha,
            canonical_sha256=digest(parsed["pages"]),
            source_name=filename,
            mime=mime,
            document_type="REMITTANCE",
            actor_id=actor,
            size_bytes=len(raw),
            synthetic_approved=synthetic,
            pages=parsed["pages"],
            parser_version=parsed["parser_version"],
            parse_status=parsed["status"],
            parse_error=parse_error,
        )
        session.add(doc)
        session.flush()
        audit(session, org, doc, actor, "document.ingested", doc.id, parse_status=doc.parse_status)
    else:
        integrity(doc, store)
    session.add(
        DocumentOperation(
            organization_id=org,
            document_id=doc.id,
            idempotency_key=key,
            request_sha256=fingerprint,
            operation="UPLOAD",
        )
    )
    session.commit()
    return doc


def extract_document(session, org, doc_id, key, actor, body, settings, store, gateway):
    lock_company(session, org)
    doc = owned(session, Document, org, doc_id)
    if doc.version != body.expected_document_version:
        raise HTTPException(409, "STALE_DOCUMENT_VERSION")
    fingerprint = digest({"operation": "EXTRACT", **body.model_dump(mode="json")})
    prior = operation(session, org, key, fingerprint, "EXTRACT", doc.id)
    inputs = {
        "document_sha256": doc.content_sha256,
        "canonical_sha256": doc.canonical_sha256,
        "document_version": doc.version,
        "parser_version": doc.parser_version,
        "schema_version": SCHEMA_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "revision_label": body.revision_label,
        "allow_external": body.allow_external,
        "provider": settings.extraction_provider,
        "model": settings.gemini_model,
        "external_enabled": settings.external_ai_enabled,
        "review_reference_sha256": digest(settings.privacy_review_reference),
        "timeout_ms": settings.llm_timeout_ms,
        "attempts": settings.llm_attempts,
        "rpm": settings.llm_requests_per_minute,
        "input_rate": settings.llm_input_paise_per_million_tokens,
        "output_rate": settings.llm_output_paise_per_million_tokens,
        "max_input_tokens": settings.llm_max_input_tokens,
        "max_output_tokens": settings.llm_max_output_tokens,
        "daily_requests": settings.llm_daily_requests,
        "daily_input_tokens": settings.llm_daily_input_tokens,
        "daily_output_tokens": settings.llm_daily_output_tokens,
        "shared_rpm": settings.llm_shared_requests_per_minute,
        "max_cost_paise": settings.llm_max_cost_paise_per_attempt,
    }
    if settings.extraction_provider == "gemini":
        inputs["provider_schema_version"] = PROVIDER_SCHEMA_VERSION
        if gateway is not None and getattr(gateway.transport, "task", "") == "remittance_grounded":
            from clearledger.grounded_extraction import VERSION as GROUNDED_VERSION

            inputs["provider_schema_version"] = GROUNDED_VERSION
    input_hash = digest(inputs)
    if prior:
        row = owned(session, DocumentExtraction, org, prior.extraction_id)
        if row.input_sha256 != input_hash:
            raise HTTPException(409, "STALE_EXTRACTION_CONFIGURATION")
        integrity(doc, store)
        return row
    row = session.scalar(
        select(DocumentExtraction).where(
            DocumentExtraction.organization_id == org,
            DocumentExtraction.document_id == doc.id,
            DocumentExtraction.input_sha256 == input_hash,
        )
    )
    if row:
        integrity(doc, store)
    else:
        route, reason, status, error_code, result = (
            "REVIEW",
            "SEMANTIC_EXTRACTION_REQUIRED",
            "NEEDS_REVIEW",
            None,
            {},
        )
        started = time.perf_counter_ns()
        metrics = {
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost_paise": None,
            "usage_complete": False,
            "attempts": 0,
        }
        failure_phase = "SOURCE_VALIDATION"
        try:
            integrity(doc, store)
            if doc.parse_status != "READY":
                reason = doc.parse_status
            else:
                extracted = deterministic(doc.pages, doc.mime)
                if extracted is not None:
                    route, reason = "DETERMINISTIC", "RELIABLE_STRUCTURED_FORMAT"
                elif body.allow_external:
                    if (
                        not doc.synthetic_approved
                        or not settings.external_ai_enabled
                        or not settings.privacy_review_reference
                        or gateway is None
                        or settings.extraction_provider not in {"gemini", "fake"}
                    ):
                        raise ExtractionError("EXTERNAL_AI_DISABLED_OR_UNAPPROVED")
                    route, reason = "LLM", "SEMANTIC_EXTRACTION_REQUIRED"
                    projected = project(doc.pages)
                    cached = successful_cached(session, org, doc, inputs)
                    if cached is not None:
                        previous, extracted = cached
                        metrics.update(
                            cache_hit=True,
                            cached_from_extraction_id=str(previous.id),
                            attempts=0,
                            input_tokens=0,
                            output_tokens=0,
                            total_tokens=0,
                            usage_complete=True,
                            estimated_cost_paise=0,
                        )
                        reason = "VALIDATED_RESULT_REUSED"
                    else:
                        reply, usage = gateway.generate(
                            projected.pages,
                            **(
                                {
                                    "source_context": {
                                        "source_id": f"{org}/{doc.id}",
                                        "source_hash": doc.canonical_sha256,
                                        "version": str(doc.version),
                                    }
                                }
                                if getattr(getattr(gateway, "transport", None), "task", "")
                                == "remittance_grounded"
                                else {}
                            ),
                            before_attempt=lambda: reserve(
                                session.get_bind(), org, settings.extraction_provider, settings
                            ),
                        )
                        metrics.update(usage)
                        failure_phase = "RESPONSE_DECODING"
                        decoded = decode_output(reply.json_text)
                        failure_phase = "SCHEMA_VALIDATION"
                        extracted = Extraction.model_validate(decoded)
                        failure_phase = "SOURCE_VALIDATION"
                        extracted = restore(extracted, projected.pages, doc.pages)
                        validate_semantics(extracted, doc.pages)
                    counts = {}
                    for mask in projected.masks:
                        counts[mask.kind] = counts.get(mask.kind, 0) + 1
                    metrics["redaction_counts"] = counts
                if extracted is not None:
                    result = extracted.model_dump(mode="json")
                    # Parsing/source consistency never implies authenticity or legitimacy.
                    status = "SUCCEEDED" if extracted.uncertainty == "none" else "NEEDS_REVIEW"
        except ExtractionError as error:
            metrics.update(getattr(error, "metrics", {}))
            metrics.setdefault("diagnostic", diagnostic(failure_phase, "DOMAIN_VALIDATION"))
            error_code = str(error)
            status = (
                "BLOCKED"
                if error_code.startswith(
                    (
                        "EXTERNAL_",
                        "PRIVACY_",
                        "DOCUMENT_",
                        "ORIGINAL_",
                        "PROVIDER_DAILY_",
                        "PROVIDER_SHARED_",
                    )
                )
                else "FAILED"
            )
            reason = "CONTROLLED_EXTRACTION_FAILURE"
        except (ValueError, TypeError, IndexError, RecursionError):
            metrics["diagnostic"] = diagnostic(failure_phase, "VALIDATION")
            status, error_code, reason = (
                "FAILED",
                "INVALID_EXTRACTION_OUTPUT",
                "CONTROLLED_EXTRACTION_FAILURE",
            )
        metrics["latency_ms"] = int((time.perf_counter_ns() - started) / 1_000_000)
        version = (
            session.scalar(
                select(func.coalesce(func.max(DocumentExtraction.extraction_version), 0)).where(
                    DocumentExtraction.organization_id == org,
                    DocumentExtraction.document_id == doc.id,
                )
            )
            + 1
        )
        row = DocumentExtraction(
            organization_id=org,
            document_id=doc.id,
            extraction_version=version,
            input_sha256=input_hash,
            schema_version=SCHEMA_VERSION,
            route=route,
            reason=reason,
            provider=settings.extraction_provider if route == "LLM" else "none",
            model=settings.gemini_model if route == "LLM" else None,
            status=status,
            error_code=error_code,
            inputs=inputs,
            result=result,
            metrics=metrics,
        )
        session.add(row)
        session.flush()
        audit(session, org, doc, actor, "document.extracted", row.id, route=route, status=status)
    session.add(
        DocumentOperation(
            organization_id=org,
            document_id=doc.id,
            idempotency_key=key,
            request_sha256=fingerprint,
            operation="EXTRACT",
            extraction_id=row.id,
        )
    )
    session.commit()
    return row


def association_context(session, org, doc, extraction, verified_values, store):
    integrity(doc, store)
    latest_version = session.scalar(
        select(func.max(DocumentExtraction.extraction_version)).where(
            DocumentExtraction.organization_id == org,
            DocumentExtraction.document_id == doc.id,
        )
    )
    references = sorted({row["value"] for row in extraction.result.get("utr_references", [])})
    if verified_values and set(verified_values) != set(references):
        raise HTTPException(422, "VERIFIED_REFERENCES_MUST_EQUAL_EXTRACTED_SET")
    rows = session.execute(
        read_statement(
            session,
            select(Receipt, BankTransaction)
            .join(
                BankTransaction,
                (Receipt.bank_transaction_id == BankTransaction.id)
                & (Receipt.organization_id == BankTransaction.organization_id),
            )
            .where(
                Receipt.organization_id == org,
                BankTransaction.organization_id == org,
                BankTransaction.external_transaction_id.in_(references),
            )
            .order_by(Receipt.id)
            .limit(101),
        )
    ).all()
    candidates = [
        {
            "receipt_id": str(receipt.id),
            "receipt_version": receipt.version,
            "bank_id": str(bank.id),
            "payload_sha256": bank.payload_sha256,
            "reference": bank.external_transaction_id,
            "source_valid": bank_valid(session, org, bank) if len(rows) == 1 else None,
        }
        for receipt, bank in rows
    ]
    invoice_refs = sorted({row["value"] for row in extraction.result.get("invoice_references", [])})
    invoice_rows = session.scalars(
        read_statement(
            session,
            select(Invoice)
            .where(
                Invoice.organization_id == org,
                Invoice.invoice_number.in_(invoice_refs),
            )
            .order_by(Invoice.invoice_number),
        )
    ).all()
    unknown_invoices = sorted(set(invoice_refs) - {row.invoice_number for row in invoice_rows})
    owners = {str(row.customer_id) for row in invoice_rows}
    identity_hash, identity_conflict = None, False
    if len(rows) == 1:
        _, _, identity = build_snapshot(session, org, rows[0][0].id)
        identity_hash = digest(identity)
        decision = identity["decision"]
        identity_conflict = (
            decision["identity"] == "AMBIGUOUS"
            or decision["reason"] in {"STALE_OR_INVALID_EVIDENCE", "AMBIGUOUS_OR_BUDGET_EXCEEDED"}
            or (owners and decision["customers"] and owners != set(decision["customers"]))
        )
    inputs = {
        "document_version": doc.version,
        "raw_sha256": doc.content_sha256,
        "canonical_sha256": doc.canonical_sha256,
        "extraction_id": str(extraction.id),
        "extraction_version": extraction.extraction_version,
        "latest_extraction_version": latest_version,
        "references": references,
        "verified_utr_values": sorted(set(verified_values)),
        "candidates": candidates,
        "invoice_references": [
            {
                "id": str(row.id),
                "number": row.invoice_number,
                "customer_id": str(row.customer_id),
                "version": row.version,
            }
            for row in invoice_rows
        ],
        "unknown_invoice_references": unknown_invoices,
        "identity_snapshot_sha256": identity_hash,
    }
    status, target, reason = "UNRESOLVED", None, "NO_EXACT_REFERENCE_MATCH"
    if len(candidates) > 100:
        status, reason = "SEARCH_INCOMPLETE", "CANDIDATE_LIMIT"
    elif candidates:
        status, reason = "CANDIDATES", "UNVERIFIED_OR_AMBIGUOUS_REFERENCE"
        if (
            len(candidates) == 1
            and len(references) == 1
            and verified_values
            and candidates[0]["source_valid"]
            and extraction.status == "SUCCEEDED"
            and extraction.extraction_version == latest_version
            and not unknown_invoices
            and len(owners) <= 1
            and not identity_conflict
        ):
            status, target, reason = (
                "LINKED",
                UUID(candidates[0]["receipt_id"]),
                "LOCALLY_ATTESTED_UNIQUE_REFERENCE",
            )
        elif unknown_invoices:
            reason = "UNKNOWN_INVOICE_REFERENCES"
        elif identity_conflict or len(owners) > 1:
            reason = "CONFLICTING_CUSTOMER_REFERENCES"
        elif extraction.extraction_version != latest_version:
            reason = "SUPERSEDED_EXTRACTION"
    return inputs, status, target, reason


def correlate(session, org, doc_id, key, actor, body, store):
    lock_company(session, org)
    from clearledger.correlation_models import CorrelationTask

    if (
        session.scalar(
            select(CorrelationTask.id)
            .where(CorrelationTask.organization_id == org, CorrelationTask.document_id == doc_id)
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(409, "CORRELATION_REVIEW_REQUIRED")
    doc = owned(session, Document, org, doc_id)
    extraction = owned(session, DocumentExtraction, org, body.extraction_id)
    if extraction.document_id != doc.id:
        raise HTTPException(422, "EXTRACTION_DOCUMENT_MISMATCH")
    if body.expected_document_version != doc.version:
        raise HTTPException(409, "STALE_DOCUMENT_VERSION")
    fingerprint = digest({"operation": "CORRELATE", **body.model_dump(mode="json")})
    prior = operation(session, org, key, fingerprint, "CORRELATE", doc.id)
    inputs, status, receipt_id, reason = association_context(
        session,
        org,
        doc,
        extraction,
        body.verified_utr_values,
        store,
    )
    for identifier, version in body.expected_receipt_versions.items():
        if owned(session, Receipt, org, identifier).version != version:
            raise HTTPException(409, "STALE_RECEIPT_VERSION")
    if receipt_id is not None and receipt_id not in body.expected_receipt_versions:
        raise HTTPException(409, "EXPECTED_RECEIPT_VERSION_REQUIRED")
    input_hash = digest(inputs)
    if prior:
        row = owned(session, DocumentAssociation, org, prior.association_id)
        if row.input_sha256 != input_hash:
            raise HTTPException(409, "STALE_ASSOCIATION")
        return row
    row = session.scalar(
        select(DocumentAssociation).where(
            DocumentAssociation.organization_id == org,
            DocumentAssociation.document_id == doc.id,
            DocumentAssociation.input_sha256 == input_hash,
        )
    )
    if row is None:
        row = DocumentAssociation(
            organization_id=org,
            document_id=doc.id,
            extraction_id=extraction.id,
            receipt_id=receipt_id,
            status=status,
            input_sha256=input_hash,
            inputs=inputs,
            result={
                "reason": reason,
                "candidates": inputs["candidates"],
                "financial_authority": False,
            },
        )
        session.add(row)
        session.flush()
        audit(session, org, doc, actor, "document.correlated", row.id, status=status)
    session.add(
        DocumentOperation(
            organization_id=org,
            document_id=doc.id,
            idempotency_key=key,
            request_sha256=fingerprint,
            operation="CORRELATE",
            association_id=row.id,
        )
    )
    session.commit()
    return row
