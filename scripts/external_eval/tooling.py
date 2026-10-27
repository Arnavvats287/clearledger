"""Record isolated evaluator pins/hashes and verify prepared source-only artifacts."""

import argparse
import importlib.metadata
import platform
import subprocess
from pathlib import Path

from .source import (
    load_json,
    load_plan,
    no_links,
    read_packets,
    sha256,
    verify_source_tables,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--lock-output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.runs / "phase1-v1"
    plan = load_plan(args.runs / "evaluation-plan-v1.json")
    manifest = load_json(root / "projection-manifest.json")
    if manifest["plan_sha256"] != sha256(args.runs / "evaluation-plan-v1.json"):
        raise ValueError("MANIFEST_PLAN_MISMATCH")
    counts = {}
    for name, folder in (("contract-nli", "contractnli-v1"), ("docile", "docile-v1")):
        packets = read_packets(
            args.runs / folder / "inputs" / "adapter", manifest["packets"][name], name
        )
        if set(packets) != set(plan["datasets"][name]["ids"]["adapter"]):
            raise ValueError("SELECTION_MISMATCH")
        counts[name] = len(packets)
    inventory = load_json(args.runs / "inventory" / "complete-v1" / "inventory.json")
    if (
        sha256(args.runs / "inventory" / "complete-v1" / "inventory.json")
        != plan["inventory_sha256"]
    ):
        raise ValueError("INVENTORY_HASH_MISMATCH")
    verify_source_tables(
        args.runs / "recbench-v1" / "inputs" / "sources", manifest["packets"]["recbench-small"]
    )
    for name, checksum in manifest["packets"]["recbench-small"].items():
        path = args.runs / "recbench-v1" / "inputs" / "sources" / name
        if (
            sha256(path) != checksum
            or checksum
            != inventory["datasets"]["recbench-small"]["inspection"]["csv"][path.stem]["sha256"]
        ):
            raise ValueError("SOURCE_CSV_HASH_MISMATCH")
    counts["recbench_source_tables"] = len(manifest["packets"]["recbench-small"])
    report = load_json(root / "install-report.json")
    pins = []
    distributions = []
    for item in report["install"]:
        name, version = item["metadata"]["name"], item["metadata"]["version"]
        checksum = item["download_info"]["archive_info"]["hashes"]["sha256"]
        pins.append(f"{name}=={version} --hash=sha256:{checksum}")
        distributions.append(
            {
                "name": name,
                "version": version,
                "sha256": checksum,
                "url": item["download_info"]["url"],
            }
        )
    no_links(args.lock_output)
    args.lock_output.parent.mkdir(parents=True, exist_ok=True)
    lock_text = "# Evaluation only: Windows CPython 3.12; official DocILE, no OCR extras.\n"
    lock_text += "\n".join(sorted(pins, key=str.lower)) + "\n"
    if args.check:
        if args.lock_output.read_text(encoding="ascii") != lock_text:
            raise ValueError("EVALUATOR_LOCK_MISMATCH")
    else:
        with args.lock_output.open("x", encoding="ascii") as stream:
            stream.write(lock_text)
    native_python = root / "venv" / "Scripts" / "python.exe"
    completed = subprocess.run(
        [str(native_python), "-m", "pip", "check"], capture_output=True, timeout=60, check=False
    )
    if completed.returncode:
        raise ValueError("ISOLATED_EVALUATOR_DEPENDENCY_CHECK_FAILED")
    if args.check:
        previous = load_json(root / "tooling-metadata.json")
        if previous["source_packet_validation"] != counts or previous["lock_sha256"] != sha256(
            args.lock_output
        ):
            raise ValueError("TOOLING_METADATA_MISMATCH")
        print(
            "Existing lock, dependency health, frozen selections and all source packet hashes PASS."
        )
        return
    write_json(
        root / "tooling-metadata.json",
        {
            "plan_sha256": sha256(args.runs / "evaluation-plan-v1.json"),
            "phase0_plan_unchanged": True,
            "scored_inference_performed": False,
            "python": platform.python_version(),
            "schema_pydantic": importlib.metadata.version("pydantic"),
            "evaluator_distributions": distributions,
            "dependency_check": "PASS",
            "lock_sha256": sha256(args.lock_output),
            "install_report_sha256": sha256(root / "install-report.json"),
            "source_packet_validation": counts,
            "frozen_final_answers_accessed": False,
            "privacy_transmission": {
                "contract-nli": "DENIED_PENDING_DOCUMENT_REVIEW",
                "docile": "DENIED_PENDING_DATA_LICENSE_AND_DOCUMENT_REVIEW",
                "recbench-small": "NOT_NEEDED_NO_MODEL_TASK",
            },
            "boundary": "Distinct regular files, no symlinks; logical packet reader. Not an OS "
            "security boundary against a malicious host/account. Future transport needs approval",
        },
    )
    print("Evaluator lock, package hashes and source-only metadata saved; no model calls.")


if __name__ == "__main__":
    main()
