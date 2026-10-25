"""Review credentials and immutable draft history survive real API/owned PG restarts."""

from uuid import uuid4

import pytest
from test_finance import prepared
from test_restart_persistence import restart_owned_container, running_api, tenant_rows
from test_review import FINANCIAL, RECORDS, draft_body, local_user, review
from test_review import documents_environment as documents_environment
from test_review import environment as environment

from clearledger.db import build_engine


@pytest.mark.postgres
def test_review_survives_process_and_owned_container_restart(
    documents_environment, request, monkeypatch
):
    env = documents_environment
    case, claims, _, _ = prepared(env, tax=False)
    credential = local_user(env)
    body = draft_body(env, case, claims)
    key = uuid4()
    created = review(env, case, "draft-evidence-request", body, key=key, credential=credential)
    assert created.status_code == 200, created.text
    settings = env[3].app.state.settings
    monkeypatch.setenv("REVIEW_DEMO_ENABLED", "true")
    monkeypatch.setenv("DOCUMENT_ROOT", str(settings.document_root))
    monkeypatch.setenv(
        "EVIDENCE_TRUSTED_SOURCES_JSON", settings.evidence_trusted_sources_json.get_secret_value()
    )
    url = env[0].url.render_as_string(hide_password=False)
    before = tenant_rows(env[0], env[1], (*RECORDS, *FINANCIAL))
    with running_api(url, env[1]) as (client, first_pid):
        assert client.get("/review/me", headers=credential).status_code == 200
        assert client.get("/finance/journals", headers=credential).status_code == 503
    env[0].dispose()
    container = request.config.getoption("--isolated-restart-container")
    if container:
        restart_owned_container(container)
    fresh = build_engine(url)
    try:
        assert tenant_rows(fresh, env[1], (*RECORDS, *FINANCIAL)) == before
        with running_api(url, env[1]) as (client, second_pid):
            assert second_pid != first_pid
            replay = client.post(
                f"/cases/{case['id']}/draft-evidence-request",
                json=body,
                headers={**credential, "Idempotency-Key": str(key)},
            )
            assert replay.status_code == 200 and replay.json() == created.json(), replay.text
            assert tenant_rows(fresh, env[1], (*RECORDS, *FINANCIAL)) == before
            current = env[3].get(f"/cases/{case['id']}", headers=credential)
            assert current.status_code == 200, current.text
            assert current.json()["version"] == case["version"]
    finally:
        fresh.dispose()
