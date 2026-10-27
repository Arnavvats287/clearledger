"""Three source states of one approved minimal AR fixture; no direct model calls."""

import time

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
from clearledger.models import ProviderReservation


def campaign(api, engine, org, settings, report):
    settings.extraction_provider = "disabled"
    env = engine, org, None, api, api
    assert api.app.state.finance_identity_verifier is None
    # Existing deterministic extraction fixture; no new LLM extraction or fake AI output.
    case, claim = fixture_case(
        env, amount="1.00", original_amount_paise="1000", open_amount_paise="1000"
    )
    before = financial_state(api)
    settings.investigation_provider = "gemini"
    settings.investigation_external_enabled = True
    settings.investigation_limits = settings.investigation_limits.model_copy(
        update={
            "max_claims": 1,
            "max_attempts": 1,
            "timeout_ms": 120000,
            "max_spend_paise": 60,
            "max_input_tokens": 6144,
            "max_output_tokens": 1024,
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
        if mode == "supported":
            for kind in ("WMS", "POD"):
                assert register(env, manifest(env, kind=kind, damaged=1)).status_code == 200
            pump(env)
        elif mode == "conflict":
            assert register(env, manifest(env, kind="WMS", damaged=2)).status_code == 200
            pump(env)
        observation = {"case": mode}
        report["investigation_cases"].append(observation)
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
            reservations = list(
                session.scalars(
                    select(ProviderReservation).where(ProviderReservation.organization_id == org)
                )
            )
            assert len(reservations) <= 4
            report["reserved_provider_attempts"] = len(reservations)
            report["conservative_consumed_paise"] = len(reservations) * 30
            report["remaining_authorized_paise"] = (
                report["remaining_authorized_cap_paise"] - len(reservations) * 30
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
