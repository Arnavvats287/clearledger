"""Bounded exact factual predicates. Never authentication by prose or tax policy."""

import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from clearledger.case_domain import CaseError
from clearledger.document_contract import ExtractionError, source_amount, span_text
from clearledger.evidence_contract import (
    Amount,
    Clause,
    Delivery,
    Fact,
    Finding,
    Kind,
    Money,
    Promotion,
    Question,
    RecordInput,
    Ref,
    Tax,
    TrustSource,
    Units,
)
from clearledger.remittance_parser import unique_json


def signing_bytes(org: UUID, body: RecordInput) -> bytes:
    return json.dumps(
        {
            "organization_id": str(org),
            "manifest": body.model_dump(mode="json", exclude={"signature"}),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def trust_sources(raw: str | None) -> list[TrustSource]:
    if raw is None:
        return []
    try:
        if len(raw) > 32768:
            raise ValueError
        value = unique_json(raw)
        if not isinstance(value, list) or len(value) > 32:
            raise ValueError
        parsed = [TrustSource.model_validate(item) for item in value]
        keys = {(p.organization_id, p.source_system, p.key_id) for p in parsed}
        if len(keys) != len(parsed):
            raise ValueError
        return parsed
    except (ValueError, TypeError, RecursionError, ExtractionError):
        raise CaseError("INVALID_EVIDENCE_TRUST_CONFIGURATION", 503) from None


def authenticated(org: UUID, body: RecordInput, sources: list[TrustSource]) -> bool:
    if body.signature is None:
        return False
    for source in sources:
        if (
            source.organization_id == org
            and source.source_system == body.source_system
            and source.key_id == body.key_id
            and body.fact.type in source.allowed_kinds
        ):
            expected = hmac.new(source.secret.encode(), signing_bytes(org, body), hashlib.sha256)
            return hmac.compare_digest(expected.hexdigest(), body.signature)
    return False


def source_spans(body: RecordInput, pages: list[str], customer: str, invoice: str | None) -> None:
    whole = body.excerpt
    span_text(pages, whole)
    fields: list[tuple[str, Money | Units | Ref]] = [("CUSTOMER", body.customer_reference)]
    if body.invoice_reference:
        fields.append(("INVOICE", body.invoice_reference))
    if body.customer_reference.value != customer or (
        body.invoice_reference and body.invoice_reference.value != invoice
    ):
        raise ExtractionError("EVIDENCE_OWNER_REFERENCE_MISMATCH")
    fact = body.fact
    if isinstance(fact, Clause):
        fields.append(("LIMIT", fact.limit))
    elif isinstance(fact, Delivery):
        fields.extend(
            [
                ("SHIPMENT", fact.shipment),
                ("SHIPPED", fact.shipped),
                ("DELIVERED", fact.delivered),
                ("DAMAGED", fact.damaged),
                ("UNIT_VALUE", fact.unit_value),
            ]
        )
    else:
        fields.append(("AMOUNT", fact.amount))
    for label, field in fields:
        s = field.span
        quote = span_text(pages, s)
        if s.page != whole.page or s.start < whole.start or s.end > whole.end:
            raise ExtractionError("EVIDENCE_FIELD_OUTSIDE_RECORD")
        page = pages[s.page - 1]
        prefix = page[max(0, s.start - 60) : s.start]
        if not re.search(r"\b" + label + r"\s*:\s*$", prefix, re.IGNORECASE):
            raise ExtractionError("EVIDENCE_FIELD_LABEL_REQUIRED")
        if s.end < len(page) and (page[s.end].isalnum() or page[s.end] in "_./-"):
            raise ExtractionError("EVIDENCE_FIELD_NOT_DELIMITED")
        if isinstance(field, Money):
            if source_amount(quote) != field.value or not re.search(r"INR|Rs|paise", quote):
                raise ExtractionError("EVIDENCE_MONEY_SOURCE_MISMATCH")
        elif isinstance(field, Units):
            if not re.fullmatch(r"0|[1-9][0-9]{0,9}", quote) or int(quote) != field.value:
                raise ExtractionError("EVIDENCE_QUANTITY_SOURCE_MISMATCH")
        elif quote != field.value:
            raise ExtractionError("EVIDENCE_REFERENCE_SOURCE_MISMATCH")


def validity(
    body: RecordInput, trusted: bool, current: bool, as_of: date, now: datetime
) -> list[str]:
    reasons = []
    if not current:
        reasons.append("SUPERSEDED_RECORD")
    if not trusted:
        reasons.append("SOURCE_NOT_AUTHENTICATED")
    if body.recorded_at > now.astimezone(UTC):
        reasons.append("SOURCE_FROM_FUTURE")
    if not isinstance(as_of, date) or not body.effective_from <= as_of <= body.effective_to:
        reasons.append("OUTSIDE_EFFECTIVE_PERIOD")
    if body.approved_at is None:
        reasons.append("SOURCE_APPROVAL_MISSING")
    if body.fact.type != "WMS" and body.signed_at is None:
        reasons.append("SOURCE_SIGNATURE_STATUS_MISSING")
    if body.fact.type in {"CONTRACT", "PROMOTION"} and any(
        t is not None and t.astimezone(ZoneInfo("Asia/Kolkata")).date() > as_of
        for t in (body.approved_at, body.signed_at)
    ):
        reasons.append("POST_TRANSACTION_SOURCE_STATUS_REQUIRES_REVIEW")
    return reasons


EXPECTED_KIND: dict[Question, set[Kind]] = {
    "CLAUSE_LIMIT": {"CONTRACT"},
    "PROMOTION_AMOUNT": {"PROMOTION"},
    "DELIVERY_SHORTAGE": {"WMS", "POD"},
    "DELIVERY_DAMAGE": {"WMS", "POD"},
    "TAX_DOCUMENT": {"TAX"},
    "INVOICE_AMOUNT": {"INVOICE"},
    "REMITTANCE_AMOUNT": {"REMITTANCE"},
}


def predicate(question: Question, amount: int | None, fact: Fact, identifier: UUID) -> Finding:
    if fact.type not in EXPECTED_KIND[question]:
        return Finding(
            outcome="NOT_APPLICABLE", reasons=["WRONG_EVIDENCE_KIND"], record_ids=[identifier]
        )
    if isinstance(fact, Tax):
        return Finding(
            outcome="INSUFFICIENT",
            reasons=["TAGGED_TAX_RECORD_PRESENT", "NEEDS_TAX_REVIEW"],
            record_ids=[identifier],
        )
    if isinstance(fact, (Clause, Promotion)) and fact.conditions != "NO_ADDITIONAL_CONDITIONS":
        return Finding(
            outcome="INSUFFICIENT",
            reasons=["SOURCE_CONDITIONS_UNASSESSED"],
            record_ids=[identifier],
        )
    if amount is None:
        return Finding(
            outcome="INSUFFICIENT", reasons=["UNKNOWN_CLAIM_AMOUNT"], record_ids=[identifier]
        )
    value = 0
    if isinstance(fact, Clause):
        supports = amount <= fact.limit.value
    else:
        if isinstance(fact, Delivery):
            units = (
                fact.shipped.value - fact.delivered.value
                if question == "DELIVERY_SHORTAGE"
                else fact.damaged.value
            )
            value = units * fact.unit_value.value
            if value > 2**63 - 1:
                return Finding(
                    outcome="INSUFFICIENT",
                    reasons=["PAISE_PRODUCT_OVERFLOW"],
                    record_ids=[identifier],
                )
        elif isinstance(fact, (Promotion, Amount)):
            value = fact.amount.value
        supports = amount == value
    return Finding(
        outcome="SUPPORTED" if supports else "CONTRADICTED",
        reasons=["NUMERIC_PREDICATE_MET" if supports else "NUMERIC_PREDICATE_CONTRADICTED"],
        record_ids=[identifier],
    )


def aggregate(findings: list[Finding], complete: bool) -> tuple[str, list[str]]:
    states = {f.outcome for f in findings}
    if not complete:
        return "INSUFFICIENT", ["SEARCH_INCOMPLETE"]
    if "SUPPORTED" in states and "CONTRADICTED" in states:
        return "INSUFFICIENT", ["CONFLICTING_EVIDENCE"]
    if "INSUFFICIENT" in states:
        return "INSUFFICIENT", ["INCOMPLETE_OR_UNVERIFIED_EVIDENCE"]
    if "CONTRADICTED" in states:
        return "CONTRADICTED", ["SOURCE_FACTS_CONTRADICT_PREDICATE"]
    if "SUPPORTED" in states:
        return "SUPPORTED", ["SOURCE_FACTS_SUPPORT_PREDICATE_ONLY"]
    if states == {"NOT_APPLICABLE"}:
        return "NOT_APPLICABLE", ["NO_APPLICABLE_EVIDENCE"]
    return "INSUFFICIENT", ["MISSING_EVIDENCE"]
