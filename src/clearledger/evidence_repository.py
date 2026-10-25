"""Scoped bounded SQL, never supplied by callers or exposed as a tool."""

from sqlalchemy import exists, func, select
from sqlalchemy.orm import aliased

from clearledger.case_domain import CaseError
from clearledger.evidence_models import EvidenceRecord

BUDGET = 200


def latest_clause():
    successor = aliased(EvidenceRecord)
    return ~exists(
        select(successor.id).where(
            successor.organization_id == EvidenceRecord.organization_id,
            successor.previous_id == EvidenceRecord.id,
        )
    )


def candidates(
    session,
    org,
    customer_id,
    kinds=None,
    invoice_id=None,
    query="",
    after_id=None,
    limit=BUDGET,
    invoice_ids=None,
):
    statement = select(EvidenceRecord).where(
        EvidenceRecord.organization_id == org,
        EvidenceRecord.customer_id == customer_id,
        latest_clause(),
    )
    if kinds:
        statement = statement.where(EvidenceRecord.kind.in_(kinds))
    if invoice_id:
        statement = statement.where(
            (EvidenceRecord.invoice_id == invoice_id) | EvidenceRecord.invoice_id.is_(None)
        )
    elif invoice_ids is not None:
        statement = statement.where(
            EvidenceRecord.invoice_id.is_(None) | EvidenceRecord.invoice_id.in_(invoice_ids)
        )
    if query:
        statement = statement.where(
            EvidenceRecord.search_vector.op("@@")(func.plainto_tsquery("simple", query))
        )
    if after_id:
        statement = statement.where(EvidenceRecord.id > after_id)
    return list(session.scalars(statement.order_by(EvidenceRecord.id).limit(limit + 1)))


def current(session, org, row):
    return (
        session.scalar(
            select(EvidenceRecord.id).where(
                EvidenceRecord.organization_id == org, EvidenceRecord.previous_id == row.id
            )
        )
        is None
    )


def case_facts(session, org, customer_ids, invoice_ids, store):
    if len(customer_ids) != 1:
        return []
    rows = candidates(session, org, next(iter(customer_ids)), limit=200, invoice_ids=invoice_ids)
    if len(rows) > 200 or len({r.document_id for r in rows}) > 100:
        raise CaseError("CASE_ANALYSIS_LIMIT")
    from clearledger.document_contract import ExtractionError
    from clearledger.documents import integrity
    from clearledger.matching import owned
    from clearledger.models import Document, Invoice

    valid = {}
    for row in rows:
        if row.document_id not in valid:
            try:
                integrity(owned(session, Document, org, row.document_id), store)
                valid[row.document_id] = True
            except ExtractionError:
                valid[row.document_id] = False
    return [
        {
            "id": str(r.id),
            "revision": r.revision,
            "sha256": r.content_sha256,
            "integrity": valid[r.document_id],
            "categories": r.manifest["categories"],
            "invoice_number": owned(session, Invoice, org, r.invoice_id).invoice_number
            if r.invoice_id
            else None,
        }
        for r in rows
    ]
