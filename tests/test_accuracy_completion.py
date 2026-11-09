"""Development admission and source provenance checks with synthetic fixtures."""

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from clearledger.source_invoice_candidates import candidates, fallback_candidates
from clearledger.source_semantics import section_rank, semantic_source
from clearledger.source_spans import Page, build, digest, text_source

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from accuracy_schema_probe import feature_probes, run_probe, synthesis_probes  # noqa: E402
from accuracy_score import scoped_packet  # noqa: E402
from external_eval.accuracy_nli import (  # noqa: E402
    DecisionResponse,
    packet,
    provider_shape,
    validate,
)
from external_eval.contracts import ContractPacket, Hypothesis  # noqa: E402
from external_eval.gemini_http import GeminiHTTP, ProviderError  # noqa: E402
from external_eval.scorers import GoldNli, score_contract  # noqa: E402


def test_transport_shape_does_not_replace_local_validation() -> None:
    transport = provider_shape(DecisionResponse.model_json_schema())
    assert set(transport["properties"]["answers"]) == {"type", "items"}
    src = semantic_source(text_source("fixture", ["Archival copies may be retained."]))
    view = packet(
        src,
        [{"hypothesis_id": "H01", "text": "Archival copies may be retained."}],
        request="fixture",
    )
    row = {
        "hypothesis_id": "H01",
        "aliases": ["E999"],
        "predicted_label": "Entailment",
        "relation": "SUPPORT",
        "contradiction_basis": "NONE",
    }
    assert validate({"answers": [row]}, view)[0].status == "INVALID_ALIAS"
    assert validate({"answers": [row, row]}, view)[0].status == "MODEL_OUTPUT_FAILURE"
    assert validate({"answers": []}, view)[0].status == "MODEL_OUTPUT_FAILURE"


def test_minimal_schema_and_one_variable_max_items_probe() -> None:
    probes = dict(feature_probes())
    assert probes["minimal"]["properties"]["items"]["items"]["properties"]["evidence"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    variant = dict(synthesis_probes())["exact-without-outer-maxItems"]
    variant["properties"]["answers"]["maxItems"] = 17
    assert variant == DecisionResponse.model_json_schema()


@pytest.mark.parametrize(("http_status", "calls"), [(503, 3), (400, 1), (403, 1)])
def test_probe_distinguishes_transient_from_semantic_rejection(
    tmp_path: Path,
    http_status: int,
    calls: int,
) -> None:
    seen = []
    waits: list[float] = []

    class Fake:
        def request(self, operation: str, body: dict[str, Any]) -> dict[str, Any]:
            seen.append((operation, body))
            raise ProviderError("PROVIDER_ERROR", http_status)

    run_probe(tmp_path / "probe", cast(GeminiHTTP, Fake()), sleep=waits.append)
    assert len(seen) == calls
    assert waits == ([20, 40] if calls == 3 else [])
    assert len(list((tmp_path / "probe").glob("*.started.json"))) == calls


@pytest.mark.parametrize("separator", ["/", "\\"])
def test_pdf_text_fallback_value_and_explicit_no_geometry(separator: str) -> None:
    ocr = candidates(text_source("invoice", ["Invoice\nInvoice no: A-11"]))
    pdf = build(
        "invoice",
        (Page(1, f"Invoice\nInvoice no: A-11\nInvoice no: A {separator}\n  12"),),
        source_hash=digest("pdf fixture bytes"),
        kind="PDF_TEXT",
    )
    fallback = fallback_candidates(ocr, pdf)
    assert all(item.value != "A-11" for item in fallback.items)
    candidate = next(item for item in fallback.items if item.value == f"A{separator}12")
    span = fallback.source.resolve(
        candidate.span_id, expected_hash=pdf.source_hash, expected_version=pdf.source_version
    )
    assert span.text == f"A {separator}\n  12"
    assert span.bbox is None
    assert span.token_ids == ()
    with pytest.raises(ValueError, match="STALE_SOURCE"):
        fallback.source.resolve(
            candidate.span_id,
            expected_hash=ocr.source.source_hash,
            expected_version=pdf.source_version,
        )


def test_section_rank_preserves_canonical_scope_and_budget() -> None:
    src = semantic_source(
        text_source(
            "fixture",
            [
                "1. RETENTION\nArchival copies may be kept.\nThey remain confidential.\n"
                "2. ASSIGNMENT\nAssignment requires consent.\n3. NOTICE\nGive written notice."
            ],
        )
    )
    selected = section_rank(src, "Archival copies may be kept", limit=3, hybrid=True)
    assert len({s.span_id for s in selected}) == 3
    assert any("Archival copies" in s.text for s in selected)
    view = packet(
        src,
        [{"hypothesis_id": "H01", "text": "Archival copies may be kept"}],
        request="test",
        strategy="section-hybrid",
        k=3,
    )
    assert len(view.registry.bindings) == 3
    assert all(b.source_hash == src.source.source_hash for b in view.registry.bindings)


def test_single_hypothesis_scoring_preserves_full_source_and_exact_denominator() -> None:
    source = ContractPacket(
        document_id="unit",
        text="Archival copies may be retained.",
        hypotheses=[
            Hypothesis(hypothesis_id="H01", text="Copies may be retained."),
            Hypothesis(hypothesis_id="H02", text="Copies must be returned."),
        ],
    )
    scoped = scoped_packet(source, {"H02"})
    assert scoped.text == source.text and len(source.hypotheses) == 2
    gold = [GoldNli("unit", "H02", "NotMentioned", ())]
    assert score_contract({"unit": scoped}, [], gold)["accuracy"] == 0
    with pytest.raises(ValueError, match="INVALID_DEVELOPMENT_HYPOTHESIS_SCOPE"):
        scoped_packet(source, {"H03"})
