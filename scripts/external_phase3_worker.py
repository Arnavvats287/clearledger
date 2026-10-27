"""Source-only Phase 3 worker. Reuses one-shot accounting/transport, never v1 outputs."""

import json
import logging
import sys
import time
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from external_eval.contracts import ContractOutput, DocileOutput, ProviderMetadata  # noqa: E402
from external_eval.phase3 import (  # noqa: E402
    Plan,
    read_source,
    reasoning_packet,
    resolve_decisions,
    resolve_invoice,
    validate_choices,
)
from external_eval.source import load_json, sha256, write_json  # noqa: E402
from external_gemini_worker import Worker, restrict  # noqa: E402

from clearledger.source_candidates import Candidates, discover  # noqa: E402
from clearledger.source_spans import Source  # noqa: E402


@dataclass
class DecodeContext:
    source: Source
    payload: dict[str, Any]
    candidates: Candidates | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    spans: list[dict[str, Any]] = field(default_factory=list)
    id_counts: dict[str, dict[str, int]] = field(default_factory=dict)


CONTEXT: ContextVar[DecodeContext] = ContextVar("source_only_decode_context")


class GroundedWorker(Worker):
    def attempt(
        self,
        phase: str,
        key: str,
        stage: str,
        payload: dict[str, Any],
        input_cap: int,
        output_cap: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        previous = self.root / "attempts" / phase / key / f"{stage}.json"
        if (
            previous.exists()
            and load_json(previous)["metadata"]["config_sha256"] != self.config_hash
        ):
            raise ValueError("STALE_ATTEMPT_CONFIG")
        return super().attempt(phase, key, stage, payload, input_cap, output_cap)

    @staticmethod
    def failure(metadata: dict[str, Any]) -> Literal["SCHEMA", "POLICY", "PROVIDER"]:
        if metadata["status"] in {"SCHEMA_PARSE_FAILURE", "OUTPUT_VALIDATION_FAILURE"}:
            return "SCHEMA"
        return "POLICY" if metadata["status"] == "INPUT_TOKEN_LIMIT" else "PROVIDER"

    @staticmethod
    def count_ids(value: dict[str, Any], key: str) -> None:
        context = CONTEXT.get()
        total = invalid = 0
        if key == "extraction":
            ids = value.get("candidate_ids", [])
            allowed = (
                {c.candidate_id for c in context.candidates.items} if context.candidates else set()
            )
            if isinstance(ids, list):
                total = len(ids)
                invalid = sum(not isinstance(i, str) or i not in allowed for i in ids)
        else:
            rows = value.get("evidence" if key == "plan" else "answers", [])
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("span_ids"), list):
                        continue
                    hypothesis = row.get("hypothesis_id")
                    allowed = (
                        set(context.payload["candidate_span_ids"].get(hypothesis, []))
                        if isinstance(hypothesis, str)
                        else set()
                    )
                    total += len(row["span_ids"])
                    invalid += sum(
                        not isinstance(i, str) or i not in allowed for i in row["span_ids"]
                    )
        context.id_counts[key] = {"declared": total, "invalid": invalid}

    @staticmethod
    def metadata(metadata: dict[str, Any]) -> ProviderMetadata:
        return ProviderMetadata(
            provider="gemini-phase3",
            model=metadata.get("model_version") or "gemini-3.5-flash-lite",
            latency_ms=metadata.get("latency_ms"),
        )

    @staticmethod
    def validate_plan(value: dict[str, Any], payload: dict[str, Any]) -> None:
        GroundedWorker.count_ids(value, "plan")
        plan = Plan.model_validate(value)
        validate_choices(plan.evidence, payload, CONTEXT.get().source)
        if {r.hypothesis_id for r in plan.evidence} != {
            h["hypothesis_id"] for h in payload["hypotheses"]
        }:
            raise ValueError("INVALID_PLAN_IDS")

    @staticmethod
    def contract(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> ContractOutput:
        GroundedWorker.count_ids(value, "synthesis")
        context = CONTEXT.get()
        output, checks = resolve_decisions(
            value, context.payload, context.source, GroundedWorker.metadata(metadata)
        )
        context.checks = checks
        return output

    @staticmethod
    def docile(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> DocileOutput:
        GroundedWorker.count_ids(value, "extraction")
        context = CONTEXT.get()
        if context.candidates is None:
            raise ValueError("NO_SOURCE_CANDIDATES")
        output, spans = resolve_invoice(
            value, context.candidates, key, GroundedWorker.metadata(metadata)
        )
        context.spans = spans
        return output

    def phase(self, name: str) -> None:
        phase = self.config["phases"][name]
        outputs = []
        diagnostics = []
        for position, identifier in enumerate(phase["ids"], 1):
            path = Path(phase["input_directory"]) / f"{identifier}.json"
            if sha256(path) != phase["packet_hashes"][path.name]:
                raise ValueError("PACKET_CHANGED")
            packet = load_json(path)
            metadata: dict[str, Any] = {
                "latency_ms": None,
                "model_version": None,
                "status": "SUCCESS",
            }
            output: ContractOutput | DocileOutput
            if phase["dataset"] == "contract-nli":
                self.source, self.payload = reasoning_packet(packet)
                context = DecodeContext(self.source, self.payload)
                CONTEXT.set(context)
                plan, pm = self.attempt(name, identifier, "plan", self.payload, 32768, 4096)
                if name.startswith("preflight") and pm["status"] != "SUCCESS":
                    raise ValueError("SYNTHETIC_PLAN_ADMISSION_FAILED")
                self.payload["evidence_plan"] = plan
                value, metadata = self.attempt(
                    name, identifier, "synthesis", self.payload, 32768, 4096
                )
                if value is not None:
                    output = self.contract(value, identifier, metadata)
                    diagnostic = context.checks
                else:
                    output = ContractOutput(
                        document_id=identifier,
                        answers=[],
                        metadata=ProviderMetadata(
                            provider="gemini-phase3",
                            failure=self.failure(metadata),
                        ),
                    )
                    diagnostic = {"status": metadata["status"]}
                diagnostic["plan_status"] = pm["status"]
            else:
                self.source = read_source(packet["canonical_source"])
                self.candidates = discover(self.source, limit=64)
                context = DecodeContext(self.source, {}, self.candidates)
                CONTEXT.set(context)
                diagnostic = {
                    "admission": self.candidates.admission,
                    "fallbacks": packet["canonical_source"]["fallbacks"],
                }
                if not self.source.spans:
                    output = DocileOutput(
                        document_id=identifier,
                        invoice_references=[],
                        metadata=ProviderMetadata(provider="NO_MODEL_CALL", failure="PARSE"),
                    )
                    diagnostic["status"] = "ADAPTER_INPUT_FAILURE"
                elif not self.candidates.items:
                    output = DocileOutput(
                        document_id=identifier,
                        invoice_references=[],
                        metadata=ProviderMetadata(provider="DETERMINISTIC_ADMISSION"),
                    )
                    diagnostic.update(status="ABSTENTION", selected_spans=[])
                else:
                    payload = {
                        "document_id": identifier,
                        "source_hash": self.source.source_hash,
                        "admission": self.candidates.admission,
                        "document_head": self.source.pages[0].text[:1800]
                        if self.source.pages
                        else "",
                        "candidate_search_complete": self.candidates.complete,
                        "candidates": [
                            {
                                **asdict(c),
                                "page": s.page,
                                "bbox": s.bbox,
                                "context": next(
                                    (
                                        line.text
                                        for line in self.source.spans
                                        if line.page == s.page and line.start <= s.start < line.end
                                    ),
                                    "",
                                )[:160],
                            }
                            for c in self.candidates.items
                            for s in [
                                self.candidates.source.resolve(
                                    c.span_id,
                                    expected_hash=self.source.source_hash,
                                    expected_version=self.source.source_version,
                                )
                            ]
                        ],
                    }
                    value, metadata = self.attempt(
                        name, identifier, "extraction", payload, 8192, 1024
                    )
                    if value is not None:
                        output = self.docile(value, identifier, metadata)
                        diagnostic.update(status="SUCCESS", selected_spans=context.spans)
                    else:
                        output = DocileOutput(
                            document_id=identifier,
                            invoice_references=[],
                            metadata=ProviderMetadata(
                                provider="gemini-phase3",
                                failure=self.failure(metadata),
                            ),
                        )
                        diagnostic.update(status=metadata["status"], selected_spans=[])
            outputs.append(output.model_dump(mode="json"))
            diagnostic["model_id_counts"] = context.id_counts
            diagnostics.append({"document_id": identifier, **diagnostic})
            print(f"{name}: {position}/{len(phase['ids'])} {metadata['status']}", flush=True)
            if name.startswith("preflight") and metadata.get("http_status") in {400, 401, 403, 404}:
                raise ValueError("SYNTHETIC_ADMISSION_FAILED")
        with (self.root / "predictions" / f"{name}.jsonl").open("x", encoding="utf8") as stream:
            for row in outputs:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        write_json(self.root / "logs/metadata" / f"{name}-grounding.json", diagnostics)


def main() -> None:
    logging.disable(logging.CRITICAL)
    message = json.loads(sys.stdin.read())
    worker = GroundedWorker(Path(message["config_path"]), message.pop("key"))
    if any(
        m.startswith(
            (
                "clearledger.models",
                "clearledger.investigation",
                "external_eval.gold",
                "external_eval.scorers",
            )
        )
        for m in sys.modules
    ):
        raise ValueError("WORKER_IMPORT_ISOLATION_FAILED")
    restrict(worker)
    try:
        if message["phases"] and message["phases"][0].startswith("preflight"):
            model_path = worker.root / "logs/metadata/model-preflight.json"
            if not model_path.exists():
                write_json(
                    worker.root / "logs/metadata/model-preflight.started.json",
                    {"operation": "MODEL_LOOKUP"},
                )
                info = worker.client.request("model")
                if info.get("name") != "models/gemini-3.5-flash-lite":
                    raise ValueError("MODEL_ID_MISMATCH")
                write_json(
                    model_path,
                    {
                        "status": "PASS",
                        "model": info["name"],
                        "input_limit": info.get("inputTokenLimit"),
                        "output_limit": info.get("outputTokenLimit"),
                        "quota_tier": (
                            "Operator-confirmed Free; model lookup does not expose account quotas"
                        ),
                    },
                )
                worker.state["http_operations"] += 1
                worker.state["last_http_ns"] = time.monotonic_ns()
                worker.save()
        for phase in message["phases"]:
            worker.phase(phase)
    finally:
        worker.client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"worker_failure": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
