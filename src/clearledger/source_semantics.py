"""Source-only semantic segmentation and bounded legal retrieval, never legal authority."""

import math
import re
from collections import Counter
from dataclasses import dataclass, replace

from clearledger.source_retrieval import exact_atoms, ngrams, terms, words
from clearledger.source_spans import GroundingError, Source, Span, make_span

GROUPS = (
    "retain retention keep copy copies archive archival backup backups",
    "destroy destruction return delete deletion erase disposal",
    "terminate termination expiry expiration survive survival continuing thereafter",
    "disclose disclosure share provide divulge communicate reveal",
    "employee employees representative representatives agents advisor advisers personnel",
    "law legal court judicial government regulatory subpoena compelled required",
    "prohibit prohibited unauthorized forbidden permission permitted allow allowed",
    "confidential secret proprietary information material materials data",
    "purpose use uses evaluation transaction business discussion negotiations",
    "exception exceptions exclude excluded excluding public publicly known available",
    "notice notify notification written consent approval authorize authorization",
    "independent independently development develop developed research",
    "oral orally verbal tangible marked marking identified identified writing",
)


@dataclass(frozen=True)
class SemanticSource:
    source: Source
    sections: tuple[tuple[str, str], ...]


def semantic_source(source: Source, *, max_chars: int = 900) -> SemanticSource:
    if not 160 <= max_chars <= 1600:
        raise GroundingError("SEMANTIC_LIMIT")
    source = replace(source, source_kind="SEMANTIC_CLAUSES_2")
    spans: list[Span] = []
    sections: list[tuple[str, str]] = []
    for page in source.pages:
        heading = ""
        for line in re.finditer(r"[^\n]+", page.text):
            text = line.group()
            clean = text.strip()
            if (
                len(clean) <= 110
                and (clean.isupper() or re.match(r"^\d+(?:\.\d+)*[.)]?\s+[A-Z]", clean))
                and not clean.endswith((";", "."))
            ):
                heading = clean
            # Source-only sentence/list/clause boundaries, never annotation span indices.
            boundaries = [
                0,
                *[
                    m.end()
                    for m in re.finditer(
                        r"(?<=[.;!?])\s+(?=[A-Z(\d])|(?<=:)\s+(?=\([a-z0-9]+\))", text
                    )
                ],
                len(text),
            ]
            for left, right in zip(boundaries, boundaries[1:], strict=False):
                while left < right:
                    end = min(right, left + max_chars)
                    if end < right:
                        space = text.rfind(" ", left + max_chars // 2, end)
                        if space >= left:
                            end = space
                    start = left
                    while start < end and text[start].isspace():
                        start += 1
                    trimmed = end
                    while trimmed > start and text[trimmed - 1].isspace():
                        trimmed -= 1
                    if start < trimmed:
                        span = make_span(
                            source,
                            page.number,
                            page.offset + line.start() + start,
                            page.offset + line.start() + trimmed,
                            len(spans),
                        )
                        spans.append(span)
                        sections.append((span.span_id, heading))
                    left = end if end > left else left + 1
    if len(spans) > 10000:
        raise GroundingError("SEMANTIC_SPAN_LIMIT")
    # Preserve separators too: all semantic spans together must cover source characters,
    # including whitespace inside an annotated clause. No metric normalization changes.
    complete: list[Span] = []
    section_map = dict(sections)
    complete_sections = []
    for page in source.pages:
        on_page = [s for s in spans if s.page == page.number]
        for i, span in enumerate(on_page):
            start = span.start if i else page.offset
            end = on_page[i + 1].start if i + 1 < len(on_page) else page.offset + len(page.text)
            full = make_span(source, page.number, start, end, len(complete))
            complete.append(full)
            complete_sections.append((full.span_id, section_map[span.span_id]))
    return SemanticSource(replace(source, spans=tuple(complete)), tuple(complete_sections))


def rank(catalog: SemanticSource, query: str, *, limit: int = 40) -> list[Span]:
    if not 1 <= limit <= 80 or len(query) > 8000:
        raise GroundingError("SEMANTIC_RETRIEVAL_LIMIT")
    source = catalog.source
    original = terms(query)
    expanded = set(original)
    for group in GROUPS:
        group_terms = set(group.split())
        if original & group_terms:
            expanded |= group_terms
    rows = [words(s.text) for s in source.spans]
    df = Counter(t for row in rows for t in set(row))
    avg = sum(map(len, rows)) / max(1, len(rows))
    headings = dict(catalog.sections)
    atoms, grams = exact_atoms(query), ngrams(query)
    scored = []
    for index, (span, row) in enumerate(zip(source.spans, rows, strict=True)):
        counts = Counter(row)
        value = 0.0
        for term in expanded:
            if counts[term]:
                idf = math.log(1 + (len(rows) - df[term] + 0.5) / (df[term] + 0.5))
                value += (
                    (1 if term in original else 0.35)
                    * idf
                    * counts[term]
                    * 2.2
                    / (counts[term] + 1.2 * (0.25 + 0.75 * len(row) / max(1, avg)))
                )
        value += 20 * len(atoms & exact_atoms(span.text))
        value += 0.7 * len(original & terms(headings.get(span.span_id, "")))
        gs = ngrams(span.text)
        value += 0.5 * len(gs & grams) / max(1, len(gs | grams))
        scored.append((-value, index))
    return [source.spans[i] for _, i in sorted(scored)[:limit]]


def context(catalog: SemanticSource, selected: list[Span], *, neighbors: int = 1) -> list[Span]:
    if not 0 <= neighbors <= 2:
        raise GroundingError("SEMANTIC_CONTEXT_LIMIT")
    ids = {s.span_id for s in selected}
    spans = catalog.source.spans
    chosen: set[int] = set()
    for index, span in enumerate(spans):
        if span.span_id in ids:
            chosen.update(
                i
                for i in range(max(0, index - neighbors), min(len(spans), index + neighbors + 1))
                if spans[i].page == span.page
            )
    return [spans[i] for i in sorted(chosen)]
