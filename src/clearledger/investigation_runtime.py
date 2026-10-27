"""Privileged workflow host. Transactions never span model or evidence calls."""

from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError, CaseState, case_transition
from clearledger.case_events import publish
from clearledger.case_lifecycle import revise
from clearledger.case_models import DomainEvent, EventConsumption, OutboxDelivery, OutboxEvent
from clearledger.case_repository import root, scoped
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.investigation_contract import Limits
from clearledger.investigation_models import (
    Investigation,
    InvestigationFinding,
    InvestigationOperation,
    InvestigationResult,
    InvestigationTrace,
)
from clearledger.investigation_service import current
from clearledger.matching import digest, lock_company, owned


class Runtime:
    def __init__(self, engine, org, run_id, outbox_id, token, settings):
        self.engine, self.org, self.run_id = engine, org, run_id
        self.outbox_id, self.token, self.settings = outbox_id, token, settings
        with Session(engine) as session:
            run = owned(session, Investigation, org, run_id)
            self.snapshot, self.case_id = run.snapshot, run.case_id
        self.limits = Limits.model_validate(self.snapshot["limits"])

    @contextmanager
    def transaction(self):
        with Session(self.engine) as session, session.begin():
            session.info["source_correlation_settings"] = self.settings
            session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
            session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
            lock_company(session, self.org)
            row = session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.organization_id == self.org, OutboxEvent.id == self.outbox_id)
                .with_for_update()
            )
            now = session.scalar(text("SELECT clock_timestamp()"))
            if (
                row is None
                or row.status != "LEASED"
                or row.lease_token != self.token
                or row.lease_until <= now
            ):
                raise CaseError("INVESTIGATION_LEASE_LOST")
            lease_seconds = max(
                self.settings.case_outbox_lease_seconds,
                (self.settings.llm_timeout_ms + 999) // 1000 + 5,
            )
            row.lease_until = now + timedelta(seconds=lease_seconds)
            row.version += 1
            run = owned(session, Investigation, self.org, self.run_id)
            event = owned(session, DomainEvent, self.org, row.event_id)
            if (
                event.event_type != "investigation.requested"
                or event.case_id != run.case_id
                or event.payload.get("run_id") != str(run.id)
            ):
                raise CaseError("INVESTIGATION_LEASE_SCOPE", 403)
            yield session, run, row

    def guard(self, session, run):
        if not current(session, self.org, run, self.settings):
            raise CaseError("STALE_INPUTS")
        now = session.scalar(text("SELECT clock_timestamp()"))
        if run.deadline_at and run.deadline_at <= now:
            raise CaseError("TIMEOUT")

    def begin(self):
        with self.transaction() as (session, run, row):
            if run.status == "QUEUED":
                run.status = "RUNNING"
                run.started_at = session.scalar(text("SELECT clock_timestamp()"))
                run.deadline_at = run.started_at + timedelta(milliseconds=self.limits.timeout_ms)
                run.version += 1

    def operation(
        self, key, kind, function, input_tokens=0, output_tokens=0, cost=0, metadata=None
    ):
        with self.transaction() as (session, run, row):
            self.guard(session, run)
            cached = scoped(
                session, InvestigationResult, self.org, run_id=run.id, operation_key=key
            )
            if cached:
                if "error" in cached.value:
                    raise CaseError(cached.value["error"])
                return cached.value["result"]
            if scoped(session, InvestigationOperation, self.org, run_id=run.id, operation_key=key):
                raise CaseError("INTERRUPTED_OPERATION")
            if kind == "TOOL" and run.tool_calls >= self.limits.max_tool_calls:
                raise CaseError("TOOL_LIMIT")
            if (
                run.reserved_input_tokens + input_tokens > self.limits.max_input_tokens
                or run.reserved_output_tokens + output_tokens > self.limits.max_output_tokens
            ):
                raise CaseError("TOKEN_LIMIT")
            if run.reserved_cost_paise + cost > self.limits.max_spend_paise:
                raise CaseError("SPEND_LIMIT")
            run.tool_calls += int(kind == "TOOL")
            run.provider_attempts += int(kind == "PROVIDER")
            run.reserved_input_tokens += input_tokens
            run.reserved_output_tokens += output_tokens
            run.reserved_cost_paise += cost
            run.version += 1
            session.add(
                InvestigationOperation(
                    organization_id=self.org,
                    run_id=run.id,
                    operation_key=key,
                    kind=kind,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_paise=cost,
                )
            )
        try:
            result = function()
            value = {"result": result}
        except Exception as error:
            from clearledger.extraction_provider import ProviderRunError

            code = (
                error.code
                if isinstance(error, CaseError)
                and error.code in {"FORGED_CITATION", "TOOL_LIMIT", "STALE_INPUTS"}
                else "PROVIDER_FAILURE"
            )
            value = {"error": code}
            if kind == "PROVIDER" and isinstance(error, ProviderRunError):
                from clearledger.provider_diagnostics import sanitized

                value["metrics"] = {
                    k: v
                    for k, v in error.metrics.items()
                    if k
                    in {
                        "input_tokens",
                        "output_tokens",
                        "latency_ms",
                        "estimated_cost_paise",
                        "usage_complete",
                    }
                    and (v is None or type(v) in (int, bool))
                }
                if error.metrics.get("diagnostic"):
                    value["metrics"]["diagnostic"] = sanitized(error.metrics["diagnostic"])
                if error.metrics.get("schema_errors"):
                    from clearledger.investigation_ai_contract import schema_errors

                    value["metrics"]["schema_errors"] = schema_errors(
                        error.metrics["schema_errors"]
                    )
            elif kind == "PROVIDER":
                from clearledger.provider_diagnostics import diagnostic, exception_category

                value["metrics"] = {
                    "diagnostic": diagnostic("LOCAL_VALIDATION", exception_category(error))
                }
        with self.transaction() as (session, run, row):
            safe_metadata = {
                k: v
                for k, v in (metadata or {}).items()
                if k in {"tool", "claim_id", "provider", "attempt"}
            }
            metrics = (
                (value.get("result", {}).get("metrics", {}) or value.get("metrics", {}))
                if kind == "PROVIDER"
                else {}
            )
            from clearledger.provider_diagnostics import sanitized

            safe_metrics = {
                k: v
                for k, v in metrics.items()
                if k
                in {
                    "input_tokens",
                    "output_tokens",
                    "latency_ms",
                    "estimated_cost_paise",
                    "usage_complete",
                    "external_calls",
                }
                and (v is None or type(v) in (int, bool))
            }
            session.add(
                InvestigationResult(
                    organization_id=self.org, run_id=run.id, operation_key=key, value=value
                )
            )
            session.add(
                InvestigationTrace(
                    organization_id=self.org,
                    run_id=run.id,
                    trace_key=key,
                    node=kind,
                    data={
                        "operation_sha256": key,
                        "error_code": value.get("error"),
                        "input_tokens_reserved": input_tokens,
                        "output_tokens_reserved": output_tokens,
                        "cost_paise_reserved": cost,
                        "metadata": safe_metadata,
                        "usage": safe_metrics,
                        **(
                            {"schema_errors": metrics["schema_errors"]}
                            if metrics.get("schema_errors")
                            else {}
                        ),
                        **(
                            {"diagnostic": sanitized(metrics["diagnostic"])}
                            if metrics.get("diagnostic")
                            else {}
                        ),
                    },
                )
            )
            publish(
                session,
                self.org,
                "investigation.step",
                "case_id",
                self.case_id,
                "investigation-worker",
                {
                    "run_id": str(run.id),
                    "operation_sha256": key,
                    "kind": kind,
                    "error_code": value.get("error"),
                    "metadata": safe_metadata,
                },
                key={"run": str(run.id), "operation": key},
                queued=False,
            )
        if "error" in value:
            raise CaseError(value["error"])
        return result

    def emit(self, frame):
        with self.transaction() as (session, run, row):
            if run.status in {"COMPLETED", "AWAITING_REVIEW", "STALE"}:
                return
            fresh = current(session, self.org, run, self.settings)
            now = session.scalar(text("SELECT clock_timestamp()"))
            if run.deadline_at and run.deadline_at <= now and fresh:
                from clearledger.investigation_director import consistency

                frame.error_code = "TIMEOUT"
                frame.findings = [
                    consistency(o, None, None, [], error="TIMEOUT", incomplete=True)
                    for o in frame.objectives
                ]
            status = (
                "STALE" if not fresh else "AWAITING_REVIEW" if frame.error_code else "COMPLETED"
            )
            result_version = None
            if fresh:
                case = root(session, self.org, self.case_id)
                for target in ("MATCHING", "INVESTIGATING", "AWAITING_REVIEW"):
                    if (case.state, target) not in {
                        ("NEW", "MATCHING"),
                        ("MATCHING", "INVESTIGATING"),
                        ("AWAITING_EVIDENCE", "INVESTIGATING"),
                        ("INVESTIGATING", "AWAITING_REVIEW"),
                    }:
                        continue
                    case_transition(CaseState(case.state), CaseState(target))
                    case.state = target
                    revise(
                        session,
                        self.org,
                        case,
                        "investigation-worker",
                        "case.investigated",
                        EvidenceOriginals(self.settings.document_root),
                        invalidate=False,
                        enqueue=False,
                        details={"run_id": str(run.id)},
                    )
                result_version = case.version
            for finding in frame.findings:
                objective = next(o for o in frame.objectives if o.claim_id == finding.claim_id)
                if (
                    scoped(
                        session,
                        InvestigationFinding,
                        self.org,
                        run_id=run.id,
                        claim_id=finding.claim_id,
                    )
                    is None
                ):
                    session.add(
                        InvestigationFinding(
                            organization_id=self.org,
                            run_id=run.id,
                            case_id=self.case_id,
                            claim_id=finding.claim_id,
                            basis_sha256=objective.basis_sha256,
                            value=finding.model_dump(mode="json"),
                        )
                    )
            publish(
                session,
                self.org,
                "investigation.completed",
                "case_id",
                self.case_id,
                "investigation-worker",
                {
                    "run_id": str(run.id),
                    "status": status,
                    "recommendation": run.recommendation,
                    "error_code": "STALE_INPUTS" if not fresh else frame.error_code,
                    "financial_authority": False,
                },
                key={"run_completed": str(run.id)},
                queued=False,
            )
            session.add(
                InvestigationTrace(
                    organization_id=self.org,
                    run_id=run.id,
                    trace_key=digest({"completed": str(run.id)}),
                    node="EMIT",
                    data={
                        "status": status,
                        "error_code": "STALE_INPUTS" if not fresh else frame.error_code,
                        "recommendation": "AWAITING_REVIEW",
                        "financial_authority": False,
                    },
                )
            )
            run.status = status
            run.result_case_version = result_version
            run.error_code = "STALE_INPUTS" if not fresh else frame.error_code
            run.recommendation = "AWAITING_REVIEW"
            run.version += 1

    def acknowledge(self):
        with self.transaction() as (session, run, row):
            if run.status not in {"COMPLETED", "AWAITING_REVIEW", "STALE"}:
                raise CaseError("INVESTIGATION_NOT_FINISHED")
            if (
                scoped(
                    session,
                    EventConsumption,
                    self.org,
                    event_id=row.event_id,
                    consumer="case-lifecycle-v1",
                )
                is None
            ):
                session.add(
                    EventConsumption(
                        organization_id=self.org,
                        event_id=row.event_id,
                        consumer="case-lifecycle-v1",
                        outcome="HANDLED",
                    )
                )
            row.status = "DELIVERED"
            row.version += 1
            row.lease_token = row.lease_until = None
            row.last_error_code = None
            session.add(
                OutboxDelivery(
                    organization_id=self.org,
                    outbox_id=row.id,
                    attempt=row.attempts,
                    phase="DELIVERED",
                    error_code=None,
                )
            )
