"""Small synthetic acceptance sequence over existing APIs/runners, never a product agent."""

import json
import threading
import time
from collections import Counter
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_ai_usefulness import SMOKE
from test_cases import pump
from test_documents import auth, extract, get, upload
from test_finance import headers
from test_matching import financial_state

from clearledger import documents, provider_budget
from clearledger.document_contract import Extraction, validate_semantics
from clearledger.document_privacy import project
from clearledger.models import ProviderReservation


def extraction_case(api, engine, org, name, raw, report):
    started = time.perf_counter_ns()
    pages = [raw.decode()]
    projected = project(pages)
    doc = upload(api, raw, name=f"unit-{name}.txt").json()
    assert get(api, f"/documents/{doc['id']}/text").json()["pages"] == pages
    before_count = count(engine, org)
    baseline = extract(api, doc["id"]).json()
    assert baseline["route"] == "REVIEW" and count(engine, org) == before_count
    key = uuid4()
    model_started = time.perf_counter_ns()
    response = extract(api, doc["id"], key=key, allow_external=True)
    row = {
        "fixture": name,
        "http_status": response.status_code,
        "extraction_api_ns": time.perf_counter_ns() - model_started,
        "privacy_redactions": dict(Counter(m.kind for m in projected.masks)),
        "baseline": baseline,
        "actual": response.json(),
    }
    report.setdefault("extraction_cases", []).append(row)
    assert response.status_code == 200
    actual = row["actual"]
    if actual["status"] not in {"SUCCEEDED", "NEEDS_REVIEW"} or not actual["result"]:
        report["stopped"] = "EXTRACTION_FAILED"
        return None
    parsed = Extraction.model_validate(actual["result"])
    validate_semantics(parsed, pages)
    correct = {r.value for r in parsed.invoice_references} == {"I-1"}
    correct &= (
        not parsed.claims
        if name == "injection"
        else len(parsed.claims) == 1
        and parsed.claims[0].category == ("rebate" if name == "conditional" else "damage")
        and parsed.claims[0].amount_paise == (None if name == "missing_amount" else 101)
        and parsed.claims[0].reason_code is None
    )
    correct &= {r.value for r in parsed.utr_references} == (
        {"t"} if name == "automation" else set()
    )
    correct &= parsed.payer_hint is None or (
        name == "automation" and parsed.payer_hint.value == "c"
    )
    row["expected_fields_correct"] = bool(correct)
    if not correct:
        report["stopped"] = "EXTRACTION_EXPECTATION_FAILED"
        return None
    pointers = [r.span for r in parsed.invoice_references + parsed.utr_references]
    if parsed.payer_hint:
        pointers.append(parsed.payer_hint.span)
    pointers.extend(parsed.unparsed_fields)
    pointers += [c.description for c in parsed.claims] + [
        c.amount_span for c in parsed.claims if c.amount_span
    ]
    for p in pointers:
        verified = api.post(
            f"/documents/{doc['id']}/verify-span", headers=auth(), json=p.model_dump(mode="json")
        )
        assert verified.status_code == 200 and verified.json()["source_consistent"]
    row["source_spans_verified"] = len(pointers)
    assert actual["requires_human_review"] and not actual["financial_authority"]
    after_count = count(engine, org)
    replay = extract(api, doc["id"], key=key, allow_external=True)
    assert replay.status_code == 200 and replay.json()["id"] == actual["id"]
    assert count(engine, org) == after_count
    row["replay_same_id_no_provider_call"] = True
    row["end_to_end_ns"] = time.perf_counter_ns() - started
    return doc, actual


def count(engine, org):
    with Session(engine) as session:
        return len(
            list(
                session.scalars(
                    select(ProviderReservation.id).where(ProviderReservation.organization_id == org)
                )
            )
        )


def acceptance(
    api, engine, org, settings, report, output, *, ledger_path=None, variations_only=False
):
    from live_correlation_slice import RAW, finish, prepare
    from live_investigator_smoke import campaign

    path = ledger_path or output.parent.parent / "live-acceptance-v2-20261027-budget.json"
    ledger = (
        json.loads(path.read_text())
        if path.exists()
        else {"cap_paise": 600, "cap_attempts": 20, "reservations": []}
    )
    assert ledger["cap_paise"] == 600 and ledger["cap_attempts"] == 20
    attempt_cost = report["attempt_cost_cap_paise"]
    assert attempt_cost == 34
    assert isinstance(ledger["reservations"], list) and len(ledger["reservations"]) <= 20
    assert all(type(r["paise"]) is int and r["paise"] in {30, 34} for r in ledger["reservations"])
    assert sum(r["paise"] for r in ledger["reservations"]) <= 600
    lock = threading.Lock()
    original = provider_budget.reserve
    original_document = documents.reserve

    def admitted(engine, org, provider, config):
        with lock:
            assert len(ledger["reservations"]) < 20, "CAMPAIGN_ATTEMPT_LIMIT"
            assert sum(r["paise"] for r in ledger["reservations"]) + attempt_cost <= 600, (
                "CAMPAIGN_SPEND_LIMIT"
            )
            reserved = original(engine, org, provider, config)
            ledger["reservations"].append(
                {
                    "ordinal": len(ledger["reservations"]) + 1,
                    "paise": attempt_cost,
                    "report_id": output.name,
                }
            )
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(ledger, indent=2), encoding="utf8")
            tmp.replace(path)
            return reserved

    provider_budget.reserve = documents.reserve = admitted
    env = engine, org, None, api, api
    total_started = time.perf_counter_ns()
    before = None
    try:
        prepare(api, engine, org, settings, investigation_sources=True)
        before = financial_state(api)
        report["variation_continuation_only"] = variations_only
        if not variations_only:
            primary = extraction_case(api, engine, org, "automation", RAW.encode(), report)
            if primary is None:
                return False
            correlated = finish(env, *primary)
            report["automation"] = correlated
            replay = api.post(
                f"/review/correlation-tasks/{correlated['ready_task']['id']}/decision",
                json=correlated["decision_payload"],
                headers=headers("controller", UUID(correlated["decision_key"])),
            )
            assert replay.status_code == 200 and replay.json()["id"] == correlated["decision"]["id"]
            assert pump(env) == {}
            report["confirmation_replay_same_id_no_work"] = True
            if not campaign(
                api,
                engine,
                org,
                settings,
                report,
                existing=(correlated["canonical_case"], correlated["claim"]),
            ):
                return False
            report["primary_end_to_end_including_pacing_ns"] = (
                time.perf_counter_ns() - total_started
            )
        settings.extraction_provider = "gemini"
        names = (
            ("missing_amount", "conditional", "injection")
            if variations_only
            else ("prose", "missing_amount", "conditional", "injection")
        )
        for name in names:
            time.sleep(61)
            raw = next(r[1] for r in SMOKE if r[0] == name)
            variation = extraction_case(api, engine, org, name, raw, report)
            if variation is None:
                return False
            pump(env)
            if name == "prose":
                case = next(
                    c for c in get(api, "/cases").json() if variation[0]["id"] in c["document_ids"]
                )
                tasks = api.get(
                    f"/review/cases/{case['id']}/correlation-tasks", headers=headers("controller")
                ).json()
                task = tasks[0]
                assert task["reason"] == "MISSING_AUTHENTICATED_CORRELATION_EVIDENCE"
                body = {
                    "expected_case_version": case["version"],
                    "expected_context_sha256": case["context_sha256"],
                    "expected_task_sha256": task["input_sha256"],
                    "decision": "CONFIRM",
                }
                denied = api.post(
                    f"/review/correlation-tasks/{task['id']}/decision",
                    json=body,
                    headers=headers("controller"),
                )
                assert denied.status_code == 409
                body["decision"] = "REJECT"
                key = uuid4()
                rejected = api.post(
                    f"/review/correlation-tasks/{task['id']}/decision",
                    json=body,
                    headers=headers("controller", key),
                )
                assert rejected.status_code == 200
                repeated = api.post(
                    f"/review/correlation-tasks/{task['id']}/decision",
                    json=body,
                    headers=headers("controller", key),
                )
                assert (
                    repeated.status_code == 200 and repeated.json()["id"] == rejected.json()["id"]
                )
                report["human_review_missing_proof"] = {
                    "confirm_denied_status": 409,
                    "denial_code": denied.json()["detail"],
                    "rejection": rejected.json(),
                    "replay_same_id": True,
                }
            assert financial_state(api) == before
        report["financial_nonmutation"] = financial_state(api) == before
        return True
    finally:
        provider_budget.reserve, documents.reserve = original, original_document
        # Retain the safety measurement even on schema/expectation/budget abstention.
        if before is not None:
            report["financial_nonmutation"] = financial_state(api) == before
        report["global_reserved_attempts"] = len(ledger["reservations"])
        report["global_reserved_paise"] = sum(r["paise"] for r in ledger["reservations"])
        report["remaining_authorized_paise"] = 600 - report["global_reserved_paise"]
        report["wall_ns_including_pacing"] = time.perf_counter_ns() - total_started
        (output / "observations.json").write_text(json.dumps(report, indent=2), encoding="utf8")
        assert report.get("financial_nonmutation", True), "FINANCIAL_MUTATION"
