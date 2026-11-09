"""Phase 3B isolated worker. Reuses the frozen development transport and validators."""

import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accuracy_worker import DevelopmentWorker  # noqa: E402
from external_eval.gemini_http import MODEL  # noqa: E402
from external_eval.source import load_json, write_json  # noqa: E402
from external_gemini_worker import restrict  # noqa: E402


class FinalWorker(DevelopmentWorker):
    job: dict[str, Any]

    def run_job(self, job: dict[str, Any]) -> None:
        self.job = job
        # Only the contract branch uses the selected exact-label transport schema.
        self.selection = job["kind"] == "contract"
        super().run_job(job)

    def development_attempt(
        self,
        phase: str,
        key: str,
        stage: str,
        payload: dict[str, Any],
        input_cap: int,
        output_cap: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        if stage == "extraction":
            entries = []
            for alias, item in self.invoice_lookup.items():
                source = self.invoice_sources.get(alias, self.invoice_source)
                span = source.resolve(
                    item.span_id,
                    expected_hash=source.source_hash,
                    expected_version=source.source_version,
                )
                entries.append({**asdict(span), "alias": alias, "value": item.value})
            path = self.root / "predictions/offers" / f"{key}.json"
            content = {
                "entries": entries,
                "complete": payload["complete"],
                "admission": payload["admission"],
            }
            if path.exists():
                if load_json(path) != json.loads(json.dumps(content)):
                    raise ValueError("OFFERED_CANDIDATES_CHANGED")
            else:
                write_json(path, content)
            if not entries:
                status = (
                    "ADAPTER_INPUT_FAILURE"
                    if self.job["source_unavailable"]
                    else (
                        "OUT_OF_SCOPE"
                        if payload["admission"] == "OUT_OF_SCOPE"
                        else "NO_CANDIDATES"
                    )
                )
                value = (
                    None
                    if status == "ADAPTER_INPUT_FAILURE"
                    else {
                        "document_class": "UNKNOWN",
                        "candidate_ids": [],
                    }
                )
                return value, {"status": status, "generation_called": False, "latency_ms": None}
        return self.attempt(phase, key, stage, payload, input_cap, output_cap)


def main() -> None:
    logging.disable(logging.CRITICAL)
    message = json.loads(sys.stdin.read())
    worker = FinalWorker(Path(message["config_path"]), message.pop("key"))
    if (worker.config["protocol"], worker.config["model"], worker.config["retry_policy"]) != (
        "phase3b-v1",
        MODEL,
        "NONE",
    ):
        raise ValueError("INVALID_FROZEN_RUN_CONFIGURATION")
    if any(
        n in sys.modules
        for n in ("external_eval.gold", "external_eval.scorers", "clearledger.models")
    ):
        raise ValueError("WORKER_IMPORT_BOUNDARY")
    stage = message["stage"]
    if stage not in {"controls", "jobs"}:
        raise ValueError("UNKNOWN_RUN_STAGE")
    restrict(worker)
    try:
        model_path = worker.root / "logs/metadata/model-admission.json"
        if stage == "controls" and not model_path.exists():
            result = worker.client.request("model")
            if result.get("name") != f"models/{MODEL}":
                raise ValueError("MODEL_ALIAS_UNAVAILABLE")
            worker.state["http_operations"] += 1
            worker.state["last_http_ns"] = time.monotonic_ns()
            worker.save()
            write_json(model_path, {"model": MODEL, "status": "PASS"})
        for job in worker.config[stage]:
            worker.run_job(job)
    finally:
        worker.client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"worker_failure": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
