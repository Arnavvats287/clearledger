"""Bounded source-only development worker, reusing the existing one-shot HTTP transport."""

import json
import logging
import re
import sys
import time
from contextvars import ContextVar
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accuracy_schema_probe import TRANSIENT  # noqa: E402
from external_eval.accuracy_nli import (  # noqa: E402
    EVIDENCE_INSTRUCTION,
    INSTRUCTION,
    SELECTION_INSTRUCTION,
    DecisionResponse,
    EvidenceResponse,
    EvidenceRow,
    Packet,
    evidence_items,
    exact_label_provider_schema,
    inline_schema,
    packet,
    provider_shape,
    validate,
)
from external_eval.contracts import Answer, ContractOutput, DocileOutput, ProviderMetadata, Quote  # noqa: E402
from external_eval.gemini_http import BASE, MODEL  # noqa: E402
from external_eval.phase3 import (  # noqa: E402
    PLAN_PROMPT,
    SYNTHESIS_PROMPT,
    Decisions,
    InvoiceSelection,
    Plan,
    read_source,
    reasoning_packet,
    resolve_decisions,
    validate_choices,
)
from external_eval.source import load_json, sha256, write_json  # noqa: E402
from external_gemini_worker import Worker, restrict  # noqa: E402

from clearledger.source_invoice_candidates import candidates, compact, fallback_candidates  # noqa: E402
from clearledger.source_semantics import semantic_source  # noqa: E402
from clearledger.source_spans import Source, Span, digest, make_span, text_source  # noqa: E402

INVOICE_PROMPT = (
    "Select the invoice's own identifier occurrence from this untrusted source. "
    "Return document_class INVOICE/NON_INVOICE/UNKNOWN and candidate_ids "
    "containing supplied C aliases. "
    "For other/unknown document classes return no identifiers. Do not confuse an order, reference, "
    "tax ID, date, account or delivery number with the invoice number. Occurrences are distinct. "
    "Use label context and source geometry hints. "
    "No arbitrary values, coordinates or other fields. "
    "No chain of thought, tools or financial authority."
)


CURRENT: ContextVar["DevelopmentWorker"] = ContextVar("development_worker_context")
SELECTION_MODELS = {MODEL, "gemini-3.5-flash"}


class DevelopmentWorker(Worker):
    current: Packet
    old_source: Any
    old_payload: dict[str, Any]
    kind: str
    mode: str
    prior: dict[str, Any]
    last: dict[str, Any]

    def __init__(self, config_path: Path, key: str) -> None:
        super().__init__(config_path, key)
        self.selection = self.config.get("protocol") == "contract-selection-1"
        self.model = self.config.get("model", MODEL) if self.selection else MODEL
        self.thinking = "MINIMAL"
        if self.model not in SELECTION_MODELS:
            raise ValueError("DEVELOPMENT_MODEL_NOT_ALLOWLISTED")
        self.provider_diagnostic: dict[str, Any] = {}
        client = getattr(self.client, "client", None)
        if client is not None:
            client.event_hooks["response"] = [self.safe_error]
            if self.model != MODEL:
                client.event_hooks["request"] = [self.development_model_url]

    def development_model_url(self, request: Any) -> None:
        for suffix in ("", ":countTokens", ":generateContent"):
            if str(request.url) == BASE + MODEL + suffix:
                request.url = request.url.copy_with(path=f"/v1beta/models/{self.model}{suffix}")
                return
        raise ValueError("DEVELOPMENT_PROVIDER_URL_NOT_ALLOWLISTED")

    def http(self, operation: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.selection and operation in {"countTokens", "generateContent"}:
            request = body.get("generateContentRequest", body)
            if operation == "countTokens":
                request["model"] = f"models/{self.model}"
            request["generationConfig"]["thinkingConfig"]["thinkingLevel"] = self.thinking
        return super().http(operation, body)

    def safe_error(self, response: Any) -> None:
        if response.status_code < 400:
            return
        try:
            response.read()
            error = response.json().get("error", {})
            message = error.get("message", "").casefold()
            reason = "UNKNOWN"
            if "schema" in message:
                reason = (
                    "SCHEMA_COMPLEXITY"
                    if any(w in message for w in ("complex", "nest", "states", "too many"))
                    else "SCHEMA_REJECTED"
                )
            elif "thinking" in message:
                reason = "THINKING_CONFIGURATION"
            elif "token" in message:
                reason = "TOKEN_CONFIGURATION"
            elif "capacity" in message or "overload" in message:
                reason = "CAPACITY_UNAVAILABLE"
            fields = []
            for detail in error.get("details", []):
                for violation in detail.get("fieldViolations", []):
                    field = violation.get("field", "")
                    if re.fullmatch(
                        r"(?:generationConfig|generation_config|contents|systemInstruction|model)[A-Za-z0-9_.\[\]]{0,90}",
                        field,
                    ):
                        fields.append(field)
            self.provider_diagnostic = {
                "reason": reason,
                "http_status": response.status_code,
                "field_paths": fields[:8],
            }
        except (ValueError, TypeError, AttributeError):
            self.provider_diagnostic = {
                "reason": "UNKNOWN",
                "http_status": response.status_code,
                "field_paths": [],
            }

    def attempt(
        self,
        phase: str,
        key: str,
        stage: str,
        payload: dict[str, Any],
        input_cap: int,
        output_cap: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        prior = self.root / "attempts" / phase / key / f"{stage}.json"
        if prior.exists() and load_json(prior)["metadata"]["config_sha256"] != self.config_hash:
            raise ValueError("DEVELOPMENT_ATTEMPT_CONFIG_MISMATCH")
        self.provider_diagnostic = {}
        result = super().attempt(phase, key, stage, payload, input_cap, output_cap)
        if self.provider_diagnostic:
            path = self.root / "logs/metadata" / f"{key}-{stage}-provider-diagnostic.json"
            if not path.exists():
                write_json(path, self.provider_diagnostic)
        return result

    def development_attempt(
        self,
        phase: str,
        key: str,
        stage: str,
        payload: dict[str, Any],
        input_cap: int,
        output_cap: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        result = self.attempt(phase, key, stage, payload, input_cap, output_cap)
        if self.config.get("retry_policy") != "DEVELOPMENT_TRANSIENT_2":
            return result
        for index in range(1, 3):
            metadata = result[1]
            status = metadata["http_status"]
            if status not in TRANSIENT and not (
                status is None and metadata["status"] in {"PROVIDER_TIMEOUT", "PROVIDER_ERROR"}
            ):
                break
            retry_key = f"{key}-transient-{index}"
            if not (self.root / "attempts" / phase / retry_key / f"{stage}.json").exists():
                time.sleep(10 * 2 ** (index - 1))
            result = self.attempt(phase, retry_key, stage, payload, input_cap, output_cap)
        return result

    def transport_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not self.config.get("simple_provider_shape"):
            return spec
        return {
            key: provider_shape(value) if key.endswith("_schema") else value
            for key, value in spec.items()
        }

    def metadata(self, metadata: dict[str, Any]) -> ProviderMetadata:
        return ProviderMetadata(
            provider="gemini-development",
            model=metadata.get("model_version"),
            latency_ms=metadata.get("latency_ms"),
        )

    @staticmethod
    def validate_plan(value: dict[str, Any], payload: dict[str, Any]) -> None:
        self = CURRENT.get()
        # Semantic defects are retained per item, never discarded as a whole typed response.
        if self.mode == "legacy":
            try:
                parsed = Plan.model_validate(value)
                validate_choices(parsed.evidence, payload, self.old_source)
                if {x.hypothesis_id for x in parsed.evidence} != {
                    x["hypothesis_id"] for x in payload["hypotheses"]
                }:
                    raise ValueError("PLAN_IDS")
                self.prior = {"value": value, "valid": True}
            except ValueError:
                self.prior = {"value": None, "valid": False}
        else:
            good, errors = evidence_items(value, self.current)
            self.prior = {
                "value": {k: v.model_dump(mode="json") for k, v in good.items()},
                "errors": errors,
            }

    @staticmethod
    def contract(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> ContractOutput:
        self = CURRENT.get()
        if self.mode == "legacy":
            try:
                out, checks = resolve_decisions(
                    value, self.old_payload, self.old_source, self.metadata(metadata)
                )
                self.last = {"legacy_rejected": False, "checks": checks}
            except ValueError:
                out = ContractOutput(document_id=key, answers=[], metadata=self.metadata(metadata))
                self.last = {"legacy_rejected": True}
            return out
        good = (
            {k: EvidenceRow.model_validate(v) for k, v in self.prior.get("value", {}).items()}
            if self.mode == "plan"
            else None
        )
        items = validate(value, self.current, plan=good, require_plan=self.mode == "plan")
        self.last = {"items": [asdict(x) for x in items]}
        answers = []
        for item in items:
            spans = [
                self.current.registry.resolve(a, scope=self.current.registry.scope)
                for a in item.aliases
            ]
            answers.append(
                Answer(
                    hypothesis_id=item.hypothesis_id,
                    predicted_label=item.grounded_label,
                    evidence_quotes=[Quote(text=s.text, start=s.start, end=s.end) for s in spans],
                )
            )
        return ContractOutput(document_id=key, answers=answers, metadata=self.metadata(metadata))

    @staticmethod
    def docile(value: dict[str, Any], key: str, metadata: dict[str, Any]) -> DocileOutput:
        self = CURRENT.get()
        choice = InvoiceSelection.model_validate(value)
        refs = []
        selected = []
        invalid = 0
        if choice.document_class != "INVOICE" and choice.candidate_ids:
            raise ValueError("NON_INVOICE_EMISSION")
        seen = set()
        for name in choice.candidate_ids:
            if name not in self.invoice_lookup or name in seen:
                invalid += 1
                continue
            seen.add(name)
            item = self.invoice_lookup[name]
            source = self.invoice_sources.get(name, self.invoice_source)
            span = source.resolve(
                item.span_id,
                expected_hash=source.source_hash,
                expected_version=source.source_version,
            )
            refs.append(
                {
                    "value": item.value,
                    "quote": {"text": span.text, "start": span.start, "end": span.end},
                    "page": span.page - 1,
                }
            )
            selected.append(
                {
                    **asdict(span),
                    "value": item.value,
                    "alias": name,
                    "localization_status": "AVAILABLE" if span.bbox else "UNAVAILABLE",
                }
            )
        self.last = {
            "selected": selected,
            "invalid_aliases": invalid,
            "declared_aliases": len(choice.candidate_ids),
        }
        return DocileOutput.model_validate(
            {
                "document_id": key,
                "invoice_references": refs,
                "metadata": self.metadata(metadata).model_dump(mode="json"),
            }
        )

    def run_job(self, job: dict[str, Any]) -> None:
        CURRENT.set(self)
        destination = self.root / "predictions" / f"{job['job_id']}.json"
        if destination.exists():
            print("Existing development job retained", flush=True)
            return
        input_path = self.root / job["input"]
        if sha256(input_path) != job["input_sha256"]:
            raise ValueError("SOURCE_PACKET_CHANGED")
        raw = load_json(input_path)
        self.kind = job["kind"]
        self.mode = job["mode"]
        self.thinking = job.get("thinking", "MINIMAL") if self.selection else "MINIMAL"
        if self.selection and (
            self.kind != "contract"
            or self.mode not in {"direct", "select"}
            or self.thinking not in {"MINIMAL", "LOW"}
        ):
            raise ValueError("INVALID_SELECTION_JOB")
        self.prior = {}
        self.last = {}
        extra_calls = []
        if self.kind == "contract":
            if self.mode == "legacy":
                self.old_source, self.old_payload = reasoning_packet(raw)
                payload = self.old_payload
                spec: dict[str, Any] = {
                    "plan_prompt": PLAN_PROMPT,
                    "plan_schema": Plan.model_json_schema(),
                    "synthesis_prompt": SYNTHESIS_PROMPT,
                    "synthesis_schema": Decisions.model_json_schema(),
                }
            else:
                cat = semantic_source(text_source(raw["document_id"], [raw["text"]]))
                extras: list[Span] = []
                if job.get("context_ranges"):
                    for a, b in job["context_ranges"]:
                        extras.append(
                            make_span(cat.source, 1, a, b, len(cat.source.spans) + len(extras))
                        )
                    cat = replace(
                        cat,
                        source=replace(
                            cat.source,
                            spans=tuple(
                                {s.span_id: s for s in [*cat.source.spans, *extras]}.values()
                            ),
                        ),
                    )
                questions = [
                    h for h in raw["hypotheses"] if h["hypothesis_id"] in job["hypotheses"]
                ]
                self.current = packet(
                    cat,
                    questions,
                    request=job["job_id"],
                    strategy=job["strategy"],
                    k=job["k"],
                    extra=extras,
                )
                payload = self.current.payload
                spec = {
                    "plan_prompt": EVIDENCE_INSTRUCTION,
                    "plan_schema": EvidenceResponse.model_json_schema(),
                    "synthesis_prompt": INSTRUCTION,
                    "synthesis_schema": DecisionResponse.model_json_schema(),
                }
                # Small request-local enums reduce transcription errors without replacing
                # source/version/membership validation. Large catalogs stay post-validated.
                offered = [b.alias for b in self.current.registry.bindings]
                for schema in (spec["plan_schema"], spec["synthesis_schema"]):
                    for definition in schema.get("$defs", {}).values():
                        properties = definition.get("properties", {})
                        if "hypothesis_id" in properties:
                            properties["hypothesis_id"]["enum"] = [
                                h["hypothesis_id"] for h in questions
                            ]
                        if (
                            not job.get("omit_request_enums")
                            and 0 < len(offered) <= 128
                            and "aliases" in properties
                        ):
                            properties["aliases"]["items"]["enum"] = offered
            self.config["request_spec"] = self.transport_spec(spec)
            if self.selection:
                self.config["request_spec"]["synthesis_prompt"] = SELECTION_INSTRUCTION
                self.config["request_spec"]["synthesis_schema"] = exact_label_provider_schema()
            if job.get("inline_schema"):
                for name in ("plan_schema", "synthesis_schema"):
                    self.config["request_spec"][name] = inline_schema(
                        self.config["request_spec"][name]
                    )
            if self.mode in {"legacy", "plan", "select"}:
                if job.get("synthetic_plan_from"):
                    if not job["variant"].startswith("control"):
                        raise ValueError("SYNTHETIC_ONLY_REUSE")
                    stored = load_json(self.root / job["synthetic_plan_from"])
                    if stored["metadata"]["status"] != "SUCCESS":
                        raise ValueError("INVALID_SYNTHETIC_CONTROL")
                    plan = stored["typed_result"]
                    pm = stored["metadata"]
                    self.validate_plan(plan, payload)
                else:
                    plan, pm = self.development_attempt(
                        job["variant"], job["job_id"], "plan", payload, 32768, 4096
                    )
                if job["variant"].startswith("control") and (
                    pm["status"] != "SUCCESS" or self.prior.get("errors")
                ):
                    raise ValueError("SYNTHETIC_PLAN_ADMISSION_FAILED")
                extra_calls.append(pm)
                if self.mode == "legacy":
                    payload["evidence_plan"] = self.prior.get("value")
                elif self.mode == "plan":
                    payload = {
                        **payload,
                        "evidence_plan": list(self.prior.get("value", {}).values()),
                    }
                elif self.mode == "select":
                    chosen = {
                        a for row in self.prior.get("value", {}).values() for a in row["aliases"]
                    }
                    payload = {
                        **payload,
                        "evidence": [e for e in payload["evidence"] if e["alias"] in chosen],
                    }
                    # Actual second-request visibility is authoritative, not ranking hints.
                    self.current = replace(
                        self.current,
                        selectable={
                            h: tuple(a for a in ids if a in chosen)
                            for h, ids in self.current.selectable.items()
                        },
                    )
            value, metadata = self.development_attempt(
                job["variant"], job["job_id"], "synthesis", payload, 32768, 4096
            )
            if value is not None:
                output = self.contract(value, raw["document_id"], metadata).model_dump(mode="json")
            else:
                output = ContractOutput(
                    document_id=raw["document_id"],
                    answers=[],
                    metadata=ProviderMetadata(
                        provider="gemini-development",
                        failure="PROVIDER"
                        if metadata["status"].startswith("PROVIDER")
                        else "SCHEMA",
                    ),
                ).model_dump(mode="json")
        else:
            source = read_source(raw["canonical_source"])
            pool = candidates(source)
            if job.get("extra_candidates"):
                from clearledger.source_candidates import Candidate

                extra = []
                spans = list(pool.source.spans)
                for e in job["extra_candidates"]:
                    s = make_span(source, e["page"], e["start"], e["end"], len(spans))
                    spans.append(s)
                    extra.append(
                        Candidate("dev_" + s.span_id, s.span_id, e["value"], "SOURCE_CONTEXT")
                    )
                unique = {c.candidate_id: c for c in extra}
                if len(unique) > 64:
                    raise ValueError("ORACLE_PACKET_BOUND")
                for candidate in pool.items:
                    if len(unique) >= 64:
                        break
                    unique.setdefault(candidate.candidate_id, candidate)
                pool = replace(
                    pool,
                    source=replace(
                        pool.source, spans=tuple({s.span_id: s for s in spans}.values())
                    ),
                    items=tuple(unique.values()),
                )
                # Blind deterministic order; correct occurrence is not marked or always first.
                import hashlib

                pool = replace(
                    pool,
                    items=tuple(
                        sorted(
                            pool.items,
                            key=lambda c: hashlib.sha256(c.candidate_id.encode()).hexdigest(),
                        )
                    ),
                )
            self.invoice_sources: dict[str, Source] = {}
            fallback = (
                fallback_candidates(pool, read_source(raw["pdf_text_source"]))
                if raw.get("pdf_text_source")
                else None
            )
            fallback_count = min(8, len(fallback.items)) if fallback else 0
            primary_packet, self.invoice_lookup = compact(pool, limit=64 - fallback_count)
            payload = dict(primary_packet)
            if fallback and fallback_count:
                supplement, lookup = compact(fallback, limit=fallback_count)
                for row, item in zip(supplement["candidates"], lookup.values(), strict=True):
                    name = f"C{len(self.invoice_lookup) + 1:02}"
                    self.invoice_lookup[name] = item
                    self.invoice_sources[name] = fallback.source
                    primary_packet["candidates"].append([name, *row[1:]])
                payload["complete"] = payload["complete"] and supplement["complete"]
            payload["document_id"] = raw["document_id"]
            self.invoice_source = pool.source
            self.config["request_spec"] = {
                "extraction_prompt": INVOICE_PROMPT,
                "extraction_schema": InvoiceSelection.model_json_schema(),
            }
            if self.invoice_lookup:
                self.config["request_spec"]["extraction_schema"]["properties"]["candidate_ids"][
                    "items"
                ]["enum"] = list(self.invoice_lookup)
            self.config["request_spec"] = self.transport_spec(self.config["request_spec"])
            value, metadata = self.development_attempt(
                job["variant"], job["job_id"], "extraction", payload, 8192, 1024
            )
            output = (
                self.docile(value, raw["document_id"], metadata).model_dump(mode="json")
                if value is not None
                else DocileOutput(
                    document_id=raw["document_id"],
                    invoice_references=[],
                    metadata=ProviderMetadata(provider="gemini-development", failure="POLICY"),
                ).model_dump(mode="json")
            )
        write_json(
            destination,
            {
                "job_id": job["job_id"],
                "variant": job["variant"],
                "kind": self.kind,
                "source_id": raw["document_id"],
                "raw": value,
                "output": output,
                "diagnostics": self.last,
                "plan": self.prior,
                "metadata": metadata,
                "earlier_stages": extra_calls,
                "financial_authority": False,
                **(
                    {
                        "selection_configuration": {
                            "model": self.model,
                            "thinking": self.thinking,
                            "synthesis_packet_sha256": digest(payload),
                            "synthesis_prompt_sha256": digest(SELECTION_INSTRUCTION),
                            "synthesis_schema_sha256": digest(exact_label_provider_schema()),
                        }
                    }
                    if self.selection
                    else {}
                ),
            },
        )
        print(f"{job['variant']}: {metadata['status']}", flush=True)


def main() -> None:
    logging.disable(logging.CRITICAL)
    message = json.loads(sys.stdin.read())
    worker = DevelopmentWorker(Path(message["config_path"]), message.pop("key"))
    # Preload the pure candidate type before installing the unchanged runtime boundary.

    if any(
        k in sys.modules
        for k in ("external_eval.gold", "external_eval.scorers", "clearledger.models")
    ):
        raise ValueError("WORKER_IMPORT_BOUNDARY")
    control = message.get("control", False)
    jobs = worker.config["controls"] if control else worker.config["jobs"]
    restrict(worker)
    try:
        if control and not (worker.root / "logs/metadata/model-admission.json").exists():
            info = worker.client.request("model")
            if info.get("name") != f"models/{worker.model}":
                raise ValueError("MODEL_ALIAS_UNAVAILABLE")
            worker.state["http_operations"] += 1
            worker.state["last_http_ns"] = time.monotonic_ns()
            worker.save()
            write_json(
                worker.root / "logs/metadata/model-admission.json",
                {
                    "name": info["name"],
                    "input_limit": info.get("inputTokenLimit"),
                    "output_limit": info.get("outputTokenLimit"),
                    "status": "PASS",
                },
            )
        for job in jobs:
            worker.run_job(job)
    finally:
        worker.client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"worker_failure": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
