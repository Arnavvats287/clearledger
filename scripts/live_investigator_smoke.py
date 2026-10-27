"""Three source states of one approved minimal AR fixture; no direct model calls."""

import time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_cases import pump
from test_documents import get
from test_evidence import fixture_case, manifest, register
from test_investigations import run, start
from test_matching import financial_state

from clearledger.finance_models import (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)
from clearledger.investigation_ai_contract import ARReply
from clearledger.investigation_models import InvestigationResult
from clearledger.models import ProviderReservation


def campaign(api, engine, org, settings, report, *, existing=None):
    settings.extraction_provider = "disabled"
    env = engine, org, None, api, api
    assert api.app.state.finance_identity_verifier is None or existing is not None
    # Existing deterministic extraction fixture; no new LLM extraction or fake AI output.
    case, claim = (
        existing
        if existing is not None
        else fixture_case(
            env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
        )
    )
    before = financial_state(api)
    invoice_reference = api.get("/invoices").json()[0]["invoice_number"]
    delivery = (
        {
            "shipped": 1,
            "delivered": 1,
            "unit_value": 101,
            "source_invoice_number": invoice_reference,
        }
        if existing is not None
        else {}
    )
    if existing is not None:
        assert claim["amount_paise"] == 101  # Independently declared synthetic expectation.
    settings.investigation_provider = "gemini"
    settings.investigation_external_enabled = True
    settings.investigation_limits = settings.investigation_limits.model_copy(
        update={
            "max_claims": 1,
            "max_attempts": 1,
            "timeout_ms": 120000,
            "max_spend_paise": 2 * report.get("attempt_cost_cap_paise", 30),
            "max_rounds": 24,
            # The same run limits also account for zero-cost deterministic tool decisions.
            # Per-external-call bounds stay configured; spend permits at most two calls.
            "max_input_tokens": 32768,
            "max_output_tokens": 8192,
        }
    )
    report["investigation_cases"] = []
    for index, mode in enumerate(("missing", "supported", "conflict")):
        if report.get("reserved_provider_attempts", 0) >= report["maximum_attempts"]:
            report["stopped"] = "CAMPAIGN_ATTEMPT_LIMIT"
            break
        if index:
            # Shared free-project metadata/count/generation operations, not just generations.
            time.sleep(61)
        case_started = time.perf_counter_ns()
        if mode == "supported":
            for kind in ("WMS", "POD"):
                assert (
                    register(env, manifest(env, kind=kind, damaged=1, **delivery)).status_code
                    == 200
                )
            pump(env)
        elif mode == "conflict":
            conflict_delivery = {**delivery, "shipped": 2, "delivered": 2} if existing else {}
            assert (
                register(env, manifest(env, kind="WMS", damaged=2, **conflict_delivery)).status_code
                == 200
            )
            pump(env)
        observation = {"case": mode}
        report["investigation_cases"].append(observation)
        observation["automatic_refresh_runs"] = [
            r
            for r in get(api, f"/cases/{case['id']}/investigations").json()
            if r["provider"] == "deterministic"
        ]
        if existing is not None and mode != "missing":
            assert any(
                r["status"] == "COMPLETED" and not r["is_stale"]
                for r in observation["automatic_refresh_runs"]
            ), observation["automatic_refresh_runs"]
        started = time.perf_counter_ns()
        response = start(env, case, claim, allow_external=True)
        assert response.status_code == 200
        identifier = response.json()["id"]
        assert run(env, identifier) == "DELIVERED"
        observation["elapsed_ns"] = time.perf_counter_ns() - started
        observation["run"] = get(api, f"/investigations/{identifier}").json()
        observation["findings"] = get(api, f"/investigations/{identifier}/findings").json()
        trace = get(api, f"/investigations/{identifier}/trace").json()
        observation["trace"] = trace
        ai = [t for t in trace if t["node"] == "investigator_synthesize"]
        observation["fallback"] = not ai or ai[0]["metadata"].get("fallback", True)
        observation["financial_nonmutation"] = financial_state(api) == before
        with Session(engine) as session:
            observation["provider_replies"] = []
            for result in session.scalars(
                select(InvestigationResult).where(
                    InvestigationResult.organization_id == org,
                    InvestigationResult.run_id == UUID(identifier),
                )
            ):
                value = result.value.get("result", {})
                if "reply" in value:
                    ARReply.model_validate(value["reply"])
                    observation["provider_replies"].append(
                        {"phase": value["phase"], "reply": value["reply"]}
                    )
            reservations = list(
                session.scalars(
                    select(ProviderReservation).where(ProviderReservation.organization_id == org)
                )
            )
            assert len(reservations) <= report["maximum_attempts"]
            report["reserved_provider_attempts"] = len(reservations)
            report["conservative_consumed_paise"] = len(reservations) * report.get(
                "attempt_cost_cap_paise", 30
            )
            report["remaining_authorized_paise"] = (
                report["remaining_authorized_cap_paise"] - report["conservative_consumed_paise"]
            )
            for model in (
                CashAllocation,
                NoncashSettlement,
                LedgerJournal,
                LedgerLine,
                AccountBalance,
                FinanceApproval,
            ):
                assert (
                    session.scalar(
                        select(func.count()).select_from(model).where(model.organization_id == org)
                    )
                    == 0
                )
        observation["no_allocations_settlements_journals_or_approvals"] = True
        observation["end_to_end_ns"] = time.perf_counter_ns() - case_started
        assert observation["financial_nonmutation"]
        if observation["fallback"]:
            report["stopped"] = "INVESTIGATOR_SAFE_FALLBACK"
            break
        synthesis = ai[0]["metadata"]["synthesis"]
        expected = {
            "missing": ("INSUFFICIENT_EVIDENCE", "REQUEST_EVIDENCE"),
            "supported": ("SUPPORTED", "HUMAN_REVIEW"),
            "conflict": ("CONFLICTING_EVIDENCE", "ESCALATE_CONFLICT"),
        }[mode]
        observation["expected_result_correct"] = (
            synthesis["state"],
            synthesis["next_action"],
        ) == expected
        assert observation["expected_result_correct"]
        assert observation["findings"][0]["requires_human_review"]
        assert not observation["findings"][0]["financial_authority"]
        print(
            "Investigator synthetic case:",
            mode,
            synthesis["state"],
            synthesis["next_action"],
            flush=True,
        )
    return len(report["investigation_cases"]) == 3 and not report.get("stopped")
