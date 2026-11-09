"""Prepare/run authorized development ablations only; no held-out selection or scorer."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from accuracy_development import overlap_box
from external_eval.accuracy_nli import (
    EVIDENCE_INSTRUCTION,
    INSTRUCTION,
    DecisionResponse,
    EvidenceResponse,
)
from external_eval.phase3 import read_source
from external_eval.source import load_json, sha256, write_json
from external_phase2 import key

from clearledger.source_spans import make_span

ROOT = Path(__file__).resolve().parents[1]


def jobs(runs: Path) -> None:
    root = runs / "accuracy-development-v2"
    manifest = load_json(root / "development-manifest.json")
    all_jobs = []

    def add(
        variant: str,
        source: Path,
        mode: str,
        *,
        hypotheses: list[str] | None = None,
        strategy: str = "global",
        extra: dict[str, Any] | None = None,
    ) -> None:
        job_id = f"{variant}-{source.stem}"
        job = {
            "job_id": job_id,
            "variant": variant,
            "kind": "contract" if hypotheses is not None else "invoice",
            "input": str(source.relative_to(root)),
            "input_sha256": sha256(source),
            "mode": mode,
            "hypotheses": hypotheses,
            "strategy": strategy,
            "k": 20,
        }
        all_jobs.append({**job, **(extra or {})})

    for identifier in manifest["contract_dev_ids"]:
        src = root / f"inputs/contract/dev-{identifier}.json"
        data = load_json(src)
        hs = [x["hypothesis_id"] for x in data["hypotheses"]]
        for strategy in ("local", "global", "hybrid"):
            add("nli-" + strategy, src, "direct", hypotheses=hs, strategy=strategy)
        add("nli-legacy", src, "legacy", hypotheses=hs)
        add("nli-plan", src, "plan", hypotheses=hs)
        add("nli-select", src, "select", hypotheses=hs)
        for i in range(0, len(hs), 5):
            add(f"nli-batch5-{i // 5}", src, "direct", hypotheses=hs[i : i + 5])
        # Paired, source-independent small reference path; no class-balanced gold selection.
        small = sorted(hs, key=lambda h: hashlib.sha256(("single|" + h).encode()).hexdigest())[:2]
        for h in small:
            add("nli-single-" + h, src, "direct", hypotheses=[h])
        oracle = load_json(root / f"inputs/oracle/dev-{identifier}.json")
        add(
            "nli-oracle",
            src,
            "direct",
            hypotheses=hs,
            extra={"context_ranges": oracle["source_ranges"]},
        )
    oracle_info = []
    for identifier in manifest["docile_live_ids"]:
        src = root / f"inputs/invoice/{identifier}.json"
        raw = load_json(src)
        source = read_source(raw["canonical_source"])
        add("invoice-normal", src, "direct")
        gold = load_json(root / f"scorer-only/invoice/{identifier}.json")
        if not gold["is_invoice"]:
            continue
        extra = []
        eligible = 0
        for field in gold["fields"]:
            # Oracle can choose an actual source occurrence; it cannot invent OCR or boxes.
            found = []
            for page in source.pages:
                start = 0
                while field["text"] and (pos := page.text.find(field["text"], start)) >= 0:
                    s = make_span(
                        source,
                        page.number,
                        pos + page.offset,
                        pos + page.offset + len(field["text"]),
                        0,
                    )
                    if (
                        s.bbox is not None
                        and s.page == field["page"] + 1
                        and overlap_box(s.bbox, field["bbox"]) >= 0.5
                    ):
                        found.append(s)
                    start = pos + 1
            if found:
                s = sorted(found, key=lambda x: (x.page, x.start, x.end))[0]
                extra.append({"page": s.page, "start": s.start, "end": s.end, "value": s.text})
                eligible += 1
        oracle_info.append(
            {
                "document_id": identifier,
                "gold_instances": len(gold["fields"]),
                "source_constructible_instances": eligible,
            }
        )
        if extra:
            add("invoice-oracle", src, "direct", extra={"extra_candidates": extra})
    for folder in ("config", "attempts", "logs/metadata", "predictions"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    write_json(root / "scorer-only/oracle-availability.json", oracle_info)
    files = [
        ROOT / "scripts/accuracy_worker.py",
        Path(__file__),
        ROOT / "scripts/external_eval/accuracy_nli.py",
        ROOT / "scripts/external_eval/phase3.py",
        ROOT / "scripts/external_gemini_worker.py",
        ROOT / "scripts/external_eval/gemini_http.py",
        *[
            ROOT / f"src/clearledger/{n}.py"
            for n in ("source_spans", "source_candidates", "source_ocr", "source_retrieval")
        ],
        *[
            ROOT / f"src/clearledger/{name}.py"
            for name in ("source_aliases", "source_semantics", "source_invoice_candidates")
        ],
    ]
    config: dict[str, Any] = {
        "run_root": str(root),
        "protocol": "development-ablation-1",
        "model": "gemini-3.5-flash-lite",
        "pacing": {"http_interval_seconds": 10},
        "limits": {"generations": 100, "input_tokens": 4_000_000, "output_tokens": 500_000},
        "retry_policy": "NONE",
        "thinking": "MINIMAL",
        "account_tier": "requires current operator confirmation",
        "request_spec": {},
        "jobs": all_jobs,
        "code_hashes": {str(f): sha256(f) for f in files},
        "nli_prompts": {"synthesis": INSTRUCTION, "selection": EVIDENCE_INSTRUCTION},
        "schemas": {
            "synthesis": DecisionResponse.model_json_schema(),
            "selection": EvidenceResponse.model_json_schema(),
        },
        "versions": {n: importlib.metadata.version(n) for n in ("pydantic", "httpx")},
        "estimated_generations": sum(
            2 if j["mode"] in {"legacy", "plan", "select"} else 1 for j in all_jobs
        ),
    }
    control = root / "inputs/control/legal.json"
    write_json(
        control,
        {
            "document_id": "synthetic-legal",
            "text": "Archival copies may be retained.",
            "hypotheses": [{"hypothesis_id": "H01", "text": "Archival copies may be retained."}],
        },
    )
    invoice_control = root / "inputs/control/invoice.json"
    write_json(
        invoice_control,
        load_json(runs / "phase3-v1/inputs/preflight_docile/synthetic-invoice.json"),
    )
    config["controls"] = [
        {
            "job_id": "control-legal",
            "variant": "control-legal",
            "kind": "contract",
            "mode": "plan",
            "strategy": "global",
            "k": 5,
            "input": str(control.relative_to(root)),
            "input_sha256": sha256(control),
            "hypotheses": ["H01"],
        },
        {
            "job_id": "control-invoice",
            "variant": "control-invoice",
            "kind": "invoice",
            "mode": "direct",
            "input": str(invoice_control.relative_to(root)),
            "input_sha256": sha256(invoice_control),
        },
    ]
    config["operator_quota"] = {
        "tier": "Free",
        "rpm": 15,
        "input_tpm": 250000,
        "rpd": 500,
        "displayed_peak_28_days": {"rpm": 4, "input_tpm": 57530, "rpd": 230},
        "exact_remaining_daily_allowance": "UNKNOWN",
    }
    path = root / "config/campaign.json"
    write_json(path, config)
    path.with_suffix(".sha256").write_text(sha256(path) + "\n", encoding="ascii")
    print(
        "Development-only matrix prepared:",
        len(all_jobs),
        "jobs, at most",
        config["estimated_generations"],
        "generations",
    )


def run(
    runs: Path,
    *,
    control: bool = False,
    configuration: str | None = None,
    development_root: Path | None = None,
) -> None:
    root = development_root or runs / "accuracy-development-v2"
    path = root / "config/campaign.json"
    reviewed = root / "config/campaign-reviewed.json"
    if reviewed.exists():
        path = reviewed
    if configuration is not None:
        if Path(configuration).name != configuration or not configuration.endswith(".json"):
            raise ValueError("CONFIG_FILENAME_ONLY")
        path = root / "config" / configuration
    c = load_json(path)
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("CONFIG_CHANGED")
    admission = root / "config/current-provider-admission.json"
    if not control and not admission.exists():
        raise ValueError("CURRENT_PROVIDER_ADMISSION_REQUIRED")
    if not control:
        accepted = load_json(admission)
        if accepted["status"] != "PASS" or accepted["config_sha256"] != sha256(path):
            raise ValueError("STALE_PROVIDER_ADMISSION")
    for f, h in c["code_hashes"].items():
        if sha256(Path(f)) != h:
            raise ValueError("CODE_CHANGED")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "scripts/accuracy_worker.py")],
        input=json.dumps({"config_path": str(path), "key": key(), "control": control}),
        text=True,
        encoding="utf8",
        env=env,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ValueError("DEVELOPMENT_WORKER_FAILED_NO_RETRY")
    if control:
        for j in c["controls"]:
            out = load_json(root / "predictions" / f"{j['job_id']}.json")
            if out["metadata"]["status"] != "SUCCESS":
                raise ValueError("SYNTHETIC_SCHEMA_ADMISSION_FAILED")
            if j["kind"] == "contract" and any(
                i["status"].startswith("INVALID") or i["status"] == "MODEL_OUTPUT_FAILURE"
                for i in out["diagnostics"].get("items", [])
            ):
                raise ValueError("SYNTHETIC_ALIAS_ADMISSION_FAILED")
        write_json(
            admission,
            {
                "status": "PASS",
                "model": c["model"],
                "config_sha256": sha256(path),
                "operator_quota": c["operator_quota"],
                "retry_policy": c["retry_policy"],
                "billing_changes": False,
            },
        )
        print("Synthetic model/auth/schema/alias admission PASS; no dataset generation yet")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "preflight", "run"])
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--configuration")
    args = p.parse_args()
    if args.action == "prepare":
        jobs(args.runs)
    else:
        run(args.runs, control=args.action == "preflight", configuration=args.configuration)
