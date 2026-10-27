"""Candidate-first identifiers and source-only document admission, never payment intent."""

import re
from bisect import bisect_right
from dataclasses import dataclass, replace
from typing import Literal

from clearledger.source_spans import Source, Span, digest, make_span


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    span_id: str
    value: str
    reason: str


@dataclass(frozen=True)
class Candidates:
    source: Source
    items: tuple[Candidate, ...]
    admission: str
    complete: bool


LABEL = re.compile(
    r"\b(?:tax\s+invoice|invoice|inv\.?|document|bill)"
    r"(?:\s*(?:no\.?|number|num|id|#))?\s*[:#=.-]?\s*",
    re.I,
)
VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,99}")


def admission(source: Source, purpose: Literal["invoice", "remittance"] = "invoice") -> str:
    head = "\n".join(p.text[:1800] for p in source.pages[:1])
    if purpose == "remittance" and re.search(
        r"\b(?:remittance|payment|paid|deduction|invoice)\b", head, re.I
    ):
        return "REMITTANCE_REFERENCES"
    negative = re.search(
        r"\b(?:purchase\s+order|delivery\s+note|credit\s+note|bank\s+statement|"
        r"quotation|receipt|packing\s+list)\b",
        head,
        re.I,
    )
    positive = re.search(
        r"\b(?:tax\s+invoice|sales\s+invoice|invoice\s*(?:no\.?|number|#|:)|"
        r"bill\s+of\s+supply)\b|^\s*invoice\s*$",
        head,
        re.I | re.M,
    )
    if negative and (not positive or negative.start() < positive.start()):
        return "OUT_OF_SCOPE"
    return "INVOICE" if positive else "UNKNOWN"


def discover(
    source: Source, *, purpose: Literal["invoice", "remittance"] = "invoice", limit: int = 160
) -> Candidates:
    decision = admission(source, purpose)
    if decision == "OUT_OF_SCOPE":
        return Candidates(source, (), decision, True)
    additions: dict[tuple[int, int, int], Span] = {}
    reasons: dict[tuple[int, int, int], str] = {}
    exhausted = False
    for page in source.pages:
        ranges: list[tuple[int, int, str]] = []
        lines = list(re.finditer(r"[^\n]+", page.text))
        starts = [line.start() for line in lines]
        for match in LABEL.finditer(page.text):
            if len(ranges) >= 5000:
                exhausted = True
                break
            # Same/adjacent reading-order lines only; no arbitrary distant numeric IDs.
            tail = page.text[match.end() : match.end() + 120]
            nearby = VALUE.match(tail)
            if nearby and any(c.isdigit() for c in nearby.group()):
                ranges.append((match.end(), match.end() + nearby.end(), "LABEL_PROXIMITY"))
            full = tail.split("\n", 1)[0].rstrip()
            if (
                full
                and re.fullmatch(r"[A-Za-z0-9_./ -]{1,100}", full)
                and any(c.isdigit() for c in full)
            ):
                ranges.append(
                    (match.end(), match.end() + len(full), "EXACT_LABELED_TOKEN_SEQUENCE")
                )
            i = bisect_right(starts, match.start()) - 1
            for neighbor in lines[max(0, i - 1) : i + 3]:
                left = (
                    max(neighbor.start(), match.start() - 100)
                    if neighbor.start() <= match.start() < neighbor.end()
                    else neighbor.start()
                )
                right = min(neighbor.end(), left + 256)
                for number in VALUE.finditer(page.text, left, right):
                    if len(number.group()) >= 3 and any(c.isdigit() for c in number.group()):
                        ranges.append(
                            (
                                number.start(),
                                number.end(),
                                "ADJACENT_READING_ORDER",
                            )
                        )
        for match in VALUE.finditer(page.text):
            if len(ranges) >= 5000:
                exhausted = True
                break
            value = match.group()
            if (
                any(c.isalpha() for c in value)
                and any(c.isdigit() for c in value)
                and (any(c in value for c in "-/_") or value.upper().startswith(("INV", "BILL")))
            ):
                ranges.append((match.start(), match.end(), "IDENTIFIER_PATTERN"))
        for start, end, reason in ranges:
            key = page.number, start + page.offset, end + page.offset
            additions[key] = make_span(source, *key, len(source.spans) + len(additions))
            reasons[key] = reason
    ordered = sorted(additions)
    complete = not exhausted and len(ordered) <= limit
    selected = ordered[:limit]
    spans = tuple(additions[k] for k in selected)
    catalog = {s.span_id: s for s in (*source.spans, *spans)}
    extended = replace(source, spans=tuple(catalog.values()))
    return Candidates(
        extended,
        tuple(
            Candidate("ca_" + digest(s.span_id)[:32], s.span_id, s.text, reasons[k])
            for k, s in zip(selected, spans, strict=True)
        ),
        decision,
        complete,
    )


def select(candidates: Candidates, identifiers: list[str]) -> list[Span]:
    from clearledger.source_spans import GroundingError

    if len(identifiers) != len(set(identifiers)):
        raise GroundingError("DUPLICATE_CANDIDATE")
    index = {c.candidate_id: c for c in candidates.items}
    if not set(identifiers) <= index.keys():
        raise GroundingError("UNKNOWN_CANDIDATE")
    return [
        candidates.source.resolve(
            index[i].span_id,
            expected_hash=candidates.source.source_hash,
            expected_version=candidates.source.source_version,
        )
        for i in identifiers
    ]
