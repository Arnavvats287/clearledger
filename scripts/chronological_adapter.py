"""Persistent actual-API orchestration; no scorer, schedule or dataset access."""

import os
import sys
import time
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from application_eval_contract import latency_summary, snapshot_predictions
from application_eval_host import fingerprint, rows
from application_eval_inputs import sha
from application_eval_runtime import documents, matching
from chronological_diagnostics import ObservationFailure, diagnostic, response_code, route
from chronological_host import (
    BoundedAPI,
    application,
    drain_owned,
    host_environment,
    initialize_owned,
)
from chronological_protocol import MAX_RESPONSE, Deltas, canonical

from clearledger.evidence_contract import SearchResult
from clearledger.finance_models import CashAllocation, LedgerJournal, LedgerLine, NoncashSettlement
from clearledger.models import ProviderReservation

PROTECTED = (LedgerJournal, LedgerLine, CashAllocation, NoncashSettlement, ProviderReservation)
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
MAX_STAGES = 10000
FAILURE_RESERVE_BYTES = 64 * 1024 * 1024
EVIDENCE_PAGE_LIMIT = 4
REVIEW_EVIDENCE_CODES = {
    "EVIDENCE_FINANCIAL_SOURCE_BUDGET",
    "EVIDENCE_INVOICE_SCOPE_BUDGET",
    "EVIDENCE_SOURCE_BUDGET",
    "EVIDENCE_ORIGINAL_DOCUMENT_BUDGET",
    "EVIDENCE_ORIGINAL_BYTE_BUDGET",
    "CASE_ANALYSIS_LIMIT",
    "CASE_MEMBERSHIP_LIMIT",
    "CASE_GRAPH_LIMIT",
    "STALE_EVIDENCE_CASE_CONTEXT",
}


class Adapter:
    def __init__(self, url, output):
        self.url, self.output = url, Path(output)
        self.stack = ExitStack()
        self.binding = None
        self.cutoff = None
        self.manifest_hash = None
        self.requests, self.snapshots, self.nonces = {}, {}, {}
        self.deltas = Deltas()
        self.poisoned = False
        self.engine = None
        self.artifact_bytes = 0
        self.component = "binding"

    def save(self, path, raw, *, emergency=False):
        reserve = min(FAILURE_RESERVE_BYTES, MAX_ARTIFACT_BYTES // 16)
        limit = MAX_ARTIFACT_BYTES if emergency else MAX_ARTIFACT_BYTES - reserve
        if self.artifact_bytes + len(raw) > limit:
            raise RuntimeError("PRIVATE_PROVENANCE_STORAGE_BUDGET")
        with path.open("xb") as stream:
            stream.write(raw)
        self.artifact_bytes += len(raw)

    def close(self):
        try:
            self.stack.close()
        finally:
            if self.engine is not None:
                self.engine.dispose()

    def start(self, stage):
        self.output.mkdir(parents=True, exist_ok=False)
        self.engine, self.org, password = initialize_owned(
            self.url, stage.message["company"], stage.message["run_id"]
        )
        self.env = host_environment(self.url, self.org, self.output)
        client = self.stack.enter_context(
            application(self.env, password, self.output, factory="chronological_host:factory")
        )
        self.api = BoundedAPI(client.client, password, stage.message["run_id"])

    def stage(self, stage):
        started = time.perf_counter_ns()
        analysis_started = False
        stage_dir = None
        retained_raw = None
        self.component = "binding"
        response = stage.envelope()
        request_id, snapshot_id = (stage.request[k] for k in ("request_id", "snapshot_id"))
        binding = (stage.message["run_id"], stage.message["company"], stage.request["split"])
        if self.poisoned:
            response["api_observations"] = {"error": "RUN_FAILED_DISCARD_DATABASE"}
            return response
        try:
            if self.binding is not None and binding != self.binding:
                raise ValueError("RUN_OR_COMPANY_CHANGED")
            if stage.message["nonce"] not in self.nonces and len(self.nonces) >= MAX_STAGES:
                raise ValueError("RUN_NONCE_BUDGET")
            if request_id in self.requests:
                digest, saved = self.requests[request_id]
                if digest != stage.digest:
                    raise ValueError("CONFLICTING_STAGE_REPLAY")
                nonce = stage.message["nonce"]
                if nonce in self.nonces and self.nonces[nonce] != request_id:
                    raise ValueError("REUSED_NONCE")
                self.nonces[nonce] = request_id
                return {**saved, "nonce": nonce}
            if snapshot_id in self.snapshots or stage.message["nonce"] in self.nonces:
                raise ValueError("REUSED_STAGE_ID_OR_NONCE")
            if len(self.requests) >= MAX_STAGES:
                raise ValueError("RUN_STAGE_BUDGET")
            if self.cutoff is not None and stage.cutoff < self.cutoff:
                raise ValueError("TIME_REGRESSION")
            manifest_hash = sha(canonical(stage.manifest))
            if stage.cutoff == self.cutoff and manifest_hash != self.manifest_hash:
                raise ValueError("TIED_CUTOFF_INPUTS_CHANGED")
            self.component = "delta_validation"
            plan = self.deltas.plan(stage)  # Validate ALL changes before any writes.
            if self.binding is None:
                self.component = "initialize"
                self.start(stage)
                self.binding = binding
            self.component = "stage_archive"
            directory = self.output / request_id
            directory.mkdir(exist_ok=False)
            stage_dir = directory  # Only this invocation may write into its owned stage.
            self.api.observations.clear()
            analysis_started = True
            calls_start = len(self.api.calls)
            objects = self.output / "input-objects"
            objects.mkdir(exist_ok=True)
            for raw in stage.bytes.values():
                path = objects / sha(raw)
                if path.exists():
                    if path.read_bytes() != raw:
                        raise RuntimeError("PRIVATE_SOURCE_ARCHIVE_CHANGED")
                else:
                    self.save(path, raw)
            self.api.deadline = time.monotonic() + max(
                1, 105 - (time.perf_counter_ns() - started) / 1_000_000_000
            )
            self.component = "financial_snapshot_before_import"
            old = rows(self.engine)
            imported = []
            self.component = "csv_import"
            for kind, (raw, count) in plan[0].items():
                result = self.api.request(
                    "POST",
                    "/imports/" + kind,
                    content=raw,
                    headers={
                        "Content-Type": "text/csv",
                        "X-Data-Contract-Version": "1.0",
                        "X-Source-Filename": kind + ".csv",
                    },
                )
                if result.status_code != 200:
                    raise RuntimeError("CSV_API_ERROR")
                imported.append({"kind": kind, "new_rows": count, "result": result.json()})
            self.component = "financial_snapshot_after_import"
            before = rows(self.engine)
            for table, records in old.items():
                current = {r["id"]: r for r in before[table]}
                if any(current.get(r["id"]) != r for r in records):
                    raise RuntimeError("PREVIOUS_FINANCIAL_RECORD_CHANGED")
            self.component = "documents"
            source = SimpleNamespace(files=plan[1], read=plan[1].__getitem__)
            with redirect_stdout(sys.stderr):
                observed_docs = documents(self.api, source, stage_dir)
            for doc in observed_docs.values():
                if (
                    doc["upload_status"] != 200
                    or doc.get("extraction_status") != 200
                    or (doc.get("correlation") and doc["correlation"]["status_code"] != 200)
                ):
                    raise RuntimeError("DOCUMENT_API_ERROR")
            self.component = "worker_after_documents"
            drain_owned(self.engine, self.org, self.env, self.api)
            self.component = "read_financial_records"
            data = {
                kind: self.api.collection("/" + kind)
                for kind in ("customers", "invoices", "bank-transactions", "receipts")
            }
            banks = {b["id"]: b for b in data["bank-transactions"]}
            requested = [
                r
                for r in data["receipts"]
                if {k: banks[r["bank_transaction_id"]][k] for k in stage.request["transaction"]}
                == stage.request["transaction"]
            ]
            if len(requested) > 1:
                raise RuntimeError("DUPLICATE_RECEIPT_NATURAL_KEY")
            data["receipts"] = requested
            self.component = "matching"
            observed_matches = matching(self.api, data)
            if any(
                v.get("outcome") == "API_FAILURE"
                for modes in observed_matches.values()
                for v in modes.values()
            ):
                raise RuntimeError("MATCHING_API_ERROR")
            self.component = "worker_after_matching"
            drain_owned(self.engine, self.org, self.env, self.api)
            self.component = "cases"
            cases, evidence, investigations = self.case_observations(requested, observed_docs)
            self.component = "financial_verification"
            finance_status = self.api.request("GET", "/finance/journals").status_code
            after = rows(self.engine)
            if (
                before != after
                or any(rows(self.engine, PROTECTED).values())
                or finance_status != 503
            ):
                response["financial_mutation_check"] = "FAIL"
                raise RuntimeError("FINANCIAL_INVARIANT_FAILED")
            response["financial_mutation_check"] = "PASS"
            if requested:
                response["prediction"] = snapshot_predictions(
                    data, observed_matches, stage.request["as_of"]
                )[0]
                if any(e["outcome"] == "REVIEW_REQUIRED" for e in evidence):
                    response["prediction"]["human_reviews"].append(
                        "REVIEW REQUIRED: evidence retrieval incomplete; no supported allocation"
                    )
            response["status"] = "ABSTAIN"
            observations = {
                "imports": imported,
                "documents": observed_docs,
                "matching": observed_matches,
                "cases": cases,
                "evidence": evidence,
                "investigations": investigations,
                "records": data,
                "calls": self.api.observations,
                "before_financial_sha256": fingerprint(before),
                "after_financial_sha256": fingerprint(after),
                "source_manifest": stage.manifest,
                "request": stage.request,
                "accepted_natural_payloads": {
                    kind: [
                        {"key": list(key), "sha256": digest}
                        for key, digest in sorted(values.items())
                    ]
                    for kind, values in plan[2].items()
                },
            }
            self.component = "persist_observations"
            raw = canonical(observations)
            self.save(stage_dir / "observations.json", raw)
            retained_raw = raw
            self.component = "project_response"
            response.update(
                raw_observation_sha256=sha(raw),
                capabilities={
                    "clock_independent_input_chronology": "AVAILABLE",
                    "historical_application_clock": "NOT_EVALUABLE_NO_APPROVED_REPLAY_CLOCK",
                    "financial_authority": False,
                    "gemini": "DISABLED",
                    "source_authentication": "UNVERIFIED",
                    "benchmark_accuracy": "NOT_EVALUABLE_INDEPENDENT_SCORER_REQUIRED",
                },
                api_observations={
                    "imports": [{"kind": r["kind"], "new_rows": r["new_rows"]} for r in imported],
                    "matching": {
                        mode: value.get("outcome")
                        for modes in observed_matches.values()
                        for mode, value in modes.items()
                    },
                    "documents": [
                        {
                            "source_sha256": r["document"]["content_sha256"],
                            "pages_sha256": r["canonical"]["canonical_sha256"],
                            "version": r["document"]["version"],
                            "parse_status": r["document"]["parse_status"],
                            "extraction_status": r["extraction"]["status"],
                            "route": r["extraction"]["route"],
                            "valid_spans": r["positive_spans"],
                        }
                        for r in observed_docs.values()
                    ],
                    "case_versions": [
                        {"id": c["id"], "version": c["version"], "is_stale": c["is_stale"]}
                        for c in cases
                    ],
                    "evidence_queries": sum(len(e["pages"]) for e in evidence),
                    "evidence_outcomes": [
                        {
                            "status": e["http_status"],
                            "outcome": e["outcome"],
                            "reason": e.get("reason"),
                            "search_complete": e["search_complete"],
                        }
                        for e in evidence
                    ],
                    "investigation_requests": sum("run" in i for i in investigations),
                    "receipt_available": bool(requested),
                    "finance_read_status": finance_status,
                    "latency": latency_summary(
                        [c["elapsed_ns"] for c in self.api.calls[calls_start:]]
                    ),
                },
            )
            self.api.remaining()
            self.deltas.commit(plan)
            self.cutoff, self.manifest_hash = stage.cutoff, manifest_hash
            response["elapsed_ns"] = time.perf_counter_ns() - started
            response["resources"] = {
                "elapsed_ns": response["elapsed_ns"],
                "scope": "adapter_stage_wall_including_child_work",
                "unit": "ns",
            }
            if len(canonical(response)) + 1 > MAX_RESPONSE:
                raise RuntimeError("RESPONSE_LIMIT")
            self.component = "persist_response"
            self.save(stage_dir / "response.json", canonical(response))
            self.requests[request_id] = (stage.digest, response)
            self.snapshots[snapshot_id] = request_id
            self.nonces[stage.message["nonce"]] = request_id
            return response
        except Exception as exc:
            self.poisoned = True
            # Never reflect arbitrary exception text, input values or credentials.
            failed_check = response["financial_mutation_check"]
            response = stage.envelope()
            response["financial_mutation_check"] = (
                failed_check if failed_check == "FAIL" else ("NOT_EVALUABLE")
            )
            response["elapsed_ns"] = time.perf_counter_ns() - started
            failure_diagnostic = diagnostic(exc, self.component)
            response["api_observations"] = {
                "error": failure_diagnostic["exception_type"],
                "diagnostic": failure_diagnostic,
                "artifact_storage": {
                    "used_bytes": self.artifact_bytes,
                    "limit_bytes": MAX_ARTIFACT_BYTES,
                    "failure_reserve_bytes": min(FAILURE_RESERVE_BYTES, MAX_ARTIFACT_BYTES // 16),
                },
                "disposition": "DISCARD_DATABASE_NO_RESUME",
                "recent_http": [
                    {
                        "method": call["method"],
                        "route": route(call["path"]),
                        "status": call["status"],
                    }
                    for call in (self.api.calls[calls_start:][-8:] if analysis_started else [])
                ],
            }
            if self.output.is_dir():
                failure = canonical(
                    {
                        "request": stage.request,
                        "source_manifest": stage.manifest,
                        "failure": failure_diagnostic,
                        "complete": False,
                        "financial_mutation_check": response["financial_mutation_check"],
                        "calls": self.api.observations if analysis_started else [],
                    }
                )
                try:
                    if stage_dir is None:
                        directory = self.output / request_id
                        directory.mkdir(exist_ok=False)
                        stage_dir = directory
                    if retained_raw is None:
                        self.save(stage_dir / "observations.json", failure, emergency=True)
                        retained_raw = failure
                    stored = (stage_dir / "observations.json").read_bytes()
                    if stored != retained_raw:
                        raise OSError("Retained observation integrity failure")
                    response["raw_observation_sha256"] = sha(stored)
                    response["api_observations"]["raw_provenance"] = "RETAINED"
                    try:
                        self.save(
                            stage_dir / "failure.json",
                            canonical(failure_diagnostic),
                            emergency=True,
                        )
                        self.save(stage_dir / "response.json", canonical(response), emergency=True)
                    except (OSError, RuntimeError):
                        # The already verified raw observations are still retained.
                        pass
                except (OSError, RuntimeError) as retention_error:
                    response["api_observations"]["raw_provenance"] = "UNAVAILABLE"
                    failure_diagnostic["retention_failure"] = diagnostic(
                        retention_error, "failure_provenance"
                    )
            else:
                response["api_observations"]["raw_provenance"] = "UNAVAILABLE"
            print(
                canonical(
                    {"event": "chronological_stage_failed", "diagnostic": failure_diagnostic}
                ).decode("utf-8"),
                file=sys.stderr,
                flush=True,
            )
            return response

    def case_observations(self, receipts, documents):
        identifiers = {r["id"] for r in receipts}
        document_ids = {d["document"]["id"] for d in documents.values()}
        cases, evidence, investigations = [], [], []
        # Existing scoped case API avoids revalidating every unrelated historical case.
        discovered = (
            self.api.collection("/review/cases")
            if document_ids
            else [
                case
                for receipt in receipts
                for case in self.api.collection(f"/cases?receipt_id={receipt['id']}")
            ]
        )
        seen = set()
        for case in discovered:
            if not identifiers.intersection(case["receipt_ids"]) and not document_ids.intersection(
                case["document_ids"]
            ):
                continue
            identifier = case["id"]
            if identifier in seen:
                continue
            seen.add(identifier)
            if case["is_stale"]:
                self.component = "case_refresh"
                refreshed = self.api.request(
                    "POST",
                    f"/cases/{identifier}/refresh",
                    json={
                        "expected_case_version": case["version"],
                    },
                )
                if refreshed.status_code != 200:
                    raise ObservationFailure("STALE_CASE_REFRESH_API_ERROR", refreshed)
                case = self.api.get(f"/review/cases/{identifier}")
            if case["customer_id"] is not None:
                self.component = "evidence_query"
                observation = self.observe_evidence(case)
                evidence.append(observation)
                if observation["outcome"] == "REVIEW_REQUIRED":
                    cases.append(case)
                    continue  # No investigation from an incomplete/denied evidence snapshot.
            self.component = "claim_read"
            claims = self.api.collection(f"/review/cases/{identifier}/claims")
            resolved = [c["id"] for c in claims if c["state"] == "RESOLVED"]
            if resolved:
                investigations.append(
                    {
                        "case_id": identifier,
                        "outcome": "NOT_REQUESTED",
                        "reason": "CLAIM_ALREADY_RESOLVED",
                        "claim_ids": resolved,
                    }
                )
            claims = [c for c in claims if c["state"] != "RESOLVED"]
            for start in range(0, len(claims), 10):
                current = self.api.get(f"/review/cases/{identifier}")
                self.component = "investigation_start"
                run = self.api.request(
                    "POST",
                    f"/cases/{identifier}/investigations",
                    json={
                        "expected_case_version": current["version"],
                        "expected_context_sha256": current["context_sha256"],
                        "claim_ids": [c["id"] for c in claims[start : start + 10]],
                        "allow_external": False,
                    },
                )
                if run.status_code != 200:
                    raise ObservationFailure("INVESTIGATION_API_ERROR", run)
                self.component = "investigation_worker"
                drain_owned(self.engine, self.org, self.env, self.api)
                self.component = "investigation_read"
                investigations.append(
                    {
                        "run": self.api.get(f"/investigations/{run.json()['id']}"),
                        "findings": self.api.get(f"/investigations/{run.json()['id']}/findings"),
                    }
                )
            cases.append(self.api.get(f"/review/cases/{identifier}") if claims else case)
        return cases, evidence, investigations

    def observe_evidence(self, case):
        pages, cursor = [], None
        for _ in range(EVIDENCE_PAGE_LIMIT):
            query = self.api.request(
                "POST",
                f"/cases/{case['id']}/evidence/search",
                json={
                    "expected_case_version": case["version"],
                    "expected_context_sha256": case["context_sha256"],
                    "customer_id": case["customer_id"],
                    "tool": "get_invoice_evidence",
                    "limit": 50,
                    **({"after_id": cursor} if cursor else {}),
                },
            )
            if query.status_code != 200:
                code = response_code(query)
                if query.status_code == 409 and code in REVIEW_EVIDENCE_CODES:
                    pages.append({"http_status": 409, "response": query.json()})
                    return {
                        "case_id": case["id"],
                        "http_status": 409,
                        "pages": pages,
                        "outcome": "REVIEW_REQUIRED",
                        "reason": code,
                        "search_complete": False,
                    }
                raise ObservationFailure("EVIDENCE_API_ERROR", query)
            try:
                result = SearchResult.model_validate(query.json())
            except ValueError:
                raise ObservationFailure("EVIDENCE_RESPONSE_INVALID", query) from None
            pages.append({"http_status": 200, "response": query.json()})
            if not result.has_more:
                if not result.search_complete:
                    raise ObservationFailure("EVIDENCE_RESPONSE_INVALID", query)
                return {
                    "case_id": case["id"],
                    "http_status": 200,
                    "pages": pages,
                    "outcome": "COMPLETE"
                    if any(p["response"]["items"] for p in pages)
                    else "NO_EVIDENCE",
                    "search_complete": True,
                }
            next_cursor = str(result.next_after_id) if result.next_after_id else None
            if (
                not result.items
                or not next_cursor
                or next_cursor == cursor
                or result.search_complete
            ):
                raise ObservationFailure("EVIDENCE_RESPONSE_INVALID", query)
            cursor = next_cursor
        return {
            "case_id": case["id"],
            "http_status": 200,
            "pages": pages,
            "outcome": "REVIEW_REQUIRED",
            "reason": "EVIDENCE_OBSERVATION_PAGE_LIMIT",
            "search_complete": False,
        }


def main():
    from chronological_protocol import MAX_WIRE, Stage, strict_json

    # Protocol only on stdout, and no local .env fallback anywhere in this host.
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    if any(
        os.environ.get(key)
        for key in (
            "TEST_DATABASE_URL",
            "PGPASSWORD",
            "PGPASSFILE",
            "PGSERVICE",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
        )
    ):
        print("Runner credential boundary rejected", file=sys.stderr)
        return 2
    adapter = Adapter(
        os.environ.get("DATABASE_URL", ""),
        os.environ.get(
            "CL_ADAPTER_OUTPUT",
            "local-data/chronological-evaluations/" + __import__("uuid").uuid4().hex,
        ),
    )
    exit_code = 0
    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_WIRE + 1)
            if not line:
                break
            if len(line) > MAX_WIRE or not line.endswith(b"\n"):
                raise ValueError("INPUT_WIRE_LIMIT_OR_TRUNCATION")
            stage = Stage(strict_json(line))
            response = adapter.stage(stage)
            sys.stdout.write(canonical(response).decode("utf-8") + "\n")
            sys.stdout.flush()
    except Exception as exc:
        print(
            canonical(
                {
                    "event": "chronological_protocol_failed",
                    "diagnostic": diagnostic(exc, "protocol"),
                }
            ).decode(),
            file=sys.stderr,
        )
        exit_code = 2
    finally:
        try:
            adapter.close()
        except Exception as exc:
            print(
                canonical(
                    {
                        "event": "chronological_shutdown_failed",
                        "diagnostic": diagnostic(exc, "shutdown"),
                    }
                ).decode(),
                file=sys.stderr,
            )
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
