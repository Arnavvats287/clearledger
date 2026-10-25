"""Small fully specified offline formats. Anything else needs review/semantic extraction."""

import json
import re
from typing import Any

from clearledger.document_contract import (
    ExtractedClaim,
    Extraction,
    ExtractionError,
    Reference,
    Span,
    StructuredRemittance,
    empty_extraction,
    source_amount,
    validate_semantics,
)


def json_positions(text: str) -> dict[str, tuple[int, int]]:
    positions: dict[str, tuple[int, int]] = {}
    decoder = json.JSONDecoder()

    def skip(pos: int) -> int:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        return pos

    def walk(pos: int, path: str, depth: int) -> int:
        if depth > 12:
            raise ExtractionError("JSON_DEPTH_LIMIT")
        pos = skip(pos)
        start = pos
        if text[pos] in "[{":
            array = text[pos] == "["
            close = "]" if array else "}"
            pos = skip(pos + 1)
            index = 0
            while text[pos] != close:
                key: Any = index
                if not array:
                    key, pos = decoder.raw_decode(text, pos)
                    pos = skip(pos)
                    if text[pos] != ":":
                        raise ExtractionError("INVALID_JSON")
                    pos += 1
                pos = skip(
                    walk(
                        pos, path + "/" + str(key).replace("~", "~0").replace("/", "~1"), depth + 1
                    )
                )
                index += 1
                if text[pos] != ",":
                    break
                pos = skip(pos + 1)
            if text[pos] != close:
                raise ExtractionError("INVALID_JSON")
            pos += 1
        else:
            _, pos = decoder.raw_decode(text, pos)
        positions[path] = (start, pos)
        return pos

    if skip(walk(0, "", 0)) != len(text):
        raise ExtractionError("INVALID_JSON")
    return positions


def unique_json(text: str) -> Any:
    def nonfinite(_: str) -> Any:
        raise ExtractionError("NONFINITE_JSON")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ExtractionError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def structured(text: str) -> Extraction:
    positions = json_positions(text)
    body = StructuredRemittance.model_validate(unique_json(text))

    def span(path: str) -> Span:
        start, end = positions[path]
        return Span(page=1, start=start, end=end, quote=text[start:end])

    result = empty_extraction()
    for field in ("invoice_references", "utr_references"):
        values: list[str] = getattr(body, field)
        setattr(
            result,
            field,
            [Reference(value=value, span=span(f"/{field}/{i}")) for i, value in enumerate(values)],
        )
    if body.payer_hint is not None:
        result.payer_hint = Reference(value=body.payer_hint, span=span("/payer_hint"))
    for i, claim in enumerate(body.claims):
        path = f"/claims/{i}"
        result.claims.append(
            ExtractedClaim(
                category=claim.category,
                description=span(path),
                amount_paise=claim.amount_paise,
                amount_span=span(path + "/amount_paise")
                if claim.amount_paise is not None
                else None,
                reason_code=Reference(value=claim.reason_code, span=span(path + "/reason_code"))
                if claim.reason_code is not None
                else None,
            )
        )
    result.uncertainty = "review" if any(c.amount_paise is None for c in body.claims) else "none"
    validate_semantics(result, [text], structured=True)
    return result


def deterministic(pages: list[str], mime: str) -> Extraction | None:
    if mime == "application/json":
        return structured(pages[0])
    result = empty_extraction()
    found = False
    for page_number, page in enumerate(pages, 1):
        offset = 0
        for line in page.splitlines(keepends=True):
            value = line.rstrip("\n")
            if not value.strip():
                offset += len(line)
                continue
            reference = re.fullmatch(r"(INVOICE|UTR|PAYER): ([^\n]{1,200})", value)
            claim = re.fullmatch(
                r"CLAIM (tax|damage|short_shipment|rebate|early_discount|other|unknown): "
                r"((?:INR|Rs\.?)[ ]?[0-9]+(?:\.[0-9]{1,2})?|[0-9]+ paise)",
                value,
            )
            if reference:
                start, end = reference.span(2)
                ref = Reference(
                    value=reference[2],
                    span=Span(
                        page=page_number,
                        start=offset + start,
                        end=offset + end,
                        quote=reference[2],
                    ),
                )
                if reference[1] == "PAYER":
                    if result.payer_hint is not None:
                        return None
                    result.payer_hint = ref
                else:
                    target = (
                        result.invoice_references
                        if reference[1] == "INVOICE"
                        else result.utr_references
                    )
                    target.append(ref)
            elif claim:
                start, end = claim.span(2)
                result.claims.append(
                    ExtractedClaim.model_validate(
                        {
                            "category": claim[1],
                            "description": {
                                "page": page_number,
                                "start": offset,
                                "end": offset + len(value),
                                "quote": value,
                            },
                            "amount_paise": source_amount(claim[2]),
                            "amount_span": {
                                "page": page_number,
                                "start": offset + start,
                                "end": offset + end,
                                "quote": claim[2],
                            },
                            "reason_code": None,
                        }
                    )
                )
            else:
                return None
            offset += len(line)
            found = True
    if not found:
        return None
    result.uncertainty = "none"
    # Revalidate list/count limits after building the offline result.
    result = Extraction.model_validate(result.model_dump())
    validate_semantics(result, pages)
    return result
