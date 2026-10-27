"""Scorer-only denominator bridge; no fabricated packets for rejected OCR inputs."""

from typing import Any

from .contracts import DocileOutput, DocilePacket
from .scorers import GoldInvoice, prf, ratio, score_docile
from .source import normalized


def score_with_input_failures(
    packets: dict[str, DocilePacket],
    outputs: list[DocileOutput],
    gold: list[GoldInvoice],
    failures: set[str],
) -> dict[str, Any]:
    if set(packets) & failures or set(packets) | failures != {g.document_id for g in gold}:
        raise ValueError("INPUT_FAILURE_COVERAGE_MISMATCH")
    if len({g.document_id for g in gold}) != len(gold):
        raise ValueError("DUPLICATE_GOLD")
    if any(o.document_id in failures and o.invoice_references for o in outputs):
        raise ValueError("INPUT_FAILURE_WITH_PREDICTIONS")
    result = score_docile(
        packets,
        [o for o in outputs if o.document_id not in failures],
        [g for g in gold if g.document_id not in failures],
    )
    counts = result["counts"]
    for item in gold:
        if item.document_id not in failures:
            continue
        counts["fn"] += len({normalized(v) for v in item.references}) if item.is_invoice else 0
        counts["missing_outputs"] += 1
        counts["abstained_documents"] += 1
        counts["non_invoice_documents"] += not item.is_invoice
    result.update(
        documents=len(gold),
        invoice_id=prf(counts["tp"], counts["fp"], counts["fn"]),
        exact_set_match=ratio(counts["exact_set_match"], len(gold)),
        coverage=ratio(counts["covered_documents"], len(gold)),
        adapter_input_failures=len(failures),
        denominator_bridge="v1; algebraically equivalent to missing-output frozen scorer semantics",
    )
    return result
