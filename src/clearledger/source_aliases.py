"""Request-local presentation aliases; immutable canonical locations remain authoritative."""

import re
from dataclasses import dataclass

from clearledger.source_spans import GroundingError, Source, Span, digest


@dataclass(frozen=True)
class Binding:
    alias: str
    canonical_id: str
    source_id: str
    source_hash: str
    source_version: str


@dataclass(frozen=True)
class Aliases:
    scope: str
    bindings: tuple[Binding, ...]
    sources: tuple[Source, ...]

    def resolve(self, alias: str, *, scope: str, current: tuple[Source, ...] | None = None) -> Span:
        if scope != self.scope:
            raise GroundingError("ALIAS_REQUEST_MISMATCH")
        binding = next((b for b in self.bindings if b.alias == alias), None)
        if binding is None:
            raise GroundingError("UNKNOWN_ALIAS")
        source = next(
            (
                s
                for s in (current if current is not None else self.sources)
                if s.source_id == binding.source_id
            ),
            None,
        )
        if source is None:
            raise GroundingError("ALIAS_SOURCE_SCOPE")
        return source.resolve(
            binding.canonical_id,
            expected_hash=binding.source_hash,
            expected_version=binding.source_version,
        )

    def alias_for(self, canonical_id: str) -> str:
        binding = next((b for b in self.bindings if b.canonical_id == canonical_id), None)
        if binding is None:
            raise GroundingError("UNEXPOSED_CANONICAL_ID")
        return binding.alias


def aliases(
    sources: tuple[Source, ...], spans: list[Span], *, request: str, prefix: str = "E"
) -> Aliases:
    if not request or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,8}", prefix) or len(spans) > 1000:
        raise GroundingError("ALIAS_LIMIT_OR_SCOPE")
    if len({s.source_id for s in sources}) != len(sources):
        raise GroundingError("ALIAS_SOURCE_COLLISION")
    ids = [s.span_id for s in spans]
    if len(set(ids)) != len(ids):
        raise GroundingError("ALIAS_CANONICAL_COLLISION")
    bindings = tuple(
        Binding(f"{prefix}{i:02}", s.span_id, s.source_id, s.source_hash, s.source_version)
        for i, s in enumerate(spans, 1)
    )
    scope = digest(
        [request, [(b.alias, b.canonical_id, b.source_hash, b.source_version) for b in bindings]]
    )
    result = Aliases(scope, bindings, sources)
    for b in bindings:
        result.resolve(b.alias, scope=scope)
    return result
