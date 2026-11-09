"""Versioned occurrence candidates over the shared source. No gold or financial policy."""

import re
from dataclasses import replace
from itertools import islice
from typing import TypedDict

from clearledger.source_candidates import Candidate, Candidates, discover
from clearledger.source_spans import Source, digest, make_span

LABEL = re.compile(r"\b(?:invoice|inv\.?|document|bill)\s*(?:no\.?|number|num|id|#|:)", re.I)
FRAGMENT = re.compile(r"[A-Za-z0-9]+(?:\s*[-/.\\]\s*[A-Za-z0-9]+)+")


def invoice_admission(source: Source) -> str:
    head = source.pages[0].text[:1800] if source.pages else ""
    invoice = re.search(r"(?im)^\s*(?:tax\s+|sales\s+)?invoice\s*(?:copy|original)?\s*$", head)
    other = re.search(
        r"(?im)^\s*(?:purchase order|bank statement|delivery note|"
        r"quotation|packing list|receipt)\s*$",
        head,
    )
    if other and not invoice:
        return "OUT_OF_SCOPE"
    if invoice and not other:
        return "INVOICE"
    # Mixed or incidental references need typed classification, not keyword authority.
    return "UNKNOWN"


def candidates(source: Source, *, internal_limit: int = 1024) -> Candidates:
    if not 64 <= internal_limit <= 2048:
        raise ValueError("INVOICE_CANDIDATE_BOUND")
    decision = invoice_admission(source)
    if decision == "OUT_OF_SCOPE":
        return Candidates(source, (), decision, True)
    base = replace(discover(source, purpose="remittance", limit=2048), admission=decision)
    locations = {s.span_id: s for s in base.source.spans}
    found: dict[tuple[str, str], Candidate] = {(c.span_id, c.value): c for c in base.items}
    exhausted = False
    for page in source.pages:
        # Recall candidates include header numeric IDs even when OCR detached the label.
        # These are candidates only, never verified invoice identifiers.
        for index, token in enumerate(page.tokens):
            if len(found) >= 10000:
                exhausted = True
                break
            if token.bbox is not None and token.bbox[1] > 0.65:
                continue
            raw = page.text[token.start : token.end]
            if not re.fullmatch(r"\d{3,24}", raw):
                continue
            s = make_span(
                source,
                page.number,
                token.start + page.offset,
                token.end + page.offset,
                len(locations),
            )
            locations[s.span_id] = s
            found[s.span_id, raw] = Candidate(
                "vc_" + digest([s.span_id, raw])[:32], s.span_id, raw, "HEADER_NUMERIC"
            )
            if index + 1 < len(page.tokens) and token.bbox:
                nxt = page.tokens[index + 1]
                right = page.text[nxt.start : nxt.end]
                if (
                    nxt.bbox
                    and re.fullmatch(r"\d{1,15}", right)
                    and 0 <= nxt.bbox[0] - token.bbox[2] <= 0.008
                    and min(nxt.bbox[3], token.bbox[3]) > max(nxt.bbox[1], token.bbox[1])
                ):
                    joined = raw + right
                    if len(joined) <= 24:
                        s = make_span(
                            source,
                            page.number,
                            token.start + page.offset,
                            nxt.end + page.offset,
                            len(locations),
                        )
                        locations[s.span_id] = s
                        found[s.span_id, joined] = Candidate(
                            "vc_" + digest([s.span_id, joined])[:32],
                            s.span_id,
                            joined,
                            "ADJACENT_DIGIT_TOKENS",
                        )
        labels = list(islice(LABEL.finditer(page.text), 201))
        if len(labels) > 200:
            exhausted = True
        for match in labels[:200]:
            if len(found) >= 10000:
                exhausted = True
                break
            # Same/next line exact values and punctuation-separated OCR identifiers.
            left = match.end()
            tail = page.text[left : left + 140]
            # Stop before the following label or column value. Join only visible punctuation.
            fragment = re.match(r"[\s:=#]*", tail)
            if fragment:
                identifier = FRAGMENT.match(tail, fragment.end())
                if identifier and any(c.isdigit() for c in identifier.group()):
                    span = make_span(
                        source,
                        page.number,
                        page.offset + left + identifier.start(),
                        page.offset + left + identifier.end(),
                        len(locations),
                    )
                    joined = re.sub(r"\s*([-/.\\])\s*", r"\1", span.text)
                    locations[span.span_id] = span
                    found[span.span_id, joined] = Candidate(
                        "vc_" + digest([span.span_id, joined])[:32],
                        span.span_id,
                        joined,
                        "PUNCTUATION_JOIN",
                    )
            value = re.search(r"[A-Za-z0-9][A-Za-z0-9_./ -]{0,65}", tail)
            if value and any(c.isdigit() for c in value.group()):
                start, end = left + value.start(), left + value.end()
                raw = page.text[start:end].rstrip()
                end = start + len(raw)
                if raw:
                    s = make_span(
                        source, page.number, start + page.offset, end + page.offset, len(locations)
                    )
                    locations[s.span_id] = s
                    found[s.span_id, raw] = Candidate(
                        "vc_" + digest([s.span_id, raw])[:32], s.span_id, raw, "LABEL_VALUE"
                    )
                    joined = re.sub(r"\s*([-/.])\s*", r"\1", raw)
                    if joined != raw:
                        found[s.span_id, joined] = Candidate(
                            "vc_" + digest([s.span_id, joined])[:32],
                            s.span_id,
                            joined,
                            "PUNCTUATION_JOIN",
                        )
            label_tokens = [
                t for t in page.tokens if t.start < match.end() and t.end > match.start()
            ]
            boxes = [t.bbox for t in label_tokens if t.bbox is not None]
            if not boxes:
                continue
            x = max(b[2] for b in boxes)
            top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
            for index, token in enumerate(page.tokens):
                box = token.bbox
                if box is None or box[0] < x - 0.01 or min(box[3], bottom) <= max(box[1], top):
                    continue
                if box[0] - x > 0.3:
                    continue
                for width in range(1, 5):
                    group = page.tokens[index : index + width]
                    if len(group) != width or any(t.bbox is None for t in group):
                        continue
                    if any(min(t.bbox[3], bottom) <= max(t.bbox[1], top) for t in group if t.bbox):
                        continue
                    raw = page.text[group[0].start : group[-1].end]
                    if len(raw) > 80 or not any(c.isdigit() for c in raw):
                        continue
                    s = make_span(
                        source,
                        page.number,
                        group[0].start + page.offset,
                        group[-1].end + page.offset,
                        len(locations),
                    )
                    locations[s.span_id] = s
                    found[s.span_id, raw] = Candidate(
                        "vc_" + digest([s.span_id, raw])[:32], s.span_id, raw, "RIGHT_OF_LABEL"
                    )
                    joined = re.sub(r"\s*([-/.])\s*", r"\1", raw)
                    if joined != raw:
                        found[s.span_id, joined] = Candidate(
                            "vc_" + digest([s.span_id, joined])[:32],
                            s.span_id,
                            joined,
                            "PUNCTUATION_JOIN",
                        )
    extended = replace(source, spans=tuple(locations.values()))

    def score(c: Candidate) -> tuple[float, int, int, int, str]:
        s = locations[c.span_id]
        page = next(p for p in source.pages if p.number == s.page)
        local = page.text[max(0, s.start - page.offset - 65) : s.start - page.offset]
        proximity = bool(
            re.search(
                r"(?:invoice|inv\.?|document|bill)\s*(?:no\.?|number|#|:)?[^\n]{0,28}$", local, re.I
            )
        )
        strength = (8.0 if proximity else 0.0) + (
            4 if c.reason in {"LABEL_VALUE", "RIGHT_OF_LABEL", "PUNCTUATION_JOIN"} else 0
        )
        strength += 2 if s.bbox and s.bbox[1] < 0.5 else 0
        strength -= 4 if re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", c.value.strip()) else 0
        strength -= max(0, len(c.value) - 35) / 20
        return -strength, s.page, s.start, s.end, c.value

    ordered = sorted(found.values(), key=score)
    return Candidates(
        extended,
        tuple(ordered[:internal_limit]),
        base.admission,
        base.complete and not exhausted and len(ordered) <= internal_limit,
    )


class CompactPacket(TypedDict):
    admission: str
    head: str
    columns: list[str]
    candidates: list[list[object]]
    complete: bool


def compact(c: Candidates, *, limit: int = 64) -> tuple[CompactPacket, dict[str, Candidate]]:
    if not 1 <= limit <= 128:
        raise ValueError("INVOICE_PROVIDER_BOUND")
    selected = c.items[:limit]
    lookup = {f"C{i:02}": item for i, item in enumerate(selected, 1)}
    rows: list[list[object]] = []
    for alias, item in lookup.items():
        s = c.source.resolve(
            item.span_id,
            expected_hash=c.source.source_hash,
            expected_version=c.source.source_version,
        )
        page = next(p for p in c.source.pages if p.number == s.page)
        a, b = s.start - page.offset, s.end - page.offset
        rows.append(
            [
                alias,
                item.value,
                s.page,
                [round(v, 4) for v in s.bbox] if s.bbox else None,
                page.text[max(0, a - 45) : min(len(page.text), b + 45)],
            ]
        )
    return {
        "admission": c.admission,
        "head": c.source.pages[0].text[:600] if c.source.pages else "",
        "columns": ["alias", "value", "page", "box_hint", "context"],
        "candidates": rows,
        "complete": c.complete and len(c.items) <= limit,
    }, lookup


def fallback_candidates(primary: Candidates, text: Source) -> Candidates:
    """Offer source-backed values that are unavailable in OCR; never create geometry."""
    if text.source_kind != "PDF_TEXT" or any(page.tokens for page in text.pages):
        raise ValueError("PDF_TEXT_FALLBACK_SOURCE_REQUIRED")
    if primary.admission == "OUT_OF_SCOPE":
        return Candidates(text, (), primary.admission, True)
    existing = {item.value for item in primary.items}
    discovered = candidates(text)
    novel = tuple(item for item in discovered.items if item.value not in existing)
    return replace(discovered, items=novel)
