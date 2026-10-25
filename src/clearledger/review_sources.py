"""Read-only draft facts. A valid source pointer is not financial authorization."""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.case_models import Claim
from clearledger.case_repository import members
from clearledger.evidence_contract import ScopeInput
from clearledger.evidence_models import EvidenceRecord
from clearledger.evidence_reader import EvidenceReader, begin_readonly
from clearledger.matching import owned
from clearledger.models import Invoice


def draft_sources(engine, org, case_id, body, settings):
    with Session(engine) as session:
        begin_readonly(session, org)
        reader = EvidenceReader(session, org, settings)
        from clearledger.case_repository import root

        case = root(session, org, case_id)
        if case.customer_id is None:
            raise CaseError("VERIFIED_CASE_CUSTOMER_REQUIRED")
        scope = ScopeInput(
            expected_case_version=body.expected_case_version,
            expected_context_sha256=body.expected_context_sha256,
            customer_id=case.customer_id,
        )
        reader.scope(case_id, scope)
        invoices = []
        invoice_map = {}
        for identifier in body.invoice_ids:
            reader.scope(case_id, scope.model_copy(update={"invoice_id": identifier}))
            invoice = owned(session, Invoice, org, identifier)
            hit = reader.invoice_hit(invoice)
            if not hit.source_integrity or hit.metadata.get("privacy_review_required"):
                raise CaseError("DRAFT_INVOICE_SOURCE_INVALID")
            invoices.append(hit.model_dump(mode="json"))
            invoice_map[invoice.id] = invoice
        claims = []
        for identifier in body.claim_ids:
            claim = owned(session, Claim, org, identifier)
            if claim.case_id not in members(session, org, case):
                raise CaseError("CLAIM_CASE_MISMATCH", 404)
            claims.append(
                {
                    "id": str(claim.id),
                    "version": claim.version,
                    "category": claim.category,
                    "claimed_paise": claim.amount_paise,
                    "status": claim.state,
                    "authority": "UNVERIFIED_CUSTOMER_ASSERTION",
                }
            )
        deliveries = []
        for identifier in body.delivery_record_ids:
            row = owned(session, EvidenceRecord, org, identifier)
            hit = reader.document_hit(row)
            manifest = row.manifest
            invoice_id = UUID(manifest["invoice_id"]) if manifest.get("invoice_id") else None
            if (
                row.kind not in {"WMS", "POD"}
                or row.customer_id != case.customer_id
                or invoice_id not in invoice_map
                or manifest["date_basis"] != "INVOICE_ISSUED"
                or not hit.source_authenticated
                or not hit.source_integrity
                or not hit.is_current
                or not hit.metadata.get("signed")
                or not hit.metadata.get("approved")
                or hit.metadata.get("privacy_review_required")
            ):
                raise CaseError("DRAFT_VERIFIED_DELIVERY_REQUIRED")
            issued = invoice_map[invoice_id].issued_date
            if (
                not date.fromisoformat(manifest["effective_from"])
                <= issued
                <= date.fromisoformat(manifest["effective_to"])
            ):
                raise CaseError("DRAFT_DELIVERY_PERIOD_MISMATCH")
            deliveries.append(hit.model_dump(mode="json"))
        return {
            "case_id": str(case.id),
            "case_version": case.version,
            "context_sha256": case.context_sha256,
            "invoices": invoices,
            "claims": claims,
            "deliveries": deliveries,
            "source_authenticity": "PER_SOURCE_NOT_FINANCIAL_AUTHORITY",
        }
