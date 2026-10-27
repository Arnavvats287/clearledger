"""Bounded immutable source locations. No model, database, authority or normalization."""

import hashlib
import json
import re
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass
from functools import cached_property

VERSION = "canonical-spans-1"
Box = tuple[float, float, float, float]


class GroundingError(ValueError):
    """Fixed codes only: never include source text in error messages."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Token:
    token_id: str
    start: int
    end: int
    bbox: Box | None


@dataclass(frozen=True)
class Page:
    number: int
    text: str
    tokens: tuple[Token, ...] = ()
    offset: int = 0

    @cached_property
    def token_starts(self) -> tuple[int, ...]:
        return tuple(t.start for t in self.tokens)

    @cached_property
    def token_ends(self) -> tuple[int, ...]:
        return tuple(t.end for t in self.tokens)


@dataclass(frozen=True)
class Fallback:
    method: str
    source_hash: str
    page: int
    reason: str


@dataclass(frozen=True)
class Span:
    span_id: str
    source_id: str
    source_hash: str
    source_version: str
    page: int
    text: str
    start: int
    end: int
    token_ids: tuple[str, ...]
    bbox: Box | None
    reading_order: int
    source_kind: str


@dataclass(frozen=True)
class Source:
    source_id: str
    source_hash: str
    source_version: str
    pages: tuple[Page, ...]
    spans: tuple[Span, ...]
    source_kind: str
    fallbacks: tuple[Fallback, ...] = ()

    def resolve(self, identifier: str, *, expected_hash: str, expected_version: str) -> Span:
        if (expected_hash, expected_version) != (self.source_hash, self.source_version):
            raise GroundingError("STALE_SOURCE")
        for span in self.spans:
            if span.span_id == identifier:
                if span != make_span(self, span.page, span.start, span.end, span.reading_order):
                    raise GroundingError("SOURCE_SPAN_INTEGRITY")
                return span
        raise GroundingError("UNKNOWN_SPAN")


def make_span(source: Source, number: int, start: int, end: int, order: int) -> Span:
    page = next((p for p in source.pages if p.number == number), None)
    if page is None or not page.offset <= start < end <= page.offset + len(page.text):
        raise GroundingError("INVALID_RANGE")
    left, right = start - page.offset, end - page.offset
    tokens = page.tokens[
        bisect_right(page.token_ends, left) : bisect_left(page.token_starts, right)
    ]
    boxes = [t.bbox for t in tokens if t.bbox is not None]
    bbox = None
    if boxes and len(boxes) == len(tokens):
        bbox = (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
    text = page.text[left:right]
    basis = [
        VERSION,
        source.source_id,
        source.source_hash,
        source.source_version,
        source.source_kind,
        number,
        start,
        end,
        text,
        [(t.token_id, t.start, t.end, t.bbox) for t in tokens],
    ]
    return Span(
        "sp_" + digest(basis)[:32],
        source.source_id,
        source.source_hash,
        source.source_version,
        number,
        text,
        start,
        end,
        tuple(t.token_id for t in tokens),
        bbox,
        order,
        source.source_kind,
    )


def build(
    source_id: str,
    pages: tuple[Page, ...],
    *,
    source_hash: str,
    version: str = "1",
    kind: str = "TEXT",
    fallbacks: tuple[Fallback, ...] = (),
) -> Source:
    if (
        not source_id
        or not re.fullmatch(r"[0-9a-f]{64}", source_hash)
        or not version
        or len(pages) > 200
        or sum(len(p.text) for p in pages) > 500_000
        or len({p.number for p in pages}) != len(pages)
    ):
        raise GroundingError("SOURCE_LIMIT_OR_IDENTITY")
    source = Source(source_id, source_hash, version, pages, (), kind, fallbacks)
    spans: list[Span] = []
    for page in pages:
        if page.number < 1 or page.offset < 0:
            raise GroundingError("INVALID_PAGE")
        previous = 0
        for token in page.tokens:
            if not previous <= token.start < token.end <= len(page.text):
                raise GroundingError("INVALID_TOKEN_RANGE")
            previous = token.end
            if token.bbox is not None and (
                not all(0 <= n <= 1 for n in token.bbox)
                or token.bbox[0] > token.bbox[2]
                or token.bbox[1] > token.bbox[3]
            ):
                raise GroundingError("INVALID_GEOMETRY")
        for line in re.finditer(r"[^\n]+", page.text):
            # Bounded contiguous chunks, never guessed boundaries from dataset annotations.
            for chunk in re.finditer(r".{1,1600}(?:\s|$)|\S{1,1600}", line.group()):
                start, end = line.start() + chunk.start(), line.start() + chunk.end()
                while start < end and page.text[start].isspace():
                    start += 1
                while end > start and page.text[end - 1].isspace():
                    end -= 1
                if start < end:
                    spans.append(
                        make_span(
                            source, page.number, start + page.offset, end + page.offset, len(spans)
                        )
                    )
    if len(spans) > 10_000:
        raise GroundingError("SPAN_LIMIT")
    return Source(source_id, source_hash, version, pages, tuple(spans), kind, fallbacks)


def text_source(
    source_id: str, texts: list[str], *, source_hash: str | None = None, version: str = "1"
) -> Source:
    pages = tuple(Page(i, text) for i, text in enumerate(texts, 1))
    return build(source_id, pages, source_hash=source_hash or digest(texts), version=version)


def span_packet(span: Span) -> dict[str, object]:
    return asdict(span)
