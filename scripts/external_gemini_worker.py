"""Isolated, sequential evaluation worker; never imports any gold or application module."""

import ipaddress
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from external_eval.contracts import (  # noqa: E402
    ContractOutput,
    ContractPacket,
    DocileOutput,
    DocilePacket,
    ProviderMetadata,
)
from external_eval.gemini_http import MODEL, GeminiHTTP, ProviderError, generation_request  # noqa: E402
from external_eval.source import load_json, locate, quote_box, sha256, write_json  # noqa: E402
from pydantic import ValidationError  # noqa: E402


def usage(data: dict[str, Any]) -> dict[str, int | None]:
    raw = data.get("usageMetadata") or {}
    return {
        key: raw.get(key) if type(raw.get(key)) is int else None
        for key in (
            "promptTokenCount",
            "candidatesTokenCount",
            "thoughtsTokenCount",
            "totalTokenCount",
            "cachedContentTokenCount",
        )
    }


def parse_text(data: dict[str, Any]) -> dict[str, Any]:
    candidates = data.get("candidates") or []
    if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
        raise ValueError("SCHEMA_PARSE_FAILURE")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("SCHEMA_PARSE_FAILURE") from None
    if not isinstance(value, dict):
        raise ValueError("OUTPUT_VALIDATION_FAILURE")
    return value


class Worker:
    def __init__(self, config_path: Path, key: str) -> None:
        self.config_path = config_path.resolve()
        self.config = load_json(config_path)
        if sha256(config_path) != config_path.with_suffix(".sha256").read_text().strip():
            raise ValueError("CONFIG_HASH_MISMATCH")
        self.config_hash = sha256(config_path)
        self.root = Path(self.config["run_root"]).resolve()
        self.client = GeminiHTTP(key)
        self.last_request_ms = 0
        self.state_path = self.root / "logs" / "metadata" / "usage-ledger.json"
        self.state = (
            load_json(self.state_path)
            if self.state_path.exists()
            else {
                "generations": 0,
                "input_charged": 0,
                "output_charged": 0,
                "http_operations": 0,
                "last_http_ns": 0,
            }
        )

    def save(self) -> None:
        # Mutable accounting ledger only; immutable attempts/config/predictions are never replaced.
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state), encoding="utf8")
        os.replace(temporary, self.state_path)

    def http(self, operation: str, body: dict[str, Any]) -> dict[str, Any]:
        interval = self.config["pacing"]["http_interval_seconds"]
        elapsed = (time.monotonic_ns() - self.state["last_http_ns"]) / 1_000_000_000
        if elapsed < interval:
            time.sleep(interval - max(0, elapsed))
        self.state["last_http_ns"] = time.monotonic_ns()
        self.state["http_operations"] += 1
        self.save()
        started = time.perf_counter_ns()
        try:
            return self.client.request(operation, body)
        finally:
            self.last_request_ms = (time.perf_counter_ns() - started) // 1_000_000

    def attempt(
        self,
        phase: str,
        key: str,
        stage: str,
        payload: dict[str, Any],
        input_cap: int,
        output_cap: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        directory = self.root / "attempts" / phase / key
        result_path = directory / f"{stage}.json"
        if result_path.exists():
            stored = load_json(result_path)
            return stored.get("typed_result"), stored["metadata"]
        marker = directory / f"{stage}.started.json"
        if marker.exists():
            raise ValueError("UNKNOWN_INFLIGHT_NO_RETRY")
        if (
            self.state["generations"] >= self.config["limits"]["generations"]
            or self.state["input_charged"] + input_cap > self.config["limits"]["input_tokens"]
            or self.state["output_charged"] + output_cap > self.config["limits"]["output_tokens"]
        ):
            raise ValueError("FROZEN_BUDGET_EXHAUSTED")
        spec = self.config["request_spec"]
        body = generation_request(
            payload, spec[f"{stage}_prompt"], spec[f"{stage}_schema"], output_cap
        )
        write_json(
            marker,
            {
                "config_sha256": self.config_hash,
                "stage": stage,
                "input_reserved": input_cap,
                "output_reserved": output_cap,
            },
        )
        start = time.perf_counter_ns()
        metadata: dict[str, Any] = {
            "phase": phase,
            "source_id": key,
            "stage": stage,
            "config_sha256": self.config_hash,
            "generation_called": False,
            "status": "SUCCESS",
            "http_status": None,
            "provider_status": None,
            "usage": {k: None for k in usage({})},
            "model_version": None,
            "count_latency_ms": None,
            "provider_latency_ms": None,
        }
        value = None
        reservation = False
        try:
            count = self.http(
                "countTokens", {"generateContentRequest": {"model": f"models/{MODEL}", **body}}
            )
            metadata["count_latency_ms"] = self.last_request_ms
            total = count.get("totalTokens")
            if type(total) is not int or not 0 < total <= input_cap:
                metadata["status"] = "INPUT_TOKEN_LIMIT"
            else:
                metadata["counted_input_tokens"] = total
                # Reserve before sending; interrupted calls keep full reservation, never retry.
                self.state["generations"] += 1
                self.state["input_charged"] += input_cap
                self.state["output_charged"] += output_cap
                reservation = True
                self.save()
                metadata["generation_called"] = True
                data = self.http("generateContent", body)
                metadata.update(
                    http_status=200, usage=usage(data), model_version=data.get("modelVersion")
                )
                value = parse_text(data)
        except ProviderError as exc:
            metadata.update(
                status=exc.category,
                http_status=exc.http_status,
                provider_status=exc.provider_status,
            )
        except ValueError as exc:
            if str(exc) not in {"SCHEMA_PARSE_FAILURE", "OUTPUT_VALIDATION_FAILURE"}:
                raise
            metadata["status"] = str(exc)
        finally:
            metadata["wall_latency_ms"] = (time.perf_counter_ns() - start) // 1_000_000
            metadata["latency_ms"] = self.last_request_ms if metadata["generation_called"] else None
            metadata["provider_latency_ms"] = metadata["latency_ms"]
            observed = metadata["usage"]
            if reservation:
                prompt, combined = observed["promptTokenCount"], observed["totalTokenCount"]
                if prompt is not None and 0 <= prompt <= input_cap:
                    self.state["input_charged"] -= input_cap - prompt
                if (
                    prompt is not None
                    and combined is not None
                    and 0 <= combined - prompt <= output_cap
                ):
                    self.state["output_charged"] -= output_cap - (combined - prompt)
                self.save()
        # Typed stage validation: no output normalization/repair, no hidden reasoning persisted.
        if value is not None:
            try:
                if stage == "plan":
                    self.validate_plan(value, payload)
                elif stage == "synthesis":
                    parsed = self.contract(value, payload["document_id"], metadata)
                    expected = {h["hypothesis_id"] for h in payload["hypotheses"]}
                    actual = {a.hypothesis_id for a in parsed.answers}
                    if not actual <= expected:
                        raise ValueError("UNKNOWN_HYPOTHESIS")
                    metadata["missing_hypotheses"] = len(expected - actual)
                else:
                    self.docile(value, payload["document_id"], metadata)
            except (ValidationError, ValueError):
                metadata["status"] = "OUTPUT_VALIDATION_FAILURE"
                value = None
        write_json(result_path, {"metadata": metadata, "typed_result": value})
        return value, metadata

    @staticmethod
    def validate_plan(value: dict[str, Any], payload: dict[str, Any]) -> None:
        if set(value) != {"questions"} or not isinstance(value["questions"], list):
            raise ValueError("INVALID_PLAN")
        expected = {h["hypothesis_id"] for h in payload["hypotheses"]}
        actual = []
        for row in value["questions"]:
            if (
                not isinstance(row, dict)
                or set(row)
                != {
                    "hypothesis_id",
                    "question",
                    "support_test",
                    "contradiction_test",
                    "unresolved_test",
                }
                or not all(isinstance(v, str) and 0 < len(v) <= 4000 for v in row.values())
            ):
                raise ValueError("INVALID_PLAN")
            actual.append(row["hypothesis_id"])
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("INVALID_PLAN_IDS")

    @staticmethod
    def contract(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> ContractOutput:
        if set(value) != {"answers"}:
            raise ValueError("INVALID_OUTPUT_FIELDS")
        return ContractOutput.model_validate(
            {
                "document_id": key,
                **value,
                "metadata": {
                    "provider": "gemini-http",
                    "model": metadata.get("model_version") or MODEL,
                    "latency_ms": metadata["latency_ms"],
                },
            }
        )

    @staticmethod
    def docile(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> DocileOutput:
        if set(value) != {"invoice_references"}:
            raise ValueError("INVALID_OUTPUT_FIELDS")
        return DocileOutput.model_validate(
            {
                "document_id": key,
                **value,
                "metadata": {
                    "provider": "gemini-http",
                    "model": metadata.get("model_version") or MODEL,
                    "latency_ms": metadata["latency_ms"],
                },
            }
        )

    def phase(self, name: str) -> None:
        phase = self.config["phases"][name]
        directory = Path(phase["input_directory"])
        outputs = []
        statuses: Counter[str] = Counter()
        for index, key in enumerate(phase["ids"]):
            if key in phase.get("input_failures", {}):
                output = DocileOutput(
                    document_id=key,
                    invoice_references=[],
                    metadata=ProviderMetadata(provider="NO_MODEL_CALL", failure="PARSE"),
                )
                outputs.append(output.model_dump(mode="json"))
                statuses["ADAPTER_INPUT_FAILURE"] += 1
                continue
            path = directory / f"{key}.json"
            if sha256(path) != phase["packet_hashes"][path.name]:
                raise ValueError("SOURCE_PACKET_HASH_MISMATCH")
            if phase["dataset"] == "contract-nli":
                packet = ContractPacket.model_validate(load_json(path))
                payload = packet.model_dump(mode="json")
                plan, plan_meta = self.attempt(name, key, "plan", payload, 32768, 4096)
                if (name.startswith("preflight") or name.endswith("smoke")) and plan_meta[
                    "http_status"
                ] in {400, 401, 403, 404}:
                    raise ValueError("CRITICAL_PROVIDER_ADMISSION_FAILURE")
                payload["evidence_plan"] = plan
                result, meta = self.attempt(name, key, "synthesis", payload, 32768, 4096)
                if result is not None:
                    output_nli = self.contract(result, key, meta)
                    expected = {h.hypothesis_id for h in packet.hypotheses}
                    if any(a.hypothesis_id not in expected for a in output_nli.answers):
                        result = None
                        meta["status"] = "OUTPUT_VALIDATION_FAILURE"
                    else:
                        quotes = Counter(
                            locate(packet.text, q).status
                            for a in output_nli.answers
                            for q in a.evidence_quotes
                        )
                        if any(k != "VALID" and n for k, n in quotes.items()):
                            statuses["EVIDENCE_QUOTE_FAILURE"] += 1
                        statuses["MISSING_ANSWERS"] += len(
                            expected - {a.hypothesis_id for a in output_nli.answers}
                        )
                if result is None:
                    output_nli = ContractOutput(
                        document_id=key,
                        answers=[],
                        metadata=ProviderMetadata(
                            provider="gemini-http",
                            model=MODEL,
                            failure=(
                                "PROVIDER"
                                if meta["status"].startswith(("PROVIDER", "AUTH"))
                                else "SCHEMA"
                            ),
                            latency_ms=meta["latency_ms"],
                        ),
                    )
                outputs.append(output_nli.model_dump(mode="json"))
                statuses[f"plan:{plan_meta['status']}"] += 1
            else:
                packet_d = DocilePacket.model_validate(load_json(path))
                payload = {
                    "document_id": key,
                    "pages": [{"page": p.page, "text": p.text} for p in packet_d.pages],
                }
                result, meta = self.attempt(name, key, "extraction", payload, 8192, 1024)
                if result is not None:
                    output_doc = self.docile(result, key, meta)
                    if any(
                        quote_box(packet_d, r.quote, r.page)["status"] != "VALID"
                        for r in output_doc.invoice_references
                    ):
                        statuses["LOCALIZATION_FAILURE"] += 1
                else:
                    output_doc = DocileOutput(
                        document_id=key,
                        invoice_references=[],
                        metadata=ProviderMetadata(
                            provider="gemini-http",
                            model=MODEL,
                            failure=(
                                "PROVIDER"
                                if meta["status"].startswith(("PROVIDER", "AUTH"))
                                else "SCHEMA"
                            ),
                            latency_ms=meta["latency_ms"],
                        ),
                    )
                outputs.append(output_doc.model_dump(mode="json"))
            statuses[meta["status"]] += 1
            print(f"{name}: {index + 1}/{len(phase['ids'])} {meta['status']}", flush=True)
            if (name.startswith("preflight") or name.endswith("smoke")) and (
                meta["http_status"] in {400, 401, 403, 404}
                or (
                    phase["dataset"] == "contract-nli"
                    and plan_meta["http_status"] in {400, 401, 403, 404}
                )
            ):
                raise ValueError("CRITICAL_PROVIDER_ADMISSION_FAILURE")
        output_path = self.root / "predictions" / f"{name}.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf8") as stream:
            for row in outputs:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        write_json(
            self.root / "logs" / "metadata" / f"{name}-summary.json",
            {
                "statuses": statuses,
                "documents": len(outputs),
                "config_sha256": self.config_hash,
                "prediction_sha256": sha256(output_path),
            },
        )


def restrict(worker: Worker) -> None:
    root = worker.root
    runtime = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
    code = Path(__file__).resolve().parent
    read_roots = [root / part for part in ("inputs", "config", "attempts", "logs", "predictions")]
    write_roots = [root / part for part in ("attempts", "logs", "predictions", "preflight")]

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.spawn"}:
            raise PermissionError("WORKER_PROCESS_DENIED")
        if event == "import" and (
            str(args[0]).startswith("clearledger")
            or args[0] in {"external_eval.gold", "external_eval.scorers"}
        ):
            raise PermissionError("WORKER_IMPORT_DENIED")
        if event == "socket.getaddrinfo" and args[0] != "generativelanguage.googleapis.com":
            raise PermissionError("WORKER_HOST_DENIED")
        if event == "socket.connect":
            address = args[1]
            if address[1] != 443 or not ipaddress.ip_address(address[0]).is_global:
                raise PermissionError("WORKER_NETWORK_DENIED")
        if event == "open" and not isinstance(args[0], int):
            path = Path(args[0]).resolve()
            mode, flags = args[1], args[2]
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
            )
            allowed = write_roots if writing else read_roots + runtime
            permitted_code = (
                not writing
                and path.parent == code / "external_eval"
                and path.name in {"source.py", "contracts.py", "gemini_http.py"}
            )
            if not permitted_code and not any(path.is_relative_to(p) for p in allowed):
                raise PermissionError("WORKER_FILE_BOUNDARY")

    sys.addaudithook(audit)


def main() -> None:
    logging.disable(logging.CRITICAL)
    message = json.loads(sys.stdin.read())
    worker = Worker(Path(message["config_path"]), message.pop("key"))
    if any(
        k.startswith("clearledger") or k in {"external_eval.gold", "external_eval.scorers"}
        for k in sys.modules
    ):
        raise ValueError("WORKER_IMPORT_ISOLATION_FAILED")
    restrict(worker)
    try:
        for phase in message["phases"]:
            worker.phase(phase)
    finally:
        worker.client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never emit exception messages/tracebacks or provider response bodies.
        print(json.dumps({"worker_failure": type(exc).__name__}), flush=True)
        raise SystemExit(1) from None
