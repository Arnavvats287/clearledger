"""Short names for existing typed provider contracts; host provenance checks still run."""

from copy import deepcopy
from typing import Any

from clearledger.source_spans import GroundingError

PRESENTATION_VERSION = "request-aliases-1"


def names(ids: list[str], prefix: str) -> dict[str, str]:
    if len(ids) > 1000 or len(ids) != len(set(ids)) or prefix not in {"E", "C"}:
        raise GroundingError("ALIAS_COLLISION_OR_LIMIT")
    return {f"{prefix}{i:02}": value for i, value in enumerate(ids, 1)}


def canonical(value: str, mapping: dict[str, str]) -> str:
    if value not in mapping:
        raise GroundingError("UNKNOWN_ALIAS")
    return mapping[value]


def remittance_packet(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    public = deepcopy(payload)
    spans = names([s["span_id"] for s in public["source_spans"]], "E")
    candidates = names([c["candidate_id"] for c in public["invoice_candidates"]], "C")
    reverse = {v: k for k, v in spans.items()}
    reverse_c = {v: k for k, v in candidates.items()}
    for span in public["source_spans"]:
        span["span_id"] = reverse[span["span_id"]]
    for candidate in public["invoice_candidates"]:
        candidate["candidate_id"] = reverse_c[candidate["candidate_id"]]
        candidate["span_id"] = reverse[candidate["span_id"]]
    return public, {"spans": spans, "candidates": candidates}


def remittance_selection(
    value: dict[str, Any], mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    result = deepcopy(value)
    for field in ("invoice_candidate_ids", "utr_span_ids", "unparsed_span_ids"):
        table = mapping["candidates" if field == "invoice_candidate_ids" else "spans"]
        result[field] = [canonical(v, table) for v in result[field]]
    if result.get("payer_span_id") is not None:
        result["payer_span_id"] = canonical(result["payer_span_id"], mapping["spans"])
    for claim in result["claims"]:
        for field in ("description_span_id", "amount_span_id", "reason_code_span_id"):
            if claim.get(field) is not None:
                claim[field] = canonical(claim[field], mapping["spans"])
    return result


def investigation_packet(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    result = deepcopy(payload)
    rows = result.get("evidence_spans", [])
    mapping = names([r["span_id"] for r in rows], "E")
    reverse = {v: k for k, v in mapping.items()}
    for row in rows:
        row["span_id"] = reverse[row["span_id"]]
    return result, mapping
