"""Untrusted extraction claims, never accounting decisions or authenticated evidence."""

import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from clearledger.money import paise_from_decimal_string

SCHEMA_VERSION = "remittance-extraction-1.0"
MAX_DOCUMENT_BYTES = 2_097_152
MAX_TEXT = 100_000
MAX_PAGES = 20
Paise = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
Category = Literal[
    "tax", "damage", "short_shipment", "rebate", "early_discount", "other", "unknown"
]
# Prose needs an explicit field label, not a category/status word promoted to a code.
REASON_CODE_SOURCE = re.compile(
    r"(?=\breason[ _-]+code\s*[:#=]\s*([A-Za-z0-9][A-Za-z0-9_./-]{0,99})\b)",
    re.IGNORECASE,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    @field_validator("*")
    @classmethod
    def safe_unicode(cls, value: Any, info: ValidationInfo) -> Any:
        def check(item: Any) -> None:
            if isinstance(item, str):
                try:
                    item.encode("utf-8", errors="strict")
                except UnicodeError:
                    raise ValueError("Invalid Unicode scalar") from None
                allowed = "\n\t" if info.field_name == "quote" else ""
                if any(ord(char) < 32 and char not in allowed for char in item):
                    raise ValueError("Unsupported control character")
            elif isinstance(item, list):
                for child in item:
                    check(child)

        check(value)
        return value


class Span(StrictModel):
    page: Annotated[int, Field(ge=1, le=MAX_PAGES)]
    start: Annotated[int, Field(ge=0, le=MAX_TEXT)]
    end: Annotated[int, Field(ge=1, le=MAX_TEXT)]
    quote: Annotated[str, Field(min_length=1, max_length=2000)]


class Reference(StrictModel):
    value: Annotated[str, Field(min_length=1, max_length=200)]
    span: Span


class ExtractedClaim(StrictModel):
    category: Category
    description: Span
    amount_paise: Paise | None
    amount_span: Span | None
    reason_code: Reference | None


class Extraction(StrictModel):
    invoice_references: Annotated[list[Reference], Field(max_length=100)]
    utr_references: Annotated[list[Reference], Field(max_length=20)]
    payer_hint: Reference | None
    claims: Annotated[list[ExtractedClaim], Field(max_length=100)]
    uncertainty: Literal["none", "review", "unknown"]
    unparsed_fields: Annotated[list[Span], Field(max_length=100)]


class StructuredClaim(StrictModel):
    category: Category
    amount_paise: Paise | None
    reason_code: Annotated[str, Field(min_length=1, max_length=100)] | None


class StructuredRemittance(StrictModel):
    remittance_version: Literal["1.0"]
    invoice_references: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=100)
    ]
    utr_references: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=20)
    ]
    payer_hint: Annotated[str, Field(min_length=1, max_length=200)] | None
    claims: Annotated[list[StructuredClaim], Field(max_length=100)]


class ExtractionError(Exception):
    """Only fixed non-sensitive codes may cross the extraction boundary."""


def span_text(pages: list[str], span: Span) -> str:
    if not 1 <= span.page <= len(pages):
        raise ExtractionError("INVALID_SPAN")
    page = pages[span.page - 1]
    if not 0 <= span.start < span.end <= len(page) or page[span.start : span.end] != span.quote:
        raise ExtractionError("INVALID_SPAN")
    return span.quote


def literal(quote: str) -> str:
    if quote.startswith('"'):
        try:
            value = json.loads(quote)
            if isinstance(value, str):
                return value
        except ValueError:
            pass
    return quote


def source_amount(quote: str) -> int:
    # JSON numbers come only from the deterministic structured parser, never free prose.
    if re.fullmatch(r"0|[1-9][0-9]{0,18}", quote):
        value = int(quote)
    elif match := re.fullmatch(r"([0-9]+) paise", quote):
        value = int(match[1])
    elif match := re.fullmatch(r"(?:INR|Rs\.?)[ ]?([0-9]+(?:\.[0-9]{1,2})?)", quote):
        value = paise_from_decimal_string(match[1])
    else:
        raise ExtractionError("UNSUPPORTED_AMOUNT_SOURCE")
    if not 0 <= value <= 2**63 - 1:
        raise ExtractionError("AMOUNT_RANGE")
    return value


CATEGORY_CUES: dict[str, str] = {
    "tax": r"\b(?:tax|withholding)\b",
    "damage": r"\bdamag(?:e|ed)\b",
    "short_shipment": r"\b(?:short_shipment|short shipment)\b",
    "rebate": r"\brebate\b",
    "early_discount": r"\b(?:early_discount|early discount)\b",
    "other": r"\bother\b",
    "unknown": r"",
}


def validate_semantics(result: Extraction, pages: list[str], *, structured: bool = False) -> None:
    references = [(ref, "invoice") for ref in result.invoice_references]
    references += [(ref, "utr") for ref in result.utr_references]
    if result.payer_hint:
        references.append((result.payer_hint, "payer"))
    for ref, kind in references:
        if literal(span_text(pages, ref.span)) != ref.value:
            raise ExtractionError("UNSUPPORTED_REFERENCE")
        if kind in {"invoice", "utr"}:
            page = pages[ref.span.page - 1]
            if not structured:
                label = (
                    r"(?:invoice(?:\s+(?:no\.?|number))?|inv)"
                    if kind == "invoice"
                    else r"(?:utr|transaction(?: id)?|reference)"
                )
                prefix = page[max(0, ref.span.start - 60) : ref.span.start]
                if not re.search(r"\b" + label + r"\s*[:#]?\s*$", prefix, re.IGNORECASE):
                    raise ExtractionError("REFERENCE_LABEL_REQUIRED")
            # Prevent a prefix of another invoice/transaction identifier becoming evidence.
            for position in (ref.span.start - 1, ref.span.end):
                if 0 <= position < len(page) and (
                    page[position].isalnum() or page[position] in "-_./"
                ):
                    raise ExtractionError("REFERENCE_NOT_DELIMITED")
    for claim in result.claims:
        description = span_text(pages, claim.description)
        if not re.search(CATEGORY_CUES[claim.category], description, re.IGNORECASE):
            raise ExtractionError("UNSUPPORTED_CATEGORY")
        if (claim.amount_paise is None) != (claim.amount_span is None):
            raise ExtractionError("MISSING_AMOUNT_EVIDENCE")
        if claim.amount_span is not None:
            quote = span_text(pages, claim.amount_span)
            page = pages[claim.amount_span.page - 1]
            before = page[: claim.amount_span.start]
            after = page[claim.amount_span.end :]
            if (
                before
                and (
                    before[-1].isalnum()
                    or before[-1] == "_"
                    or before.rstrip().endswith(("+", "-"))
                )
            ) or (
                after
                and (
                    after[0].isalnum()
                    or after[0] == "_"
                    or (after[0] in ".," and len(after) > 1 and after[1].isdigit())
                )
            ):
                raise ExtractionError("AMOUNT_NOT_DELIMITED")
            if not structured and re.fullmatch(r"[0-9]+", quote):
                raise ExtractionError("AMOUNT_UNIT_REQUIRED")
            if source_amount(quote) != claim.amount_paise:
                raise ExtractionError("AMOUNT_SOURCE_MISMATCH")
            if (
                claim.description.page != claim.amount_span.page
                or claim.amount_span.start < claim.description.start
                or claim.amount_span.end > claim.description.end
            ):
                raise ExtractionError("AMOUNT_OUTSIDE_CLAIM")
        if claim.reason_code:
            if literal(span_text(pages, claim.reason_code.span)) != claim.reason_code.value:
                raise ExtractionError("UNSUPPORTED_REASON")
            if (
                claim.reason_code.span.page != claim.description.page
                or claim.reason_code.span.start < claim.description.start
                or claim.reason_code.span.end > claim.description.end
            ):
                raise ExtractionError("REASON_OUTSIDE_CLAIM")
            if not structured and not any(
                match.span(1) == (claim.reason_code.span.start, claim.reason_code.span.end)
                for match in REASON_CODE_SOURCE.finditer(pages[claim.reason_code.span.page - 1])
            ):
                raise ExtractionError("REASON_CODE_LABEL_REQUIRED")
    for unparsed in result.unparsed_fields:
        span_text(pages, unparsed)


def empty_extraction() -> Extraction:
    return Extraction(
        invoice_references=[],
        utr_references=[],
        payer_hint=None,
        claims=[],
        uncertainty="unknown",
        unparsed_fields=[],
    )
