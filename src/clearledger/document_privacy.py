"""Fail-closed allowlisted projection. Reversible offsets stay only in private memory."""

import re
from dataclasses import dataclass

from clearledger.document_contract import Extraction, ExtractionError, literal, span_text

PRIVACY_VERSION = "projection-v1"
SENSITIVE: dict[str, str] = {
    "GSTIN": r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "EMAIL": r"(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}(?![\w.-])",
    "PHONE": r"(?<!\w)(?:\+91[- ]?)?[6-9][0-9 -]{8,13}[0-9](?!\w)",
    "BANK": (
        r"\b(?:a/c|account|acct|iban|bank account)(?:\s*(?:no\.?|number))?"
        r"\s*[:#=-]?\s*[A-Z0-9 -]{6,34}"
    ),
    "IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "CONTACT": r"(?im)^(?:name|contact|address|phone|mobile|email|pan|gstin|ifsc)\s*[:=].*$",
    "URL": r"https?://\S+",
}
VOCABULARY = set(
    "invoice invoices inv utr reference references receipt payment paid pay against for the a an "
    "and or of to from customer payer remittance cash total amount paise inr rs claim claims "
    "deduction deductions tax withholding damage damaged short shipment rebate early discount "
    "reason code unknown other disputed dispute due balance outstanding remaining less with "
    "is was has this that received on dated missing unavailable unclear not no requested "
    "reported asserted partial full under over".split()
)
REFERENCE = re.compile(
    r"(?=\b(?:invoice(?:\s+(?:no\.?|number))?|inv|utr|transaction(?: id)?|reference)"
    r"(?:\s*[:#]\s*|\s+)([A-Za-z0-9][A-Za-z0-9_./-]{0,99})\b)",
    re.IGNORECASE,
)
AMOUNT = re.compile(r"\b(?:INR|Rs\.?)\s?[0-9]+(?:\.[0-9]{1,2})?\b|\b[0-9]+ paise\b")


@dataclass(frozen=True)
class PrivateMask:
    page: int
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class Projected:
    pages: list[str]
    masks: tuple[PrivateMask, ...]


def project(pages: list[str]) -> Projected:
    output: list[str] = []
    masks: list[PrivateMask] = []
    for number, page in enumerate(pages, 1):
        if "█" in page:
            raise ExtractionError("PRIVACY_RESERVED_CHARACTER")
        preserve = [(m.start(1), m.end(1)) for m in REFERENCE.finditer(page)]
        amounts = list(AMOUNT.finditer(page))
        for amount in amounts:
            suffix = page[amount.end() :]
            if len(suffix) > 1 and suffix[0] in ".," and suffix[1].isdigit():
                raise ExtractionError("PRIVACY_UNSUPPORTED_MONEY_FORMAT")
        preserve += [(m.start(), m.end()) for m in amounts]
        sensitive = [
            (m.start(), m.end(), kind)
            for kind, pattern in SENSITIVE.items()
            for m in re.finditer(pattern, page, re.IGNORECASE)
        ]
        for start, end, _ in sensitive:
            if any(start < right and end > left for left, right in preserve):
                raise ExtractionError("PRIVACY_ESSENTIAL_IDENTIFIER_CONFLICT")
        visible = [False] * len(page)
        for start, end in preserve:
            visible[start:end] = [True] * (end - start)
        for word in re.finditer(r"[A-Za-z]+", page):
            if word[0].casefold() in VOCABULARY:
                visible[word.start() : word.end()] = [True] * len(word[0])
        for index, character in enumerate(page):
            if character.isspace() or character in ".,:;-/()?!":
                visible[index] = True
        for start, end, kind in sensitive:
            visible[start:end] = [False] * (end - start)
            masks.append(PrivateMask(number, start, end, kind))
        # All unknown words/numbers/symbols are masked too, not just regex-detected PII.
        for match in re.finditer(r"\S+", page):
            if any(not visible[i] for i in range(match.start(), match.end())):
                masks.append(PrivateMask(number, match.start(), match.end(), "UNNECESSARY_CONTENT"))
        projected = "".join(char if visible[i] else "█" for i, char in enumerate(page))
        output.append(projected)
    return Projected(output, tuple(masks))


def restore(result: Extraction, visible: list[str], original: list[str]) -> Extraction:
    # Validate model spans against exactly what the provider saw, then resolve original offsets.
    result = result.model_copy(deep=True)
    refs = [
        *result.invoice_references,
        *result.utr_references,
        *([result.payer_hint] if result.payer_hint else []),
    ]
    spans = [ref.span for ref in refs] + result.unparsed_fields
    for claim in result.claims:
        spans.append(claim.description)
        if claim.amount_span:
            spans.append(claim.amount_span)
        if claim.reason_code:
            refs.append(claim.reason_code)
            spans.append(claim.reason_code.span)
    for ref in refs:
        if ref.value != literal(span_text(visible, ref.span)):
            raise ExtractionError("UNSUPPORTED_MODEL_VALUE")
    # A shared Span can occur twice. Verify once before rewriting its quote.
    seen: set[int] = set()
    for span in spans:
        if id(span) in seen:
            continue
        seen.add(id(span))
        span_text(visible, span)
        span.quote = original[span.page - 1][span.start : span.end]
    for ref in refs:
        ref.value = literal(ref.span.quote)
    return result
