"""Source-only OCR resilience. Missing geometry stays missing; no annotation rescue."""

import math
from typing import Any

from clearledger.source_spans import Box, Fallback, Page, Source, Token, build, digest


def valid_box(value: object) -> Box | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(row, (list, tuple)) and len(row) == 2 for row in value)
    ):
        value = [n for row in value for n in row]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 1 for n in value):
        return None
    left, top, right, bottom = (float(n) for n in value)
    return (left, top, right, bottom) if left <= right and top <= bottom else None


def from_ocr(
    source_id: str,
    raw: dict[str, Any],
    *,
    source_hash: str,
    alternatives: dict[int, str] | None = None,
) -> Source:
    pages = []
    fallbacks = []
    word_count = 0
    data = raw.get("pages", [])
    if not isinstance(data, list) or len(data) > 200:
        from clearledger.source_spans import GroundingError

        raise GroundingError("OCR_PAGE_LIMIT")
    for number, page in enumerate(data, 1):
        declared = page.get("page_idx", number - 1) if isinstance(page, dict) else number - 1
        if type(declared) is not int or declared != number - 1:
            page_alternative = (alternatives or {}).get(number, "")
            pages.append(Page(number, page_alternative))
            fallbacks.append(
                Fallback(
                    "ALTERNATE_TEXT_LAYER_NO_COORDINATES" if page_alternative else "UNAVAILABLE",
                    source_hash,
                    number,
                    "INVALID_OCR_PAGE_ORDER",
                )
            )
            continue
        text = ""
        tokens = []
        bad_word = bad_geometry = False
        blocks = page.get("blocks", []) if isinstance(page, dict) else []
        if not isinstance(blocks, list):
            blocks = []
            bad_word = True
        for block in blocks:
            lines = block.get("lines", []) if isinstance(block, dict) else []
            if not isinstance(lines, list):
                bad_word = True
                continue
            for line in lines:
                words = line.get("words", []) if isinstance(line, dict) else []
                if not isinstance(words, list):
                    bad_word = True
                    continue
                for word in words:
                    word_count += 1
                    if word_count > 60_000:
                        from clearledger.source_spans import GroundingError

                        raise GroundingError("OCR_WORD_LIMIT")
                    value = word.get("value") if isinstance(word, dict) else None
                    if not isinstance(value, str) or not value.strip():
                        bad_word = True
                        continue
                    if len(text) + len(value) > 500_000:
                        from clearledger.source_spans import GroundingError

                        raise GroundingError("OCR_TEXT_LIMIT")
                    if text and not text.endswith("\n"):
                        text += " "
                    start = len(text)
                    text += value
                    box = valid_box(word.get("geometry"))
                    bad_geometry |= box is None
                    tokens.append(
                        Token(
                            "tk_"
                            + digest(
                                [source_id, source_hash, number, start, len(text), value, box]
                            ),
                            start,
                            len(text),
                            box,
                        )
                    )
                if text and not text.endswith("\n"):
                    text += "\n"
            if text and not text.endswith("\n\n"):
                text += "\n"
        text = text.rstrip("\n")
        reason = (
            "EMPTY_OCR_PAGE"
            if not text
            else "INVALID_OCR_WORD"
            if bad_word
            else "INVALID_OCR_GEOMETRY"
            if bad_geometry
            else ""
        )
        if reason:
            alternate = (alternatives or {}).get(number)
            if alternate:
                text, tokens = alternate, []
                method = "ALTERNATE_TEXT_LAYER_NO_COORDINATES"
            else:
                method = "PARTIAL_OCR_TEXT_NO_FABRICATED_COORDINATES" if text else "UNAVAILABLE"
            fallbacks.append(Fallback(method, source_hash, number, reason))
        pages.append(Page(number, text, tuple(tokens)))
    return build(
        source_id, tuple(pages), source_hash=source_hash, kind="OCR", fallbacks=tuple(fallbacks)
    )
