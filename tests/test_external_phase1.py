"""Evaluation-only schemas, leakage boundaries and independently checked scorer arithmetic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from external_eval.contracts import (  # noqa: E402
    Answer,
    ContractOutput,
    ContractPacket,
    DocileOutput,
    Edge,
    Hypothesis,
    InvoiceReference,
    ProviderMetadata,
    Quote,
)
from external_eval.gold import (  # noqa: E402
    check_seal,
    contract_gold,
    docile_scorer_view,
    seal_predictions,
    verify_gold_sources,
)
from external_eval.scorers import (  # noqa: E402
    GoldInvoice,
    GoldNli,
    kile_predictions,
    overlap_counts,
    score_contract,
    score_docile,
    score_edges,
)
from external_eval.source import (  # noqa: E402
    RECBENCH_COLUMNS,
    contract_packets,
    docile_packet,
    load_plan,
    locate,
    no_links,
    normalized,
    project_recbench_sources,
    read_packets,
    sha256,
    verify_source_tables,
    write_json,
    write_packets,
)


def packet():
    return ContractPacket(
        document_id="fixture",
        text="alpha beta gamma",
        hypotheses=[Hypothesis(hypothesis_id=f"h{i}", text=f"Assertion {i}") for i in range(3)],
    )


def output(labels, quotes=None, **metadata):
    return ContractOutput(
        document_id="fixture",
        answers=[
            Answer(
                hypothesis_id=f"h{i}",
                predicted_label=label,
                evidence_quotes=[Quote(text=quotes[i])] if quotes else [],
            )
            for i, label in enumerate(labels)
        ],
        metadata=ProviderMetadata(provider="offline-fixture", **metadata),
    )


def gold():
    return [
        GoldNli("fixture", "h0", "Entailment", ((0, 5),)),
        GoldNli("fixture", "h1", "Contradiction", ((6, 10),)),
        GoldNli("fixture", "h2", "NotMentioned", ()),
    ]


def ocr_data(values=("INV-001", "amount")):
    return {
        "pages": [
            {
                "page_idx": 0,
                "dimensions": [100, 100],
                "blocks": [
                    {
                        "lines": [
                            {
                                "words": [
                                    {
                                        "value": value,
                                        "geometry": [[0.1 + i * 0.2, 0.1], [0.2 + i * 0.2, 0.2]],
                                    }
                                    for i, value in enumerate(values)
                                ]
                            }
                        ]
                    }
                ],
            }
        ]
    }


def doc_packet(tmp_path, values=("INV-001", "amount")):
    path = tmp_path / "ocr.json"
    write_json(path, ocr_data(values))
    return docile_packet(path, "fixture")


def doc_output(value="INV-001", quote="INV-001", page=None, **metadata):
    return DocileOutput(
        document_id="fixture",
        invoice_references=[InvoiceReference(value=value, quote=Quote(text=quote), page=page)],
        metadata=ProviderMetadata(provider="offline-fixture", **metadata),
    )


def json_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(json_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(json_keys(v) for v in value))
    return set()


def test_contract_projection_has_only_source_and_hypotheses(tmp_path):
    path = tmp_path / "dev.json"
    data = {
        "labels": {"h0": {"hypothesis": "A public hypothesis", "choice": "POISON"}},
        "documents": [
            {
                "id": 1,
                "text": "Prepared source contract.",
                "url": "private",
                "file_name": "private",
                "spans": [[0, 5]],
                "annotation_sets": [{"annotations": {"h0": {"choice": "POISON"}}}],
            }
        ],
    }
    write_json(path, data)
    projected = contract_packets(path, ["1"], ["h0"])[0].model_dump()
    assert set(projected) == {"document_id", "text", "hypotheses"}
    assert set(projected["hypotheses"][0]) == {"hypothesis_id", "text"}
    assert not {"annotation_sets", "choice", "spans", "url", "file_name"} & json_keys(projected)
    assert "POISON" not in json.dumps(projected)


@pytest.mark.parametrize("extra", ["annotation_sets", "choice", "spans", "url", "label"])
def test_packet_rejects_answer_or_metadata_keys(extra):
    data = packet().model_dump()
    data[extra] = "untrusted"
    with pytest.raises(ValidationError):
        ContractPacket.model_validate(data)


def test_docile_projection_uses_ocr_only_not_gold(tmp_path):
    data = ocr_data()
    data["field_extractions"] = [{"text": "GOLD-POISON", "bbox": [0, 0, 1, 1]}]
    data["metadata"] = {"document_type": "GOLD-POISON"}
    path = tmp_path / "ocr.json"
    write_json(path, data)
    projected = docile_packet(path, "fixture").model_dump()
    assert "GOLD-POISON" not in json.dumps(projected)
    assert not {
        "field_extractions",
        "metadata",
        "document_type",
        "line_item_extractions",
    } & json_keys(projected)
    assert projected["pages"][0]["words"][0]["box"]["left"] == 0.1


def test_recbench_projection_excludes_labels_and_truth(tmp_path):
    root, destination = tmp_path / "dataset", tmp_path / "inputs"
    (root / "csv").mkdir(parents=True)
    for name, columns in RECBENCH_COLUMNS.items():
        (root / "csv" / f"{name}.csv").write_text(columns.replace(" ", ",") + "\n")
    (root / "csv" / "labels_ledger.csv").write_text("GOLD-POISON")
    (root / "csv" / "truth_ledger_processor.csv").write_text("GOLD-POISON")
    manifest = project_recbench_sources(root, destination)
    assert set(manifest) == {f"{name}.csv" for name in RECBENCH_COLUMNS}
    assert not any("GOLD-POISON" in p.read_text() for p in destination.iterdir())
    assert not any(p.is_symlink() or p.is_junction() for p in destination.iterdir())
    verify_source_tables(destination, manifest)
    (destination / "truth_ledger_processor.csv").write_text("GOLD-POISON")
    with pytest.raises(ValueError, match="UNEXPECTED_SOURCE_TABLES"):
        verify_source_tables(destination, manifest)


def test_recbench_rejects_leaked_column(tmp_path):
    (tmp_path / "csv").mkdir()
    (tmp_path / "csv" / "bank_statements.csv").write_text("stmt_line_id,match_type\n")
    with pytest.raises(ValueError, match="UNEXPECTED_SOURCE_COLUMNS"):
        project_recbench_sources(tmp_path, tmp_path / "output")


@pytest.mark.parametrize(
    "text,quote,status",
    [
        ("alpha beta", "alpha", "VALID"),
        ("alpha beta", "missing", "MISSING"),
        ("alpha alpha", "alpha", "AMBIGUOUS"),
        ("aaaa", "aaa", "AMBIGUOUS"),
    ],
)
def test_independent_exact_quote_location(text, quote, status):
    result = locate(text, Quote(text=quote))
    assert result.status == status
    assert bool(result.intervals) == (status == "VALID")


def test_offsets_cannot_select_a_gold_compatible_duplicate():
    assert locate("same same", Quote(text="same", start=5, end=9)).status == "AMBIGUOUS"
    assert locate("one two", Quote(text="two", start=0, end=3)).status == "RANGE_MISMATCH"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("  INV-001  ", "INV-001"),
        ("I  001", "I  001"),
        ("i-001", "i-001"),
        ("INV/001", "INV/001"),
        ("e\u0301-01", "é-01"),
    ],
)
def test_frozen_normalization(value, expected):
    assert normalized(value) == expected


def test_native_geometry_is_source_union_and_zero_based(tmp_path):
    source = doc_packet(tmp_path)
    prediction = doc_output(quote="INV-001 amount", page=0)
    native, counts = kile_predictions(source, prediction)
    assert native[0]["bbox"] == [0.1, 0.1, 0.4, 0.2]
    assert native[0]["page"] == 0
    assert native[0]["fieldtype"] == "document_id"
    assert counts["VALID"] == 1


def test_duplicate_quote_cannot_be_rescued_by_page_or_gold(tmp_path):
    source = doc_packet(tmp_path, ("INV-001", "INV-001"))
    native, counts = kile_predictions(source, doc_output(page=0))
    assert native == []
    assert counts["AMBIGUOUS"] == 1


@pytest.mark.parametrize(
    "value,quote,page,status",
    [
        ("OTHER", "INV-001", None, "VALUE_NOT_IN_QUOTE"),
        ("INV-001", "INV-001", 3, "PAGE_MISMATCH"),
        ("MISSING", "MISSING", None, "UNALIGNED"),
    ],
)
def test_invalid_localization_is_not_rescued(tmp_path, value, quote, page, status):
    native, counts = kile_predictions(doc_packet(tmp_path), doc_output(value, quote, page))
    assert native == []
    assert counts[status] == 1


def test_classification_and_joint_evidence_metrics_hand_calculation():
    result = score_contract(
        {"fixture": packet()}, [output(["Entailment"] * 3, ["alpha", "beta", "gamma"])], gold()
    )
    assert result["accuracy"] == pytest.approx(1 / 3)
    assert result["macro_f1"] == pytest.approx(1 / 6)
    assert result["unsupported_conclusion_rate"] == pytest.approx(2 / 3)
    assert result["per_class"]["Entailment"]["precision"] == pytest.approx(1 / 3)
    assert result["per_class"]["Entailment"]["recall"] == 1
    assert result["evidence_character_overlap"]["tp"] == 9
    assert result["evidence_character_overlap"]["f1"] == 1
    assert result["joint_correct_label_evidence"]["tp"] == 5
    assert result["joint_correct_label_evidence"]["fn"] == 4
    assert result["joint_correct_label_evidence"]["f1"] == pytest.approx(5 / 7)
    assert result["counts"]["quotes_on_gold_notmentioned"] == 1
    assert result["quote_validity"] == 1


def test_abstain_failure_and_notmentioned_are_distinct():
    result = score_contract(
        {"fixture": packet()}, [output(["Abstain", "ProviderFailure", "NotMentioned"])], gold()
    )
    assert result["accuracy"] == pytest.approx(1 / 3)
    assert result["answered_only_accuracy"] == 1
    assert result["counts"]["abstentions"] == 1
    assert result["counts"]["provider_failures"] == 1
    assert result["unsupported_conclusion_rate"] is None
    assert result["evidence_character_overlap"]["fn"] == 9


def test_provider_document_failure_covers_missing_answers():
    result = score_contract({"fixture": packet()}, [output([], failure="PROVIDER")], gold())
    assert result["pairs"] == 3
    assert result["accuracy"] == 0
    assert result["counts"]["provider_failures"] == 3
    assert result["answered_only_accuracy"] is None


def test_full_204_pair_denominator_without_reading_real_test_answers():
    packets, truth = {}, []
    for doc in range(12):
        key = f"unit-{doc}"
        packets[key] = ContractPacket(
            document_id=key,
            text="Minimal fixture.",
            hypotheses=[
                Hypothesis(hypothesis_id=f"h{i}", text="Unit assertion.") for i in range(17)
            ],
        )
        truth.extend(GoldNli(key, f"h{i}", "NotMentioned", ()) for i in range(17))
    result = score_contract(packets, [], truth)
    assert result["pairs"] == 204
    assert result["counts"]["abstentions"] == 204
    assert result["accuracy"] == 0


def test_scorer_rejects_incomplete_gold_or_unknown_predictions():
    with pytest.raises(ValueError, match="GOLD_COVERAGE_MISMATCH"):
        score_contract({"fixture": packet()}, [], gold()[:1])
    unknown = output(["NotMentioned"])
    unknown.answers[0].hypothesis_id = "unknown"
    with pytest.raises(ValueError, match="UNKNOWN_HYPOTHESIS"):
        score_contract({"fixture": packet()}, [unknown], gold())
    with pytest.raises(ValueError, match="FAILURE_WITH_SUCCESSFUL"):
        score_contract({"fixture": packet()}, [output(["Entailment"], failure="PROVIDER")], gold())


def test_docile_secondary_counts_false_emission_and_missing_quote(tmp_path):
    source = doc_packet(tmp_path)
    truth = [GoldInvoice("fixture", True, ("INV-001",))]
    good = score_docile({"fixture": source}, [doc_output()], truth)
    assert good["invoice_id"]["f1"] == 1
    invalid = score_docile({"fixture": source}, [doc_output(quote="invented")], truth)
    assert invalid["invoice_id"]["tp"] == 0
    assert invalid["invoice_id"]["fp"] == invalid["invoice_id"]["fn"] == 1
    other = score_docile({"fixture": source}, [doc_output()], [GoldInvoice("fixture", False, ())])
    assert other["counts"]["non_invoice_false_emissions"] == 1
    assert other["unsupported_field_rate"] == 1


def test_edge_scorer_hand_checked_duplicates_and_abstention():
    a = Edge(txn_id="t1", line_id="l1")
    b = Edge(txn_id="t2", line_id="l2")
    c = Edge(txn_id="t3", line_id="l3")
    result = score_edges([a, b], [a, a, c], {"t2"})
    assert result["tp"] == result["fp"] == result["fn"] == 1
    assert result["f1"] == 0.5
    assert result["duplicate_prediction_count"] == 1
    assert result["missed_edges_for_abstained_transactions"] == 1
    with pytest.raises(ValueError, match="ABSTENTION_CONFLICT"):
        score_edges([a], [a], {"t1"})
    with pytest.raises(ValueError, match="DUPLICATE_GOLD"):
        score_edges([a, a], [])


def test_edge_scorer_preserves_one_to_many_truth():
    a, b = Edge(txn_id="t1", line_id="l1"), Edge(txn_id="t1", line_id="l2")
    result = score_edges([a, b], [a])
    assert result["tp"] == result["fn"] == 1
    assert result["fp"] == 0
    assert result["recall"] == 0.5


intervals = st.lists(
    st.tuples(st.integers(0, 50), st.integers(1, 20)).map(
        lambda pair: (pair[0], pair[0] + pair[1])
    ),
    max_size=12,
)


@given(intervals, intervals)
def test_character_overlap_against_independent_character_set_oracle(left, right):
    expected = {char for a, b in left for char in range(a, b)}
    predicted = {char for a, b in right for char in range(a, b)}
    result = overlap_counts(left, right)
    assert result["tp"] == len(expected & predicted)
    assert result["fp"] == len(predicted - expected)
    assert result["fn"] == len(expected - predicted)


def test_prediction_seal_and_source_packet_hashes(tmp_path):
    directory = tmp_path / "inputs"
    manifest = write_packets(directory, [packet()])
    loaded = read_packets(directory, manifest, "contract-nli")
    assert set(loaded) == {"fixture"}
    predictions = tmp_path / "outputs.jsonl"
    predictions.write_text("{}\n")
    seal = tmp_path / "seal.json"
    seal_predictions(predictions, seal, manifest, "a" * 64)
    check_seal(predictions, seal, manifest, "a" * 64)
    predictions.write_text("changed\n")
    with pytest.raises(ValueError, match="PREDICTION_SEAL_MISMATCH"):
        check_seal(predictions, seal, manifest, "a" * 64)
    (directory / "fixture.json").write_text("{}")
    with pytest.raises(ValueError, match="PACKET_HASH_MISMATCH"):
        read_packets(directory, manifest, "contract-nli")


def test_unexpected_gold_file_in_packet_directory_rejected(tmp_path):
    manifest = write_packets(tmp_path / "inputs", [packet()])
    (tmp_path / "inputs" / "labels.json").write_text("{}")
    with pytest.raises(ValueError, match="UNEXPECTED_PACKET_FILES"):
        read_packets(tmp_path / "inputs", manifest, "contract-nli")


def test_linked_ancestor_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == "trap")
    with pytest.raises(ValueError, match="LINK_REFUSED"):
        no_links(tmp_path / "trap" / "source.json")


def test_production_and_scorer_modules_absent_from_fresh_packet_reader():
    code = (
        "import sys;sys.path.insert(0,sys.argv[1]);import external_eval.source;"
        "assert 'external_eval.gold' not in sys.modules;"
        "assert not any(k.startswith(('clearledger','google.genai')) for k in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SCRIPTS)], capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode()


def test_packet_reader_operates_with_gold_and_network_reads_denied(tmp_path):
    directory = tmp_path / "inputs"
    manifest = write_packets(directory, [packet()])
    metadata = tmp_path / "manifest.json"
    write_json(metadata, manifest)
    outside = tmp_path / "scorer-only.json"
    outside.write_text("NEVER_READ_THIS_GOLD")
    code = """
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from external_eval.source import read_packets
root = pathlib.Path(sys.argv[2]).resolve()
manifest = json.loads(pathlib.Path(sys.argv[3]).read_text())
def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
        raise PermissionError("NO_EXTERNAL_CAPABILITY")
    if event == "open":
        path = pathlib.Path(args[0]).resolve()
        if not path.is_relative_to(root):
            raise PermissionError("OUTSIDE_PACKET_BOUNDARY")
sys.addaudithook(audit)
assert len(read_packets(root, manifest, "contract-nli")) == 1
try:
    pathlib.Path(sys.argv[4]).read_text()
except PermissionError:
    pass
else:
    raise AssertionError("GOLD_WAS_READABLE")
assert "external_eval.gold" not in sys.modules
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(SCRIPTS),
            str(directory),
            str(metadata),
            str(outside),
        ],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode()


def test_gold_reader_uses_selected_dev_only_and_native_view_preserves_boxes(tmp_path):
    dev = tmp_path / "dev.json"
    write_json(
        dev,
        {
            "documents": [
                {
                    "id": 1,
                    "text": "alpha",
                    "spans": [[0, 5]],
                    "annotation_sets": [
                        {"annotations": {"h0": {"choice": "Entailment", "spans": [0]}}}
                    ],
                },
                {"id": 2, "annotation_sets": "DO_NOT_INTERPRET_UNSELECTED_GOLD"},
            ]
        },
    )
    assert contract_gold(dev, ["1"], ["h0"])[0].evidence == ((0, 5),)
    source, destination = tmp_path / "docile", tmp_path / "scorer-view"
    original = {
        "metadata": {"document_type": "tax_invoice"},
        "field_extractions": [
            {"fieldtype": "document_id", "text": "INV-001", "bbox": [0.1, 0.2, 0.3, 0.4]},
            {"fieldtype": "date_issue", "text": "unmapped"},
        ],
        "line_item_extractions": [],
    }
    path = source / "annotations" / "one.json"
    write_json(path, original)
    write_json(source / "ocr" / "one.json", ocr_data())
    before = sha256(path)
    docile_scorer_view(source, ["one"], destination, "fixture_split")
    copied = json.loads((destination / "annotations" / "one.json").read_text())
    assert copied["field_extractions"] == original["field_extractions"][:1]
    assert sha256(path) == before


def test_plan_check_never_rewrites_frozen_files(tmp_path):
    path = tmp_path / "plan.json"
    write_json(path, {"protocol": "clearledger-external-evaluation-v1"})
    path.with_suffix(".sha256").write_text(sha256(path))
    before = path.read_bytes()
    assert load_plan(path)["protocol"] == "clearledger-external-evaluation-v1"
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "data",
    [
        {"txn_id": "t", "line_id": "l", "relation": "gold"},
        {"txn_id": "../unsafe", "line_id": "l"},
    ],
)
def test_typed_edges_reject_extra_truth_attributes_and_unsafe_keys(data):
    with pytest.raises(ValidationError):
        Edge.model_validate(data)


@pytest.mark.parametrize(
    "extra,value",
    [("predicted_label", "Approved"), ("confidence", 1.1), ("financial_authority", True)],
)
def test_prediction_contract_rejects_invalid_labels_confidence_and_authority(extra, value):
    data = {"hypothesis_id": "h0", "predicted_label": "Entailment"}
    data[extra] = value
    with pytest.raises(ValidationError):
        Answer.model_validate(data)


def test_gold_source_hash_check_before_answer_parsing(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "dev.json").write_text("not-even-answer-json")
    inventory = tmp_path / "inventory.json"
    write_json(
        inventory,
        {"datasets": {"contract-nli": {"inspection": {"splits": {"dev": {"sha256": "0" * 64}}}}}},
    )
    plan = {"inventory_sha256": sha256(inventory)}
    with pytest.raises(ValueError, match="GOLD_SOURCE_CHANGED"):
        verify_gold_sources(inventory, plan, "contract-nli", source, "adapter")


def test_real_scoring_cli_with_synthetic_plan_seals_and_gold(tmp_path):
    source, inputs = tmp_path / "source", tmp_path / "inputs"
    source.mkdir()
    truth_file = source / "test.json"  # A minimal unit fixture, not external test data.
    write_json(
        truth_file,
        {
            "documents": [
                {
                    "id": "fixture",
                    "text": packet().text,
                    "spans": [[0, 5], [6, 10]],
                    "annotation_sets": [
                        {
                            "annotations": {
                                "h0": {"choice": "Entailment", "spans": [0]},
                                "h1": {"choice": "Contradiction", "spans": [1]},
                                "h2": {"choice": "NotMentioned", "spans": []},
                            }
                        }
                    ],
                }
            ]
        },
    )
    inventory = tmp_path / "inventory" / "complete-v1" / "inventory.json"
    write_json(
        inventory,
        {
            "datasets": {
                "contract-nli": {"inspection": {"splits": {"test": {"sha256": sha256(truth_file)}}}}
            }
        },
    )
    plan = tmp_path / "plan.json"
    write_json(
        plan,
        {
            "protocol": "clearledger-external-evaluation-v1",
            "inventory_sha256": sha256(inventory),
            "datasets": {
                "contract-nli": {
                    "ids": {"scored": ["fixture"]},
                    "hypothesis_ids": ["h0", "h1", "h2"],
                }
            },
        },
    )
    plan.with_suffix(".sha256").write_text(sha256(plan))
    packet_manifest = write_packets(inputs, [packet()])
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest, {"plan_sha256": sha256(plan), "packets": {"contract-nli": packet_manifest}}
    )
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text(
        output(
            ["Entailment", "Contradiction", "NotMentioned"], ["alpha", "beta", "gamma"]
        ).model_dump_json()
        + "\n"
    )
    seal = tmp_path / "seal.json"
    seal_predictions(predictions, seal, packet_manifest, sha256(plan))
    result = tmp_path / "result.json"
    command = [
        sys.executable,
        str(SCRIPTS / "external_phase1.py"),
        "score",
        "--plan",
        str(plan),
        "--source",
        str(source),
        "--manifest",
        str(manifest),
        "--inputs",
        str(inputs),
        "--predictions",
        str(predictions),
        "--seal",
        str(seal),
        "--output",
        str(result),
        "--dataset",
        "contract-nli",
        "--tier",
        "scored",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text())["accuracy"] == 1
    predictions.write_text("{}\n")
    truth_file.rename(source / "withheld-fixture.json")
    rejected = subprocess.run(command, capture_output=True, text=True, check=False)
    assert rejected.returncode != 0
    assert "PREDICTION_SEAL_MISMATCH" in rejected.stderr
    assert json.loads(result.read_text())["accuracy"] == 1
