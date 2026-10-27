"""Small isolated fixtures; no external dataset, application, database or model access."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import external_inventory as inventory  # noqa: E402
from freeze_external_plan import build_plan, workload  # noqa: E402


def test_selection_is_order_invariant_and_disjoint():
    ids = [f"fixture-{i}" for i in range(30)]
    selected = inventory.select_ids(ids, "adapter", 8)
    assert selected == inventory.select_ids(list(reversed(ids)), "adapter", 8)
    remaining = sorted(set(ids) - set(selected))
    assert not set(selected) & set(inventory.select_ids(remaining, "scored", 8))


@pytest.mark.parametrize("ids,count", [(["same", "same"], 1), (["one"], -1)])
def test_invalid_selection_rejected(ids, count):
    with pytest.raises(ValueError):
        inventory.select_ids(ids, "fixture", count)


def test_shape_contains_no_gold_values():
    result = inventory.shape({"annotations": [{"choice": "SECRET", "spans": [9]}]})
    assert "SECRET" not in json.dumps(result)
    assert "9" not in json.dumps(result)


def test_inventory_only_explicit_root(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "README.md").write_text("local fixture")
    (tmp_path / "not-authorized.txt").write_text("must not be inventoried")
    result = inventory.inventory(public, tmp_path)
    assert result["file_count"] == 1
    assert result["metadata_files"][0]["sha256"] == inventory.digest(public / "README.md")
    assert "not-authorized" not in (tmp_path / "public-files.jsonl").read_text()


def test_resume_never_overwrites_inventory(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "sentinel"
    marker.write_text("preserve")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "external_inventory.py"),
            "--source-root",
            str(tmp_path / "source"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "REFUSE_TO_OVERWRITE" in result.stderr
    assert marker.read_text() == "preserve"


def test_missing_minor_units_are_not_zero_or_float(tmp_path):
    (tmp_path / "csv").mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"row_counts": {"settlement_lines": 2}, "generator_version": "fixture"})
    )
    (tmp_path / "csv" / "settlement_lines.csv").write_text(
        "line_id,gross_amount_minor,net_amount_minor\na,,5\nb,1.5,-2\n"
    )
    result = inventory.recbench(tmp_path)["csv"]["settlement_lines"]["counts"]
    assert result["missing:gross_amount_minor"] == 1
    assert result["invalid_integer:gross_amount_minor"] == 1
    assert result["negative:net_amount_minor"] == 1
    assert result["zero:gross_amount_minor"] == 0


def fixture_inventory():
    def ids(prefix, count):
        return [f"{prefix}-{n}" for n in range(count)]

    return {
        "datasets": {
            "docile": {
                "inspection": {
                    "selected_ids": {"adapter": ids("train", 8), "scored": ids("val", 50)}
                }
            },
            "contract-nli": {
                "inspection": {
                    "splits": {
                        name: {
                            "selected_document_ids": ids(name, count),
                            "selected_hypothesis_ids": ids("hypothesis", 17),
                            "selected_text_characters": 100,
                        }
                        for name, count in (("dev", 3), ("test", 12))
                    }
                }
            },
            "recbench-small": {
                "inspection": {
                    "csv": {
                        "bank_statements": {
                            "selected_ids": {
                                "adapter": ids("bank-adapter", 16),
                                "scored": ids("bank-scored", 128),
                            }
                        }
                    }
                }
            },
        }
    }


def test_plan_gold_is_hidden_and_no_inference_authorized():
    plan = build_plan(fixture_inventory(), {}, "a" * 64)
    assert plan["inference_performed"] is False
    assert plan["external_calls_authorized"] is False
    assert plan["common"]["scorer_command"] is None
    assert "annotation_sets" in plan["datasets"]["contract-nli"]["hidden"]
    assert "truth_*" in plan["datasets"]["recbench-small"]["hidden"]
    assert plan["datasets"]["docile"]["workload"]["maximum_generation_attempts"] == 58
    assert workload(30, 32768, 4096)["input_token_reservation"] == 983040


def test_plan_rejects_overlapping_partitions():
    data = fixture_inventory()
    data["datasets"]["docile"]["inspection"]["selected_ids"]["scored"][0] = "train-0"
    with pytest.raises(ValueError, match="SAMPLE_OVERLAP"):
        build_plan(data, {}, "a" * 64)


def test_helpers_have_no_model_or_application_dependency():
    for name in ("external_inventory", "external_recbench_structure", "freeze_external_plan"):
        spec = importlib.util.find_spec(name)
        assert spec is not None
        source = Path(spec.origin).read_text()
        assert "from clearledger" not in source
        assert "google.genai" not in source


def test_linked_root_refused_before_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "public")
    with pytest.raises(ValueError, match="LINKED_ROOT_REFUSED"):
        list(inventory.files(tmp_path / "public"))


def test_output_inside_dataset_refused(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "external_inventory.py"),
            "--source-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "output"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "OUTPUT_MUST_BE_OUTSIDE_DATASETS" in result.stderr
    assert not (tmp_path / "output").exists()


def test_frozen_plan_exclusive_creation_check_and_tamper_detection(tmp_path):
    source = tmp_path / "inventory.json"
    structure = tmp_path / "structure.json"
    output = tmp_path / "plan.json"
    source.write_text(json.dumps(fixture_inventory()))
    structure.write_text("{}")
    command = [
        sys.executable,
        str(SCRIPTS / "freeze_external_plan.py"),
        "--inventory",
        str(source),
        "--structure",
        str(structure),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
    assert output.read_bytes() == original
    assert subprocess.run(command + ["--check"], capture_output=True, check=False).returncode == 0
    output.write_text(output.read_text() + " ")
    checked = subprocess.run(command + ["--check"], capture_output=True, text=True, check=False)
    assert checked.returncode != 0
    assert "PLAN_DIGEST_MISMATCH" in checked.stderr


def test_graph_inspection_reports_unresolved_group_keys_without_fabricating_sources(
    tmp_path, monkeypatch
):
    import external_recbench_structure as structure

    (tmp_path / "manifest.json").write_text("{}")
    fixture = {
        "ledger": [{"txn_id": "transaction-fixture"}],
        "settlement_lines": [
            {"line_id": "line-fixture", "payout_id": "payout-fixture", "net_amount_minor": "3"}
        ],
        "payouts": [{"payout_id": "payout-fixture", "amount_minor": "3"}],
        "bank_statements": [{"stmt_line_id": "bank-fixture"}],
        "truth_ledger_processor": [{"txn_id": "transaction-fixture", "line_id": "line-fixture"}],
        "truth_line_payout": [{"line_id": "line-fixture", "payout_id": "unresolved-group"}],
        "truth_payout_bank": [{"payout_id": "unresolved-group", "stmt_line_id": "bank-fixture"}],
    }
    monkeypatch.setattr(structure, "rows", lambda root, name: iter(fixture[name]))
    result = structure.inspect(tmp_path)
    assert result["truth_ledger_processor"]["edges_missing_left_source"] == 0
    assert result["truth_line_payout"]["edges_missing_right_source"] == 1
    assert result["truth_payout_bank"]["edges_missing_left_source"] == 1
    assert (
        result["source_only_direct_links"]["payouts_with_all_linked_net_sum_different_from_amount"]
        == 0
    )
    assert "unresolved-group" not in json.dumps(result)
