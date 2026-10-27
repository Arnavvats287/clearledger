"""Provider-only ID selections resolved into the unchanged strict remittance contract."""

import re
from dataclasses import replace
from typing import Annotated, Any, Literal

from pydantic import Field

from clearledger.document_contract import REASON_CODE_SOURCE, Category, Extraction, StrictModel
from clearledger.source_candidates import Candidates, discover, select
from clearledger.source_spans import Source, Span, make_span, span_packet, text_source

VERSION = "grounded-remittance-1"


class ClaimSelection(StrictModel):
    category: Category
    description_span_id: str
    amount_paise: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)] | None
    amount_span_id: str | None
    reason_code_span_id: str | None


class RemittanceSelection(StrictModel):
    invoice_candidate_ids: Annotated[list[str], Field(max_length=100)]
    utr_span_ids: Annotated[list[str], Field(max_length=20)]
    payer_span_id: str | None = None
    claims: Annotated[list[ClaimSelection], Field(max_length=100)]
    uncertainty: Literal["none", "review", "unknown"]
    unparsed_span_ids: Annotated[list[str], Field(max_length=100)]


def catalog(
    pages: list[str],
    *,
    source_id: str = "remittance-privacy-projection",
    source_hash: str | None = None,
    version: str = "1",
) -> Candidates:
    source = text_source(source_id, pages, source_hash=source_hash, version=version)
    spans = list(source.spans)
    pattern = (
        r"\b(?:INR|Rs\.?)\s?[0-9]+(?:\.[0-9]{1,2})?\b|\b[0-9]+ paise\b|"
        r"(?<=reason code: )[A-Za-z0-9_./-]+"
    )
    for page in source.pages:
        for match in re.finditer(r"(?im)^(?:payer|customer)\s*[:=]\s*(.+)$", page.text):
            spans.append(make_span(source, page.number, match.start(1), match.end(1), len(spans)))
        for match in REASON_CODE_SOURCE.finditer(page.text):
            spans.append(make_span(source, page.number, match.start(1), match.end(1), len(spans)))
        for match in re.finditer(pattern, page.text, re.I):
            spans.append(make_span(source, page.number, match.start(), match.end(), len(spans)))
        for match in re.finditer(
            r"\b(?:UTR|transaction id|reference)\s*[:#]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9_./-]{0,99})",
            page.text,
            re.I,
        ):
            spans.append(make_span(source, page.number, match.start(1), match.end(1), len(spans)))
    source = replace(source, spans=tuple({s.span_id: s for s in spans}.values()))
    return discover(source, purpose="remittance")


def payload(candidates: Candidates) -> dict[str, Any]:
    return {
        "source_hash": candidates.source.source_hash,
        "source_version": candidates.source.source_version,
        "admission": candidates.admission,
        "search_complete": candidates.complete,
        "invoice_candidates": [c.__dict__ for c in candidates.items],
        "source_spans": [span_packet(s) for s in candidates.source.spans],
    }


def pointer(span: Span) -> dict[str, Any]:
    return {"page": span.page, "start": span.start, "end": span.end, "quote": span.text}


def resolve_selection(value: RemittanceSelection, candidates: Candidates) -> Extraction:
    source: Source = candidates.source

    def resolve(identifier: str) -> Span:
        return source.resolve(
            identifier, expected_hash=source.source_hash, expected_version=source.source_version
        )

    claims = []
    for claim in value.claims:
        reason = resolve(claim.reason_code_span_id) if claim.reason_code_span_id else None
        claims.append(
            {
                "category": claim.category,
                "description": pointer(resolve(claim.description_span_id)),
                "amount_paise": claim.amount_paise,
                "amount_span": pointer(resolve(claim.amount_span_id))
                if claim.amount_span_id
                else None,
                "reason_code": {"value": reason.text, "span": pointer(reason)} if reason else None,
            }
        )
    return Extraction.model_validate(
        {
            "invoice_references": [
                {"value": s.text, "span": pointer(s)}
                for s in select(candidates, value.invoice_candidate_ids)
            ],
            "utr_references": [
                {"value": s.text, "span": pointer(s)} for s in map(resolve, value.utr_span_ids)
            ],
            "payer_hint": (
                {
                    "value": resolve(value.payer_span_id).text,
                    "span": pointer(resolve(value.payer_span_id)),
                }
                if value.payer_span_id
                else None
            ),
            "claims": claims,
            "uncertainty": value.uncertainty if candidates.complete else "review",
            "unparsed_fields": [pointer(resolve(i)) for i in value.unparsed_span_ids],
        }
    )


def provider_schema() -> dict[str, Any]:
    # Provider hints omit complexity-heavy bounds. Host DTO and semantics keep all checks.
    def simplify(node: Any) -> Any:
        if isinstance(node, list):
            return [simplify(v) for v in node]
        if not isinstance(node, dict):
            return node
        return {
            k: simplify(v)
            for k, v in node.items()
            if k not in {"minimum", "maximum", "minLength", "maxLength", "maxItems"}
        }

    result: dict[str, Any] = simplify(RemittanceSelection.model_json_schema())
    return result
