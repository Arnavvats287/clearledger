"""Local bounded lexical recall; relevance never authenticates or proves an assertion."""

import math
import re
from collections import Counter
from dataclasses import dataclass

from clearledger.source_spans import GroundingError, Source, Span

STOP = set(
    "a an the this that is are be been being to of in on for by with as and or "
    "party parties receiving disclosing agreement information confidential may shall "
    "must can will it its any such under not no only".split()
)


def words(text: str) -> list[str]:
    return re.findall(r"[\w]+(?:[-./][\w]+)*", text.casefold())


def terms(text: str) -> set[str]:
    return {w for w in words(text) if w not in STOP and len(w) > 2}


def exact_atoms(text: str) -> set[str]:
    # Financial amounts, dates and identifiers retain punctuation and leading zeroes.
    return {w for w in re.findall(r"[\w]+(?:[-./][\w]+)*", text) if any(c.isdigit() for c in w)}


def ngrams(text: str) -> set[str]:
    value = " ".join(words(text))[:4000]
    return {value[i : i + 3] for i in range(max(0, len(value) - 2))}


def retrieve(source: Source, query: str, *, limit: int = 8, neighbors: int = 1) -> list[Span]:
    if not 1 <= limit <= 64 or not 0 <= neighbors <= 2 or len(query) > 8000:
        raise GroundingError("RETRIEVAL_LIMIT")
    tokens = [words(s.text) for s in source.spans]
    frequencies = Counter(w for row in tokens for w in set(row))
    query_terms = terms(query)
    atoms = exact_atoms(query)
    query_grams = ngrams(query)
    average = sum(map(len, tokens)) / max(1, len(tokens))
    scored = []
    for i, (span, row) in enumerate(zip(source.spans, tokens, strict=True)):
        counts = Counter(row)
        score = 0.0
        for term in query_terms:
            tf = counts[term]
            if tf:
                idf = math.log(
                    1 + (len(tokens) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(row) / max(1, average)))
        # Exact financial keys/numerics dominate weaker lexical/character similarities.
        score += 20 * len(atoms & exact_atoms(span.text))
        grams = ngrams(span.text)
        score += 0.5 * len(grams & query_grams) / max(1, len(query_grams | grams))
        if score > 0:
            scored.append((-score, i))
    ranked = [i for _, i in sorted(scored)[:limit]]
    selected = set(ranked)
    for index in ranked:
        for i in range(max(0, index - neighbors), min(len(source.spans), index + neighbors + 1)):
            if source.spans[i].page == source.spans[index].page:
                selected.add(i)
    return [source.spans[i] for i in sorted(selected)]


@dataclass(frozen=True)
class AssertionCheck:
    admitted: bool
    reasons: tuple[str, ...]
    financial_authority: bool = False


def assertion_gate(
    source: Source,
    ids: list[str],
    assertion: str,
    *,
    source_hash: str,
    source_version: str,
    relation: str,
    current: bool = True,
    authenticated: bool = True,
    contradictory: bool = False,
    required_atoms: tuple[str, ...] = (),
) -> AssertionCheck:
    reasons = []
    if not current or not authenticated:
        reasons.append("UNVERIFIED_OR_STALE_SOURCE")
    selected = [
        source.resolve(i, expected_hash=source_hash, expected_version=source_version) for i in ids
    ]
    if len(ids) != len(set(ids)):
        reasons.append("DUPLICATE_SPAN")
    text = "\n".join(s.text for s in selected)
    query_terms = terms(assertion)
    if not selected or len(query_terms & terms(text)) < min(2, max(1, len(query_terms))):
        reasons.append("NO_RELEVANT_EVIDENCE")
    if not set(required_atoms) <= exact_atoms(text):
        reasons.append("EXACT_FACT_MISMATCH")
    if contradictory:
        reasons.append("UNRESOLVED_CONFLICT")
    if relation not in {"SUPPORT", "CONFLICT"}:
        reasons.append("NO_ASSERTIVE_RELATION")
    explicit_negative = re.search(
        r"\b(?:not|no|never|prohibit\w*|except|unless|without|only|inconsistent|disagree\w*)\b",
        text,
        re.I,
    )
    positive_against_negative = re.search(
        r"\b(?:not|no|never|prohibit\w*)\b", assertion, re.I
    ) and re.search(r"\b(?:permitted|may|allowed|required|must)\b", text, re.I)
    if relation == "CONFLICT" and not (explicit_negative or positive_against_negative):
        reasons.append("NO_EXPLICIT_CONFLICT")
    # This is necessary admission, not a universal semantic entailment engine.
    # Product source-fact predicates must independently establish the same conclusion.
    return AssertionCheck(not reasons, tuple(reasons))
