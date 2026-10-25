"""Reproduce 04C with private outputs and disposable PostgreSQL; never generate data."""

import argparse
import json
import os
import subprocess
import sys
import tracemalloc
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from pilot_package import (
    compare_successor,
    copy_visible,
    digest,
    portable_validator_source,
    unpack,
    verify_unchanged,
)
from pilot_runtime import ROOT, disposable_database, run_split

# Reviewed read-only validator in the supplied independent package. A different
# executable requires review; manifest integrity alone does not authorize code.
REVIEWED_VALIDATOR = "46f805827e8d08bb52606d9391023a4d69c63dfcaf7256abd20bd7f6aea901b1"
REVIEWED_COMPAT_VALIDATOR = "f171ad383ddf67334f57e883e030dcf0cc8c1a5507b25acef43438c54e9256e3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=ROOT / "local-data/pilot/clearledger_pilot_v1.zip"
    )
    args = parser.parse_args()
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
        "TEST_DATABASE_URL"
    )
    if not url:
        raise SystemExit("TEST_DATABASE_URL with CREATEDB is required")
    output = ROOT / "local-data/pilot-runs" / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    tracemalloc.start()
    package, integrity = unpack(args.archive, output / "evaluator")
    validator = package / "validation/validate.py"
    if digest(validator.read_bytes()) != REVIEWED_VALIDATOR:
        raise SystemExit("Unreviewed package validator; refusing executable input")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(validator), "--root", str(package)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    (output / "validator.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit(f"Independent validator FAILED; inspect {output}")
    validator_result = json.loads(result.stdout)
    assert validator_result["status"] == "PASS"
    compat_result = None
    if integrity["archive_root"] == "clearledger_pilot_v1_1":
        compat_validator = package / "validation/validate_compat.py"
        if digest(compat_validator.read_bytes()) != REVIEWED_COMPAT_VALIDATOR:
            raise SystemExit("Unreviewed compatibility validator")
        checked = subprocess.run(
            [sys.executable, "-I", "-B", str(compat_validator), "--root", str(package)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        (output / "compat-validator.log").write_text(
            checked.stdout + checked.stderr, encoding="utf-8"
        )
        adapted = False
        if (
            checked.returncode
            and os.name == "nt"
            and "manifest digest/coverage mismatch" in checked.stderr
        ):
            manifest = json.loads((package / "MANIFEST.json").read_text("utf-8"))
            disk = {
                p.relative_to(package).as_posix(): {
                    "bytes": p.stat().st_size,
                    "sha256": digest(p.read_bytes()),
                }
                for p in package.rglob("*")
                if p.is_file() and p.name != "MANIFEST.json"
            }
            assert disk == manifest["all_other_files"], "Actual disk integrity failure"
            adapter = output / "compat-validator-windows-path-adapter.py"
            with adapter.open("x", encoding="utf-8") as stream:
                stream.write(portable_validator_source(compat_validator.read_text("utf-8")))
            checked = subprocess.run(
                [sys.executable, "-I", "-B", str(adapter), "--root", str(package)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            (output / "compat-validator-portable.log").write_text(
                checked.stdout + checked.stderr, encoding="utf-8"
            )
            adapted = True
        if checked.returncode:
            raise SystemExit(f"Compatibility validator FAILED; inspect {output}")
        compat_result = json.loads(checked.stdout)
        compat_result["native_status"] = "FAILED_WINDOWS_PATH_SEPARATOR" if adapted else "PASS"
        compat_result["path_normalization_adapter"] = adapted
        assert compat_result["status"] == "PASS"
    observations = {}
    for split in ("dev", "eval"):
        visible = copy_visible(package, split, output / "application-inputs" / split)
        with disposable_database(url) as database:
            observations[split] = run_split(
                visible,
                database,
                output / "application-output" / split,
                include_compat=compat_result is not None,
            )
        print(
            f"{split}: application integration completed; disposable database removed", flush=True
        )
    # All API processes/connections have closed and disposable databases are gone.
    # Only now import the answer reader. No scoring object is passed to runtime.
    from pilot_score import evaluate

    summary, details = evaluate(package, observations)
    if compat_result is not None:
        from pilot_compat_score import evaluate_compat

        compatibility, compat_details = evaluate_compat(package, observations)
        summary["compatibility"] = compatibility
        details["compatibility"] = compat_details
        summary["safety_blockers"].extend(compatibility["safety_blockers"])
        summary["predecessor_comparison"] = compare_successor(
            ROOT / "local-data/pilot/clearledger_pilot_v1.zip", args.archive
        )
    summary["package"] = integrity
    summary["validator"] = validator_result
    if compat_result is not None:
        summary["compatibility_validator"] = compat_result
    summary["evaluator_python_peak_traced_bytes"] = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert verify_unchanged(package, args.archive), "Package copy was modified"
    assert digest(args.archive.read_bytes()) == integrity["zip_sha256"]
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "evaluator/details.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    if summary["safety_blockers"]:
        raise SystemExit(f"Pilot safety blockers found; inspect private results in {output}")
    print(f"Pilot integration and safety checks PASS. Private outputs: {output}", flush=True)


if __name__ == "__main__":
    main()
