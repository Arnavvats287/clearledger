"""Atomic, tenant-scoped CSV ingestion. No matching, seeding or GL recognition."""

import csv
import hashlib
import io
import json
import re
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clearledger.data_contract import CONTRACT_VERSION, INPUTS, MAX_BYTES, MAX_ROWS, timestamp
from clearledger.models import (
    AuditEvent,
    BankTransaction,
    Customer,
    Invoice,
    PayerAlias,
    Receipt,
    SourceImport,
)


class ImportFailure(Exception):
    def __init__(self, code: str, errors: list[dict], status_code: int = 422):
        self.code, self.errors, self.status_code = code, errors, status_code


def fail(code: str, row: int | None, field: str, message: str, status: int = 422):
    raise ImportFailure(code, [{"row": row, "field": field, "message": message}], status)


def parse_csv(kind: str, raw: bytes):
    if len(raw) > MAX_BYTES:
        fail("TOO_LARGE", None, "file", "Maximum file size is 2097152 bytes", 413)
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("INVALID_ENCODING", None, "file", "Expected UTF-8 CSV")
    schema = INPUTS[kind]
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    parsed, errors = [], []
    try:
        header = next(reader, [])
        if len(header) != len(set(header)) or set(header) != set(schema.model_fields):
            fail(
                "INVALID_HEADER", 1, "header", "Expected exactly: " + ",".join(schema.model_fields)
            )
        for number, values in enumerate(reader, 2):
            if number > MAX_ROWS + 1:
                fail("TOO_MANY_ROWS", number, "file", "Maximum 10000 data rows")
            if len(values) != len(header):
                errors.append({"row": number, "field": "row", "message": "Incorrect column count"})
            else:
                data = dict(zip(header, values, strict=True))
                try:
                    for field in data:
                        if field.endswith("_paise"):
                            if not re.fullmatch(r"0|[1-9][0-9]{0,18}", data[field]):
                                raise ValueError(field)
                            data[field] = int(data[field])
                    parsed.append((number, schema.model_validate(data)))
                except ValueError as exc:
                    if isinstance(exc, ValidationError):
                        errors.extend(
                            {
                                "row": number,
                                "field": ".".join(map(str, e["loc"])) or "row",
                                "message": e["msg"],
                            }
                            for e in exc.errors()
                        )
                    else:
                        errors.append(
                            {
                                "row": number,
                                "field": str(exc),
                                "message": "Expected unsigned integer paise",
                            }
                        )
            if len(errors) >= 100:
                break
    except csv.Error:
        fail("INVALID_CSV", reader.line_num, "file", "Malformed CSV or oversized field")
    if errors:
        raise ImportFailure("INVALID_ROWS", errors[:100])
    if not parsed:
        fail("EMPTY_IMPORT", None, "file", "At least one data row is required")
    return parsed


def canonical(row):
    data = row.model_dump(mode="json")
    for field in ("occurred_at", "verified_at"):
        if field in data:
            data[field] = timestamp(data[field]).isoformat()
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def event(
    session, organization_id, run_id, actor_id, event_type, entity_id=None, row=None, **details
):
    session.add(
        AuditEvent(
            organization_id=organization_id,
            source_import_id=run_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_id=entity_id,
            source_row=row,
            details=details,
        )
    )


def register_row(session, organization_id, run_id, actor_id, kind, number, row):
    data = row.model_dump()
    fingerprint = canonical(row)
    if kind == "customers":
        model = Customer
        conditions = [Customer.external_reference == row.external_reference]
        values = data
    elif kind in ("payer-aliases", "invoices"):
        customer = session.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.external_reference == row.customer_reference,
            )
        )
        if customer is None:
            fail(
                "UNKNOWN_CUSTOMER",
                number,
                "customer_reference",
                "Customer does not exist in this company",
            )
        data.pop("customer_reference")
        values = {**data, "customer_id": customer.id}
        if kind == "payer-aliases":
            model = PayerAlias
            normalized = " ".join(row.alias.split()).casefold()
            conditions = [PayerAlias.normalized_alias == normalized]
            values.update(normalized_alias=normalized, verified_at=timestamp(row.verified_at))
        else:
            model = Invoice
            conditions = [Invoice.invoice_number == row.invoice_number]
            values.update(
                initial_open_amount_paise=row.open_amount_paise,
                status="OPEN" if row.open_amount_paise else "CLOSED",
            )
    else:
        model = BankTransaction
        conditions = [
            BankTransaction.source_system == row.source_system,
            BankTransaction.account_ref == row.account_ref,
            BankTransaction.external_transaction_id == row.external_transaction_id,
        ]
        values = {
            **data,
            "occurred_at": timestamp(row.occurred_at),
            "occurred_at_source": row.occurred_at,
        }
    existing = session.scalar(
        select(model).where(model.organization_id == organization_id, *conditions)
    )
    if existing is not None:
        same = (
            existing.name == row.name
            if kind == "customers"
            else existing.payload_sha256 == fingerprint
        )
        if not same:
            fail(
                "IDENTITY_CONFLICT",
                number,
                "identity",
                "Existing source identity has different data; no overwrite permitted",
                409,
            )
        event(
            session,
            organization_id,
            run_id,
            actor_id,
            "import.duplicate",
            existing.id,
            number,
            kind=kind,
        )
        return existing.id, False, None
    if kind != "customers":
        values.update(source_import_id=run_id, source_row=number, payload_sha256=fingerprint)
    record = model(organization_id=organization_id, **values)
    session.add(record)
    session.flush()
    event(
        session,
        organization_id,
        run_id,
        actor_id,
        f"{model.__tablename__}.created",
        record.id,
        number,
    )
    receipt_id = None
    if kind == "bank-transactions":
        receipt = Receipt(
            organization_id=organization_id,
            bank_transaction_id=record.id,
            amount_paise=row.amount_paise,
            unapplied_amount_paise=row.amount_paise,
            currency="INR",
            status="UNAPPLIED",
        )
        session.add(receipt)
        session.flush()
        receipt_id = receipt.id
        event(session, organization_id, run_id, actor_id, "receipts.created", receipt.id, number)
    return record.id, True, receipt_id


def ingest(
    session: Session,
    *,
    organization_id: UUID,
    actor_id: str,
    kind: str,
    raw: bytes,
    source_name: str,
    idempotency_key: UUID,
    contract_version: str,
):
    """Serialize imports per company; commit data and audit atomically.

    The savepoint rolls back all business rows on error but preserves the outer
    company lock so a rejected run and its audit can be recorded without a race.
    """
    lock_key = int.from_bytes(hashlib.sha256(organization_id.bytes).digest()[:8], signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    digest = hashlib.sha256(raw).hexdigest()
    existing = session.scalar(
        select(SourceImport).where(
            SourceImport.organization_id == organization_id,
            SourceImport.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.content_sha256 != digest
            or existing.kind != kind
            or existing.contract_version != contract_version
        ):
            event(session, organization_id, existing.id, actor_id, "import.key_conflict")
            session.commit()
            return {
                "http_status": 409,
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "Use a new key for different content, kind or contract version",
            }
        event(session, organization_id, existing.id, actor_id, "import.replayed")
        result = existing.result.copy()
        session.commit()
        return result

    run_id = uuid4()
    metadata = dict(
        id=run_id,
        organization_id=organization_id,
        idempotency_key=idempotency_key,
        contract_version=contract_version,
        kind=kind,
        source_name=source_name,
        content_sha256=digest,
        raw_bytes=raw,
        actor_id=actor_id,
    )
    try:
        with session.begin_nested():
            if contract_version != CONTRACT_VERSION:
                fail("UNSUPPORTED_CONTRACT", None, "contract_version", "Supported version: 1.0")
            rows = parse_csv(kind, raw)
            run = SourceImport(**metadata, status="PROCESSING", row_count=len(rows), result={})
            session.add(run)
            session.flush()
            inserted = duplicates = receipts_created = 0
            ids = []
            for number, row in rows:
                record_id, created, receipt_id = register_row(
                    session,
                    organization_id,
                    run_id,
                    actor_id,
                    kind,
                    number,
                    row,
                )
                ids.append(str(record_id))
                inserted += int(created)
                duplicates += int(not created)
                receipts_created += int(receipt_id is not None)
            result = {
                "http_status": 200,
                "import_id": str(run_id),
                "status": "ACCEPTED",
                "row_count": len(rows),
                "inserted": inserted,
                "duplicates": duplicates,
                "receipts_created": receipts_created,
                "record_ids": ids,
            }
            run.status, run.result = "ACCEPTED", result
            event(
                session, organization_id, run_id, actor_id, "import.accepted", content_sha256=digest
            )
            session.flush()
    except (ImportFailure, IntegrityError) as exc:
        if isinstance(exc, IntegrityError):
            exc = ImportFailure(
                "CONSTRAINT_CONFLICT",
                [
                    {
                        "row": None,
                        "field": "row",
                        "message": "Database constraint conflict; entire import rejected",
                    }
                ],
                409,
            )
        result = {
            "http_status": exc.status_code,
            "import_id": str(run_id),
            "status": "REJECTED",
            "code": exc.code,
            "errors": exc.errors,
            "inserted": 0,
            "duplicates": 0,
            "receipts_created": 0,
        }
        session.add(SourceImport(**metadata, status="REJECTED", row_count=0, result=result))
        session.flush()
        event(
            session,
            organization_id,
            run_id,
            actor_id,
            "import.rejected",
            code=exc.code,
            content_sha256=digest,
        )
    session.commit()
    return result
