"""Read-only projection of already verified, privacy-filtered evidence into shared spans."""

from clearledger.case_domain import CaseError
from clearledger.source_retrieval import retrieve
from clearledger.source_spans import Page, build, span_packet


def evidence_catalog(hits, pointers, objective, organization):
    allowed = {p.record_id for p in pointers}
    sources, public = {}, []
    for hit in hits:
        if (
            hit.id not in allowed
            or not hit.source_authenticated
            or not hit.source_integrity
            or not hit.is_current
            or hit.metadata.get("privacy_review_required")
        ):
            continue
        source = build(
            f"{organization}/{hit.document_id}/{hit.id}",
            (Page(hit.page, hit.excerpt, offset=hit.start),),
            source_hash=hit.canonical_sha256,
            version=str(hit.document_version),
            kind="VERIFIED_PRIVACY_PROJECTION",
        )
        sources[str(hit.id)] = source
        selected = retrieve(
            source, f"{objective.category} {objective.question} {objective.amount_paise}", limit=4
        )
        # Context is not assertion proof; the existing source-fact verifier remains authoritative.
        for span in selected or source.spans[:1]:
            public.append({"record_id": str(hit.id), **span_packet(span)})
    return sources, public


def validate_span_selection(value, sources, catalog, *, required):
    index = {row["span_id"]: row for row in catalog}
    selected = value.evidence_span_ids
    if len(selected) != len(set(selected)) or not set(selected) <= index.keys():
        raise CaseError("INVALID_AI_SOURCE_SPAN")
    records = set()
    for identifier in selected:
        row = index[identifier]
        source = sources[row["record_id"]]
        source.resolve(
            identifier, expected_hash=row["source_hash"], expected_version=row["source_version"]
        )
        records.add(row["record_id"])
    if (required or selected) and records != {str(r) for r in value.record_ids}:
        raise CaseError("INVALID_AI_SOURCE_SPAN")
