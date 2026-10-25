"""Post-M09 API evaluation from exported visible inputs only. Never loads benchmark code/truth."""

import argparse
import json
import os
import subprocess
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from application_eval_host import ROOT, disposable_database
from application_eval_inputs import Snapshot, sha
from application_eval_runtime import run
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs", type=Path, required=True, help="Exported imports/ + app_visible/ ONLY"
    )
    parser.add_argument(
        "--as-of", required=True, help="Operator-confirmed export cutoff, not a stage schedule"
    )
    args = parser.parse_args()
    source = Snapshot(args.inputs, args.as_of)
    future = source.temporal_checks()
    if future:
        raise SystemExit("Visible CSV records exceed declared export cutoff; refusing time travel")
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
        "TEST_DATABASE_URL"
    )
    if not url:
        raise SystemExit("TEST_DATABASE_URL with disposable database privileges is required")
    output = ROOT / "local-data/application-evaluations" / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    source_root = source.root.resolve()
    if output.resolve().is_relative_to(source_root) or source_root.is_relative_to(output.resolve()):
        raise SystemExit("Inputs and outputs must be separate")
    (output / "input-inventory.json").write_text(
        json.dumps(source.files, indent=2), encoding="utf-8"
    )
    started = time.perf_counter_ns()
    tracemalloc.start()
    with disposable_database(url) as database:
        observations, summary = run(source, database, output)
    source.verify()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    summary.update(
        harness_peak_traced_bytes=peak,
        input_files=len(source.files),
        input_bytes=sum(v["bytes"] for v in source.files.values()),
        elapsed_ns=time.perf_counter_ns() - started,
        financial_csv_contract="1.0",
        application_checkpoint=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        executed_at=datetime.now(UTC).isoformat(),
        source_export_unchanged=True,
        original_stage_schedule="NOT SUPPLIED; no inferred stages or case/receipt mapping",
        full_420_receipt_426_stage_coverage="NOT EVALUABLE: single development export only",
    )
    summary["harness_sha256"] = {
        p.name: sha(p.read_bytes())
        for p in [Path(__file__), *Path(__file__).parent.glob("application_eval_*.py")]
    }
    for name, value in (
        ("observations.json", observations),
        ("summary.json", summary),
        ("snapshot-predictions.json", observations["snapshot_predictions"]),
        ("stage-predictions.json", []),
    ):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "records": summary["record_counts"],
                "stage_scoring": "NOT EVALUABLE; stage-predictions.json is deliberately empty",
            }
        )
    )


if __name__ == "__main__":
    main()
