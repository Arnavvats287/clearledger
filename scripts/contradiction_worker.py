"""Isolated development-only worker for the four ContractNLI formulations."""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accuracy_worker import CURRENT, DevelopmentWorker  # noqa: E402
from external_eval.accuracy_nli import rows  # noqa: E402
from external_eval.contracts import ContractOutput  # noqa: E402
from external_eval.contradiction import project, schema  # noqa: E402
from external_eval.gemini_http import MODEL  # noqa: E402
from external_eval.source import write_json  # noqa: E402
from external_gemini_worker import restrict  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from clearledger.source_spans import digest  # noqa: E402


class ContradictionWorker(DevelopmentWorker):
    job: dict[str, Any]

    def run_job(self, job: dict[str, Any]) -> None:
        if (job["kind"], job["mode"], job["strategy"], job["k"]) != (
            "contract",
            "direct",
            "global",
            20,
        ):
            raise ValueError("REFERENCE_PATH_CHANGED")
        self.job = job
        super().run_job(job)

    def transport_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        if digest(self.current.payload) != self.job["packet_sha256"]:
            raise ValueError("REFERENCE_PACKET_CHANGED")
        name = self.job["formulation"]
        result = super().transport_spec(spec)
        result["synthesis_prompt"] = self.config["prompts"][name]
        result["synthesis_schema"] = schema(name)
        if digest(result["synthesis_schema"]) != self.config["schema_hashes"][name]:
            raise ValueError("FORMULATION_SCHEMA_CHANGED")
        return result

    @staticmethod
    def contract(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> ContractOutput:
        worker = cast(ContradictionWorker, CURRENT.get())
        name = worker.job["formulation"]
        if name in {"rubric", "few-shot"}:
            return DevelopmentWorker.contract(value, key, metadata)
        expected = {identifier for identifier, _ in worker.current.hypotheses}
        found, duplicate, _ = rows(value, expected, stage="answers")
        projected, failures = [], {}
        for identifier, row in found.items():
            if identifier in duplicate:
                continue
            try:
                projected.append(project(row, name))
            except ValidationError:
                failures[identifier] = "INVALID_FORMULATION_ITEM"
            except ValueError as error:
                failures[identifier] = str(error)
        result = DevelopmentWorker.contract({"answers": projected}, key, metadata)
        for item in worker.last["items"]:
            if item["hypothesis_id"] in failures:
                item["reason"] = failures[item["hypothesis_id"]]
        return result


def main() -> None:
    logging.disable(logging.CRITICAL)
    message = json.loads(sys.stdin.read())
    worker = ContradictionWorker(Path(message["config_path"]), message.pop("key"))
    if worker.config.get("protocol") != "contradiction-development-1" or worker.model != MODEL:
        raise ValueError("DEVELOPMENT_PROTOCOL_REQUIRED")
    if any(
        n in sys.modules
        for n in ("external_eval.gold", "external_eval.scorers", "clearledger.models")
    ):
        raise ValueError("WORKER_IMPORT_BOUNDARY")
    control = message.get("control", False)
    restrict(worker)
    try:
        model_path = worker.root / "logs/metadata/model-admission.json"
        if control and not model_path.exists():
            info = worker.client.request("model")
            if info.get("name") != f"models/{MODEL}":
                raise ValueError("MODEL_ALIAS_UNAVAILABLE")
            worker.state["http_operations"] += 1
            worker.state["last_http_ns"] = time.monotonic_ns()
            worker.save()
            write_json(model_path, {"model": MODEL, "status": "PASS"})
        for job in worker.config["controls" if control else "jobs"]:
            worker.run_job(job)
    finally:
        worker.client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"worker_failure": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
