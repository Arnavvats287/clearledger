"""Read-only deterministic policy evaluation; source facts never become legal authority."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.case_models import Claim
from clearledger.case_repository import members, scoped
from clearledger.evidence_contract import ScopeInput, VerifyInput
from clearledger.evidence_domain import authenticated, validity
from clearledger.evidence_reader import EvidenceReader, begin_readonly
from clearledger.evidence_repository import candidates
from clearledger.finance_contract import ProposalInput, Treatment
from clearledger.finance_domain import ALGORITHM, compose
from clearledger.finance_models import FinanceSourceReview, NoncashSettlement
from clearledger.finance_repository import base, policy, recognition
from clearledger.investigation_director import PRIMARY
from clearledger.investigation_models import InvestigationFinding
from clearledger.investigation_service import finding_current
from clearledger.matching import digest, owned
from clearledger.models import Document, Invoice


def trust_digest(settings):
    return digest(
        {
            "trust": settings.evidence_trusted_sources_json.get_secret_value()
            if settings.evidence_trusted_sources_json
            else None
        }
    )


def treatment(reader, case, bank, body, binding, spec):
    session, org = reader.session, reader.org
    claim = owned(session, Claim, org, binding.claim_id)
    invoice = owned(session, Invoice, org, binding.invoice_id)
    if claim.case_id not in members(session, org, case) or binding.invoice_id not in {
        a.invoice_id for a in body.cash
    }:
        raise CaseError("CLAIM_OUTSIDE_FINANCE_APPLICATION", 404)
    if claim.state == "RESOLVED" or scoped(session, NoncashSettlement, org, claim_id=claim.id):
        raise CaseError("CLAIM_ALREADY_SETTLED")
    if binding.finding_id:
        finding = owned(session, InvestigationFinding, org, binding.finding_id)
        if (
            finding.claim_id != claim.id
            or not finding_current(session, org, finding, reader.settings)
            or finding.value.get("state") != "SUPPORTED"
        ):
            raise CaseError("UNSUPPORTED_OR_STALE_AI_RECOMMENDATION")
    scope = ScopeInput(
        expected_case_version=case.version,
        expected_context_sha256=case.context_sha256,
        customer_id=case.customer_id,
        claim_id=claim.id,
        invoice_id=invoice.id,
    )
    reader.scope(case.id, scope)
    claim_hits = [
        h
        for h in reader.remittance_hits(members(session, org, case), invoice.id)
        if h.id == claim.id
    ]
    if (
        len(claim_hits) != 1
        or not claim_hits[0].source_integrity
        or not claim_hits[0].is_current
        or claim_hits[0].metadata["invoice_reference_count"] != 1
        or claim_hits[0].metadata["extraction_uncertainty"] != "none"
    ):
        raise CaseError("CLAIM_SOURCE_INVALID")
    result = Treatment(
        claim_id=claim.id,
        invoice_id=invoice.id,
        category=claim.category,
        amount_paise=claim.amount_paise,
        allowed_paise=0,
        state="NEEDS_TAX_REVIEW" if claim.category == "tax" else "INSUFFICIENT_EVIDENCE",
        rule_id=binding.rule_id,
        treatment=None,
        evidence_ids=[],
        reasons=["REVIEWED_POLICY_REQUIRED"],
    )
    rule = next((r for r in spec.rules if r.id == binding.rule_id), None)
    receipt_date = bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    if rule is None:
        return result
    if (
        not rule.approved_fixture
        or rule.case_id != case.id
        or rule.customer_id != case.customer_id
        or rule.invoice_id != invoice.id
        or rule.claim_id != claim.id
        or rule.category != claim.category
        or rule.amount_paise != claim.amount_paise
        or not rule.effective_from <= receipt_date <= rule.effective_to
    ):
        result.reasons = ["RULE_PRECONDITIONS_NOT_ESTABLISHED"]
        return result
    if not owned(session, Document, org, claim.document_id).synthetic_approved:
        result.reasons = ["APPROVED_SYNTHETIC_FIXTURE_REQUIRED"]
        return result
    pointers = [reader.pointer(case.id, identifier, scope) for identifier in rule.required_evidence]
    for pointer in pointers:
        record = pointer.manifest
        as_of = invoice.issued_date if record.date_basis == "INVOICE_ISSUED" else receipt_date
        if (
            not pointer.source_authenticated
            or not pointer.is_current
            or validity(
                record,
                authenticated(org, record, reader.sources),
                pointer.is_current,
                as_of,
                datetime.now(UTC),
            )
            or claim.category not in record.categories
            or not owned(session, Document, org, record.document_id).synthetic_approved
        ):
            result.reasons = ["EVIDENCE_UNVERIFIED_OR_NOT_APPLICABLE"]
            return result
    if claim.category == "tax":
        if rule.date_of_deduction != receipt_date:
            result.reasons = ["DEDUCTION_DATE_REQUIRES_REVIEW"]
            return result
        records = candidates(session, org, case.customer_id, {"TAX"}, invoice.id)
        if len(records) > 200:
            result.reasons = ["TAX_EVIDENCE_SEARCH_INCOMPLETE"]
            return result
        if not set(rule.required_evidence).issubset({r.id for r in records}):
            result.reasons = ["TAX_SOURCE_REQUIRED"]
            return result
        expected = "INCOME_TAX_TDS" if rule.treatment == "INCOME_TAX" else "GST_TDS"
        relevant = []
        for row in records:
            pointer = reader.pointer(case.id, row.id, scope)
            source = pointer.manifest
            if source.fact.type != "TAX" or source.fact.tax_tag not in {expected, "UNKNOWN"}:
                continue
            relevant.append(pointer)
            as_of = invoice.issued_date if source.date_basis == "INVOICE_ISSUED" else receipt_date
            if (
                source.fact.tax_tag != expected
                or source.fact.amount.value != claim.amount_paise
                or claim.category not in source.categories
                or validity(
                    source,
                    pointer.source_authenticated,
                    pointer.is_current,
                    as_of,
                    datetime.now(UTC),
                )
            ):
                result.reasons = ["TAX_EVIDENCE_CONFLICT_OR_UNVERIFIED"]
                return result
        if not relevant or any(
            p.manifest.fact.type != "TAX" or p.manifest.fact.tax_tag != expected for p in pointers
        ):
            result.reasons = ["TAX_TAG_REQUIRES_REVIEW"]
            return result
    else:
        verified = reader.verify(
            case.id,
            VerifyInput(
                **scope.model_dump(),
                question=PRIMARY[claim.category],
                receipt_id=rule.receipt_id,
                citations=[p.citation for p in pointers],
            ),
        )
        if verified.outcome != "SUPPORTED" or not verified.search_complete:
            result.reasons = ["COMMERCIAL_CLAIM_NOT_VERIFIED", *verified.reasons]
            return result
    result.allowed_paise, result.state = rule.amount_paise, "SUPPORTED"
    result.treatment = rule.treatment
    result.evidence_ids = rule.required_evidence
    result.reasons = ["REVIEWED_SYNTHETIC_POLICY_ONLY"]
    return result


def evaluate(engine, org, case_id, body: ProposalInput, settings):
    with Session(engine) as session:
        begin_readonly(session, org)
        case, receipt, bank, invoices, inputs = base(session, org, case_id, body, settings)
        policy_record, spec = policy(session, org, body.policy_id)
        review = owned(session, FinanceSourceReview, org, body.source_review_id)
        if (
            review.snapshot_sha256 != digest(inputs)
            or review.snapshot != inputs
            or review.receipt_id != receipt.id
            or review.customer_id != case.customer_id
            or review.expires_at <= datetime.now(UTC)
        ):
            raise CaseError("SOURCE_REVIEW_STALE_OR_MISSING")
        receipt_date = bank.occurred_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if not spec.effective_from <= receipt_date <= spec.effective_to:
            raise CaseError("POLICY_OUTSIDE_TRANSACTION_PERIOD")
        reader = EvidenceReader(session, org, settings)
        if len({b.claim_id for b in body.claims}) != len(body.claims):
            raise CaseError("DUPLICATE_CLAIM_TREATMENT", 422)
        results = []
        for binding in body.claims:
            rule = next((r for r in spec.rules if r.id == binding.rule_id), None)
            if rule and rule.receipt_id != receipt.id:
                raise CaseError("RULE_RECEIPT_MISMATCH")
            results.append(treatment(reader, case, bank, body, binding, spec))
        total_noncash = 0
        for invoice in invoices:
            cash = next(a.amount_paise for a in body.cash if a.invoice_id == invoice.id)
            targets = [r for r in results if r.invoice_id == invoice.id]
            if cash + sum(r.allowed_paise for r in targets) > invoice.open_amount_paise:
                for result in targets:
                    result.allowed_paise = 0
                    result.state = (
                        "NEEDS_TAX_REVIEW" if result.category == "tax" else "INSUFFICIENT_EVIDENCE"
                    )
                    result.reasons = ["NONCASH_EXCEEDS_AVAILABLE_AR"]
            total_noncash += sum(r.allowed_paise for r in targets)
        if (
            sum(a.amount_paise for a in body.cash) > spec.max_cash_paise
            or total_noncash > spec.max_noncash_paise
        ):
            raise CaseError("POLICY_AMOUNT_LIMIT")
        if sum(a.amount_paise for a in body.cash) + total_noncash > 2**63 - 1:
            raise CaseError("JOURNAL_TOTAL_OVERFLOW", 422)
        recognized = recognition(session, org, receipt.id)
        if recognized:
            _, original_policy = policy(session, org, recognized.policy_id, active=False)
            if (original_policy.chart.BANK, original_policy.chart.UNAPPLIED) != (
                spec.chart.BANK,
                spec.chart.UNAPPLIED,
            ):
                raise CaseError("RECOGNIZED_RECEIPT_ACCOUNT_CONFLICT")
        journals = compose(
            spec.chart, receipt.amount_paise, body.cash, results, recognized is not None
        )
        snapshot = {
            "algorithm": ALGORITHM,
            "inputs": inputs,
            "body": body.model_dump(mode="json"),
            "policy_sha256": policy_record.content_sha256,
            "evidence_trust_sha256": trust_digest(settings),
            "recognized_journal_id": str(recognized.id) if recognized else None,
            "treatments": [r.model_dump(mode="json") for r in results],
        }
        return snapshot, journals, results


def compare_locked(session, org, row, preflight, settings):
    body = ProposalInput.model_validate(row.snapshot["body"])
    _, _, _, _, inputs = base(session, org, row.case_id, body, settings)
    record, _ = policy(session, org, row.policy_id)
    recognized = recognition(session, org, row.receipt_id)
    if (
        inputs != preflight["inputs"]
        or record.content_sha256 != preflight["policy_sha256"]
        or trust_digest(settings) != preflight["evidence_trust_sha256"]
        or (str(recognized.id) if recognized else None) != preflight["recognized_journal_id"]
        or digest(preflight) != row.snapshot_sha256
    ):
        raise CaseError("STALE_FINANCIAL_PROPOSAL")
