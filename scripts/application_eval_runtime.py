"""Actual API observations. No attestations, source signing, answers or financial posting."""

import csv
import io
import json
from collections import Counter
from uuid import uuid4

from application_eval_contract import latency_summary, outcome_counts, snapshot_predictions
from application_eval_host import application, drain, environment, initialize, rows
from application_eval_inputs import IMPORTS, MIMES, sha

from clearledger.finance_models import CashAllocation, LedgerJournal, LedgerLine, NoncashSettlement
from clearledger.models import ProviderReservation


def imports(api, source):
    result = []
    for kind in IMPORTS:
        raw = source.read(f"imports/{kind}.csv")
        count = len(list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))))
        headers = {
            "Content-Type": "text/csv",
            "X-Data-Contract-Version": "1.0",
            "X-Source-Filename": kind + ".csv",
        }
        key = uuid4()
        response = api.request("POST", "/imports/" + kind, key=key, content=raw, headers=headers)
        probes = []
        if response.status_code == 200:
            for replay_key in (key, uuid4()):
                replay = api.request(
                    "POST", "/imports/" + kind, key=replay_key, content=raw, headers=headers
                )
                probes.append({"status": replay.status_code, "result": replay.json()})
        result.append(
            {
                "kind": kind,
                "input_rows": count,
                "status": response.status_code,
                "result": response.json(),
                "replays": probes,
            }
        )
        if response.status_code != 200:
            break  # Never rewrite/drop invalid input rows to manufacture compatibility.
    return result


def matching(api, data):
    result = {}
    for receipt in data["receipts"]:
        modes = {}
        for name, context in (
            ("match", "matching-context"),
            ("match-advanced", "advanced-matching-context"),
        ):
            current = api.get(f"/receipts/{receipt['id']}/{context}")
            invoices = current["snapshot"]["invoices"]
            if len(invoices) > 100:
                modes[name] = {"outcome": "NOT_EVALUABLE", "reason": "EXPECTED_VERSION_MAP_LIMIT"}
                continue
            body = {
                "expected_receipt_version": receipt["version"],
                "expected_invoice_versions": {i["id"]: i["version"] for i in invoices},
                "expected_snapshot_sha256": current["snapshot_sha256"],
            }
            key = uuid4()
            response = api.request("POST", f"/receipts/{receipt['id']}/{name}", key=key, json=body)
            modes[name] = (
                response.json()
                if response.status_code == 200
                else {
                    "outcome": "API_FAILURE",
                    "status": response.status_code,
                    "detail": response.json(),
                }
            )
            if response.status_code == 200:
                again = api.request("POST", f"/receipts/{receipt['id']}/{name}", key=key, json=body)
                if again.status_code != 200 or again.json() != response.json():
                    raise RuntimeError("Matching replay changed immutable result")
        result[receipt["id"]] = modes
    return result


def documents(api, source, output):
    records = {}
    for relative in source.files:
        if not relative.startswith("app_visible/"):
            continue
        from pathlib import PurePosixPath

        raw = source.read(relative)
        path = PurePosixPath(relative)
        header = {
            "Content-Type": MIMES[path.suffix.lower()],
            "X-Source-Filename": path.name,
            "X-Synthetic-Data": "false",
        }
        response = api.request("POST", "/documents", content=raw, headers=header)
        value = response.json()
        identifier = value.get("id") or value.get("document_id")
        if identifier is None:
            records[relative] = {"upload_status": response.status_code, "failure": value}
            continue
        doc = api.get(f"/documents/{identifier}")
        original = api.request("GET", f"/documents/{identifier}/original")
        if (
            original.status_code != 200
            or original.content != raw
            or sha(raw) != doc["content_sha256"]
        ):
            raise RuntimeError("Original document integrity failure")
        canonical = api.get(f"/documents/{identifier}/text")
        calculated = sha(
            json.dumps(canonical["pages"], sort_keys=True, separators=(",", ":")).encode()
        )
        if calculated != canonical["canonical_sha256"]:
            raise RuntimeError("Canonical pages integrity failure")
        positive, negative = 0, 0
        for number, page in enumerate(canonical["pages"], 1):
            if not page:
                continue
            quote = page[:2000]
            span = {"page": number, "start": 0, "end": len(quote), "quote": quote}
            check = api.request("POST", f"/documents/{identifier}/verify-span", json=span)
            bad = api.request(
                "POST",
                f"/documents/{identifier}/verify-span",
                json={**span, "quote": ("!" if quote[0] != "!" else "?") + quote[1:]},
            )
            if check.status_code != 200 or bad.status_code != 422:
                raise RuntimeError("Canonical span verification boundary failed")
            positive += 1
            negative += 1
        run = api.request(
            "POST",
            f"/documents/{identifier}/extract",
            json={"expected_document_version": doc["version"], "allow_external": False},
        )
        extracted = run.json()
        if run.status_code == 200:
            if (
                extracted["route"] == "LLM"
                or extracted["metrics"]["attempts"] != 0
                or extracted["financial_authority"]
            ):
                raise RuntimeError("Offline extraction/authority boundary failed")
        correlation = None
        if run.status_code == 200 and (
            extracted.get("result", {}).get("utr_references")
            or extracted.get("result", {}).get("invoice_references")
        ):
            correlated = api.request(
                "POST",
                f"/documents/{identifier}/correlate",
                json={
                    "extraction_id": extracted["id"],
                    "expected_document_version": doc["version"],
                },
            )
            correlation = {"status_code": correlated.status_code, "result": correlated.json()}
            if correlated.status_code == 200 and correlated.json()["status"] == "LINKED":
                raise RuntimeError("Unattested source unexpectedly linked")
        literal = None
        if path.suffix == ".json" and run.status_code == 200:
            original_json = json.loads(raw)
            if original_json.get("remittance_version") == "1.0":
                facts = extracted.get("result", {})
                literal = {
                    kind: {
                        "source_count": len(original_json[kind]),
                        "extracted_count": len(facts.get(kind, [])),
                        "exact": original_json[kind] == [r["value"] for r in facts.get(kind, [])],
                    }
                    for kind in ("invoice_references", "utr_references")
                }
        records[relative] = {
            "upload_status": response.status_code,
            "document": doc,
            "canonical": canonical,
            "positive_spans": positive,
            "forged_spans_rejected": negative,
            "extraction_status": run.status_code,
            "extraction": extracted,
            "correlation": correlation,
            "structured_literal_check": literal,
        }
        with (output / "documents.progress.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"source": relative, **records[relative]}) + "\n")
        if len(records) % 50 == 0:
            print(f"Document observations completed: {len(records)}", flush=True)
    return records


def investigations(api, engine, org, env, output):
    cases = api.collection("/review/cases")
    attempts = []
    evidence = []
    claim_count = 0
    for case in cases:
        claims = api.collection(f"/review/cases/{case['id']}/claims")
        claim_count += len(claims)
        if case["customer_id"] is not None and not case["is_stale"]:
            query = api.request(
                "POST",
                f"/cases/{case['id']}/evidence/search",
                json={
                    "expected_case_version": case["version"],
                    "expected_context_sha256": case["context_sha256"],
                    "customer_id": case["customer_id"],
                    "tool": "get_invoice_evidence",
                    "limit": 50,
                },
            )
            evidence.append(
                {"case_id": case["id"], "status": query.status_code, "result": query.json()}
            )
        if not claims:
            continue
        for start in range(0, len(claims), 10):
            current = api.get(f"/review/cases/{case['id']}")
            response = api.request(
                "POST",
                f"/cases/{case['id']}/investigations",
                json={
                    "expected_case_version": current["version"],
                    "expected_context_sha256": current["context_sha256"],
                    "claim_ids": [c["id"] for c in claims[start : start + 10]],
                    "allow_external": False,
                },
            )
            observation = {
                "case_id": case["id"],
                "status": response.status_code,
                "run": response.json(),
            }
            if response.status_code == 200:
                drain(engine, org, env, output)
                identifier = response.json()["id"]
                observation["run"] = api.get(f"/investigations/{identifier}")
                observation["findings"] = api.get(f"/investigations/{identifier}/findings")
            attempts.append(observation)
    return {
        "cases": cases,
        "claim_count": claim_count,
        "attempts": attempts,
        "evidence_queries": evidence,
    }


def run(source, url, output):
    engine, org, password = initialize(url)
    env = environment(url, org, output / "originals")
    try:
        with application(env, password, output) as api:
            imported = imports(api, source)
            data = {
                kind: api.collection("/" + kind)
                for kind in (
                    "customers",
                    "payer-aliases",
                    "invoices",
                    "bank-transactions",
                    "receipts",
                )
            }
            before = rows(engine)
            matches = matching(api, data)
            docs = documents(api, source, output)
            workers = drain(engine, org, env, output)
            investigated = investigations(api, engine, org, env, output)
            # A read probe verifies that the real host has no financial identity adapter.
            finance_status = api.request("GET", "/finance/journals").status_code
            if finance_status != 503 or before != rows(engine):
                raise RuntimeError("Financial authorization or non-mutation invariant failed")
            protected = rows(
                engine,
                (LedgerJournal, LedgerLine, CashAllocation, NoncashSettlement, ProviderReservation),
            )
            if any(protected.values()):
                raise RuntimeError("Unexpected financial posting or external provider reservation")
            predictions = snapshot_predictions(data, matches, source.as_of.isoformat())
            observations = {
                "imports": imported,
                "records": data,
                "matching": matches,
                "documents": docs,
                "workers": workers,
                "investigation": investigated,
                "snapshot_predictions": predictions,
                "calls": api.calls,
            }
            summary = {
                "snapshot_as_of": source.as_of.isoformat(),
                "record_counts": {k: len(v) for k, v in data.items()},
                "import_file_statuses": dict(Counter(str(r["status"]) for r in imported)),
                "matching_outcomes": outcome_counts(matches),
                "document_upload_statuses": dict(
                    Counter(str(r["upload_status"]) for r in docs.values())
                ),
                "document_parse_states": dict(
                    Counter(
                        r.get("document", {}).get("parse_status", "REJECTED") for r in docs.values()
                    )
                ),
                "extraction_states": dict(
                    Counter(
                        r.get("extraction", {}).get("status", "API_FAILURE") for r in docs.values()
                    )
                ),
                "extraction_routes": dict(
                    Counter(r.get("extraction", {}).get("route", "NONE") for r in docs.values())
                ),
                "positive_spans": sum(r.get("positive_spans", 0) for r in docs.values()),
                "forged_spans_rejected": sum(
                    r.get("forged_spans_rejected", 0) for r in docs.values()
                ),
                "correlation_states": dict(
                    Counter(
                        r["correlation"]["result"].get("status", "API_FAILURE")
                        for r in docs.values()
                        if r.get("correlation")
                    )
                ),
                "case_count": len(investigated["cases"]),
                "investigation_requests": len(investigated["attempts"]),
                "materialized_claims": investigated["claim_count"],
                "evidence_query_statuses": dict(
                    Counter(str(q["status"]) for q in investigated["evidence_queries"])
                ),
                "native_evidence_hits": sum(
                    len(q["result"].get("items", [])) for q in investigated["evidence_queries"]
                ),
                "http_statuses": dict(Counter(str(c["status"]) for c in api.calls)),
                "unresolved_invoice_open_paise": sum(
                    i["open_amount_paise"] for i in data["invoices"]
                ),
                "receipt_unapplied_paise": sum(
                    r["unapplied_amount_paise"] for r in data["receipts"]
                ),
                "financial_mutations": 0,
                "external_provider_reservations": 0,
                "financial_identity_status": finance_status,
                "http_latency": latency_summary([c["elapsed_ns"] for c in api.calls]),
                "stage_accuracy": "NOT_EVALUABLE: original stage schedule and answers absent",
                "unstructured_extraction_accuracy": "NOT_EVALUABLE: extraction labels absent",
                "deduction_legitimacy": "REVIEW REQUIRED: evidence and authority unavailable",
                "source_authentication": "UNVERIFIED: publisher keys/manifests not supplied",
                "gemini_accuracy": "NOT EVALUABLE: external calls disabled",
            }
        return observations, summary
    finally:
        engine.dispose()
