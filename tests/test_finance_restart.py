"""Real-process/restart proof with an explicit test-only identity host."""

from pathlib import Path
from uuid import uuid4

import pytest
from test_finance import FixtureIdentities, approved, command, headers
from test_finance import documents_environment as documents_environment
from test_finance import environment as environment
from test_restart_persistence import restart_owned_container, running_api, tenant_rows

from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.finance_models import (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    FinanceAudit,
    FinanceCommand,
    FinancePolicy,
    FinanceProposal,
    FinanceProposalEvent,
    FinanceSourceReview,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
)
from clearledger.main import create_app as production_app
from clearledger.models import Invoice, Receipt

MODELS = (
    AccountBalance,
    CashAllocation,
    FinanceApproval,
    FinanceAudit,
    FinanceCommand,
    FinancePolicy,
    FinanceProposal,
    FinanceProposalEvent,
    FinanceSourceReview,
    LedgerJournal,
    LedgerLine,
    NoncashSettlement,
    Invoice,
    Receipt,
)


def create_app():
    """Only this tests/ module supplies fixture identities. Production never loads it."""
    settings = Settings()
    app = production_app(settings)
    app.state.finance_identity_verifier = FixtureIdentities(settings.organization_id)
    return app


@pytest.mark.postgres
def test_financial_post_survives_process_and_owned_container_restart(
    documents_environment, request, monkeypatch
):
    env = documents_environment
    _, _, proposal, _, _ = approved(env)
    settings = env[3].app.state.settings
    monkeypatch.setenv("DOCUMENT_ROOT", str(settings.document_root))
    monkeypatch.setenv(
        "EVIDENCE_TRUSTED_SOURCES_JSON", settings.evidence_trusted_sources_json.get_secret_value()
    )
    url = env[0].url.render_as_string(hide_password=False)
    factory = {"factory": "test_finance_restart:create_app", "pythonpath": Path(__file__).parent}
    key = uuid4()
    with running_api(url, env[1], **factory) as (client, first_pid):
        response = client.post(
            f"/journal-proposals/{proposal['id']}/simulate-post",
            json=command(proposal),
            headers=headers("poster", key),
        )
        assert response.status_code == 200, response.text
        output = response.json()
        before = tenant_rows(env[0], env[1], MODELS)
        journals = client.get("/finance/journals", headers=headers("auditor")).json()
        assert len(journals) == 2
    env[0].dispose()
    container = request.config.getoption("--isolated-restart-container")
    if container:
        restart_owned_container(container)
    fresh = build_engine(url)
    try:
        assert tenant_rows(fresh, env[1], MODELS) == before
        with running_api(url, env[1], **factory) as (client, second_pid):
            assert second_pid != first_pid
            assert client.get("/finance/journals", headers=headers("auditor")).json() == journals
            replay = client.post(
                f"/journal-proposals/{proposal['id']}/simulate-post",
                json=command(proposal),
                headers=headers("poster", key),
            )
            assert replay.status_code == 200 and replay.json() == output
            assert tenant_rows(fresh, env[1], MODELS) == before
            assert client.get("/invoices").json()[0]["open_amount_paise"] == 250000
            assert client.get("/receipts").json()[0]["unapplied_amount_paise"] == 0
    finally:
        fresh.dispose()
