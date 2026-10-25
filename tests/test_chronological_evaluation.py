"""Isolated protocol/API fixtures, not benchmark data or hidden stage schedules."""

import base64
import copy
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import create_engine, text
from test_imports import ALIAS, BANK, CUSTOMER, INVOICE, csv_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from application_eval_inputs import IMPORTS, sha  # noqa: E402
from chronological_adapter import Adapter  # noqa: E402
from chronological_protocol import Deltas, Stage, allowed, canonical, strict_json  # noqa: E402
from chronological_resources import owned_database  # noqa: E402

CUTOFF = "2026-01-19T12:00:00+05:30"


def message(*, run=None, transaction="t", inputs=None, cutoff=CUTOFF):
    if inputs is None:
        inputs = {
            f"imports/{k}.csv": csv_bytes(k, r)
            for k, r in zip(
                IMPORTS,
                (CUSTOMER, ALIAS, INVOICE, {**BANK, "payer_name": "Test Alias"}),
                strict=True,
            )
        }
    return {
        "request": {
            "split": "dev",
            "transaction": {
                "source_system": BANK["source_system"],
                "account_ref": BANK["account_ref"],
                "external_transaction_id": transaction,
            },
            "as_of": cutoff,
            "request_id": str(uuid4()),
            "snapshot_id": str(uuid4()),
        },
        "manifest": {k: sha(v) for k, v in inputs.items()},
        "files": list(inputs),
        "company": "isolated-unit",
        "run_id": run or str(uuid4()),
        "nonce": str(uuid4()),
        "payload": {k: base64.b64encode(v).decode() for k, v in inputs.items()},
    }


def test_utf8_canonical_manifest_and_exact_cutoff_binding():
    stage = Stage(message())
    assert canonical({"z": "é", "a": 1}) == b'{"a":1,"z":"\xc3\xa9"}'
    assert stage.envelope()["prediction"]["as_of"] == CUTOFF
    assert stage.envelope()["prediction"]["receipt"] == stage.request["transaction"]
    assert stage.envelope()["input_manifest_sha256"] == sha(canonical(stage.manifest))


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_json_ambiguity_rejected(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


@pytest.mark.parametrize(
    "name",
    [
        "../a",
        "/imports/customers.csv",
        "C:/a",
        "imports//customers.csv",
        "imports/../customers.csv",
        "imports\\customers.csv",
        "hidden_ground_truth/a.json",
        "app_visible/evidence_corpus/sidecars/a.json",
        "schedule.json",
        "generator.py",
        "app_visible/correlation_sources/unsafe\n.json",
    ],
)
def test_forbidden_inputs(name):
    assert not allowed(name)
    with pytest.raises(ValueError):
        Stage(message(inputs={name: b"x"}))


@pytest.mark.parametrize("change", ["hash", "payload", "files", "split", "naive", "extra"])
def test_protocol_tamper(change):
    m = message()
    if change == "hash":
        m["manifest"]["imports/customers.csv"] = "0" * 64
    elif change == "payload":
        m["payload"].pop("imports/customers.csv")
    elif change == "files":
        m["files"].append("unknown")
    elif change == "split":
        m["request"]["split"] = "eval"
    elif change == "naive":
        m["request"]["as_of"] = "2026-01-01T00:00:00"
    else:
        m["answers"] = {}
    with pytest.raises(ValueError):
        Stage(m)


def test_cumulative_delta_immutable_keys_no_blank_api_imports():
    delta = Deltas()
    m = message()
    plan = delta.plan(Stage(m))
    assert {k: p[1] for k, p in plan[0].items()} == dict.fromkeys(IMPORTS, 1)
    delta.commit(plan)
    assert delta.plan(Stage(m))[0] == {}
    changed = message(
        inputs={"imports/customers.csv": csv_bytes("customers", {**CUSTOMER, "name": "Changed"})}
    )
    with pytest.raises(ValueError, match="CHANGED_NATURAL"):
        delta.plan(Stage(changed))
    with pytest.raises(ValueError, match="REMOVED"):
        delta.plan(Stage(message(inputs={"imports/customers.csv": csv_bytes("customers")})))
    assert (
        Deltas().plan(Stage(message(inputs={"imports/customers.csv": csv_bytes("customers")})))[0]
        == {}
    )


def test_document_changes_and_future_records_rejected():
    delta = Deltas()
    name = "app_visible/correlation_sources/unit.json"
    delta.commit(delta.plan(Stage(message(inputs={name: b"{}"}))))
    with pytest.raises(ValueError, match="CHANGED_OR_REMOVED"):
        delta.plan(Stage(message(inputs={name: b"{ }"})))
    with pytest.raises(ValueError, match="FUTURE_SOURCE_ROW"):
        Deltas().plan(
            Stage(
                message(
                    inputs={
                        "imports/bank-transactions.csv": csv_bytes(
                            "bank-transactions", {**BANK, "occurred_at": "2026-01-20T00:00:00Z"}
                        )
                    }
                )
            )
        )


@given(
    st.lists(st.text(alphabet="abcdef012345", min_size=1, max_size=10), unique=True, max_size=30)
)
def test_delta_additions_independent_set_invariant(keys):
    delta = Deltas()
    for end in range(len(keys) + 1):
        raw = csv_bytes(
            "customers", *[{"external_reference": k, "name": "Unit"} for k in keys[:end]]
        )
        plan = delta.plan(Stage(message(inputs={"imports/customers.csv": raw})))
        assert sum(value[1] for value in plan[0].values()) == (1 if end else 0)
        delta.commit(plan)
        assert set(delta.accepted["customers"]) == {(k,) for k in keys[:end]}


@pytest.fixture
def owner_url():
    configured = os.environ.get("TEST_DATABASE_URL")
    if not configured:
        pytest.fail("TEST_DATABASE_URL required; chronological tests must not skip")
    with owned_database(configured) as url:
        yield url.render_as_string(hide_password=False)


@pytest.mark.postgres
def test_real_persistent_api_deltas_ties_replay_evidence_and_nonmutation(owner_url, tmp_path):
    from clearledger.models import SourceImport

    m = message()
    adapter = Adapter(owner_url, tmp_path / "private")
    try:
        first = adapter.stage(Stage(m))
        assert first["status"] == "ABSTAIN", first
        assert first["financial_mutation_check"] == "PASS"
        assert first["api_observations"]["receipt_available"]
        assert first["api_observations"]["evidence_queries"] == 1
        assert first["prediction"]["abstain_invoice_allocation"]
        engine_id, client_id = id(adapter.engine), id(adapter.api.client)
        count = len(adapter.api.calls)
        assert adapter.stage(Stage(m)) == first
        assert len(adapter.api.calls) == count
        retried = copy.deepcopy(m)
        retried["nonce"] = str(uuid4())
        retried["files"] = []
        rebound = adapter.stage(Stage(retried))
        assert rebound == {**first, "nonce": retried["nonce"]}
        assert len(adapter.api.calls) == count
        tied = copy.deepcopy(m)
        tied["request"].update(request_id=str(uuid4()), snapshot_id=str(uuid4()))
        tied["nonce"] = str(uuid4())
        result = adapter.stage(Stage(tied))
        assert result["status"] == "ABSTAIN" and not result["api_observations"]["imports"]
        later = message(run=m["run_id"], cutoff="2026-01-20T12:00:00+05:30")
        raw = csv_bytes(
            "bank-transactions",
            {**BANK, "payer_name": "Test Alias"},
            {**BANK, "external_transaction_id": "t2"},
        )
        later["payload"]["imports/bank-transactions.csv"] = base64.b64encode(raw).decode()
        later["manifest"]["imports/bank-transactions.csv"] = sha(raw)
        docname = "app_visible/correlation_sources/unit.json"
        raw_doc = canonical(
            {
                "remittance_version": "1.0",
                "invoice_references": ["i"],
                "utr_references": ["t"],
                "payer_hint": None,
                "claims": [{"category": "damage", "amount_paise": 2, "reason_code": "damage"}],
            }
        )
        later["payload"][docname] = base64.b64encode(raw_doc).decode()
        later["manifest"][docname] = sha(raw_doc)
        later["files"] = ["imports/bank-transactions.csv", docname]
        response = adapter.stage(Stage(later))
        assert response["status"] == "ABSTAIN", response
        assert response["financial_mutation_check"] == "PASS"
        assert response["api_observations"]["imports"] == [
            {"kind": "bank-transactions", "new_rows": 1}
        ]
        assert response["api_observations"]["documents"][0]["route"] == "DETERMINISTIC"
        assert response["api_observations"]["investigation_requests"] == 1
        assert id(adapter.engine) == engine_id and id(adapter.api.client) == client_id
        with adapter.engine.connect() as connection:
            imports = connection.execute(SourceImport.__table__.select()).mappings().all()
        assert len(imports) == 5 and sum(i["row_count"] for i in imports) == 5
        # Original stage remains immutable despite later source/case state.
        assert adapter.stage(Stage(m)) == first
        assert len(adapter.api.collection("/receipts")) == 2
        assert len(list((tmp_path / "private").glob("*/response.json"))) == 3
    finally:
        adapter.close()
    # Even clean EOF never permits a new run to reuse a prior database.
    from chronological_host import initialize_owned

    with pytest.raises(ValueError, match="PRIOR_RUN"):
        initialize_owned(owner_url, "unit", str(uuid4()))


@pytest.mark.postgres
def test_admin_database_rejected_before_migrations(disposable_database):
    from chronological_host import initialize_owned

    with pytest.raises(ValueError, match="FRESH_UNPRIVILEGED"):
        initialize_owned(disposable_database, "unit", str(uuid4()))
    engine = create_engine(disposable_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'"))
                == 0
            )
    finally:
        engine.dispose()


@pytest.mark.postgres
@pytest.mark.parametrize(
    "mode", ["administrator", "membership", "prior_function", "prior_view", "prior_schema"]
)
def test_owner_role_and_pristine_schema_guards(owner_url, mode):
    from chronological_host import initialize_owned
    from sqlalchemy.engine import make_url

    owner = make_url(owner_url)
    admin = make_url(os.environ["TEST_DATABASE_URL"])
    url = owner
    expected = "FRESH_UNPRIVILEGED"
    engine = create_engine(admin.set(database=owner.database), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            if mode == "administrator":
                url = admin.set(database=owner.database)
            elif mode == "membership":
                # Generated role identifier from the trusted disposable bootstrap.
                connection.execute(text(f'GRANT pg_read_all_data TO "{owner.username}"'))
            elif mode == "prior_function":
                connection.execute(
                    text(
                        "CREATE FUNCTION public.untrusted() RETURNS integer "
                        "LANGUAGE SQL AS 'SELECT 1'"
                    )
                )
                expected = "PRIOR_RUN"
            elif mode == "prior_view":
                connection.execute(text("CREATE VIEW public.prior AS SELECT 1 AS value"))
                expected = "PRIOR_RUN"
            else:
                connection.execute(text('CREATE SCHEMA "pgXprior"'))
                expected = "PRIOR_RUN"
        with pytest.raises(ValueError, match=expected):
            initialize_owned(url, "unit", str(uuid4()))
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_real_jsonl_stdout_only_and_clean_eof_persistence(owner_url, tmp_path):
    m = message()
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "TEMP", "TMP"}
    }
    env.update(DATABASE_URL=owner_url, PYTHONUTF8="1", CL_ADAPTER_OUTPUT=str(tmp_path / "private"))
    wire = canonical(m).decode() + "\n"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/chronological_adapter.py"],
        input=wire * 2,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    responses = [strict_json(line) for line in result.stdout.splitlines()]
    assert len(responses) == 2 and responses[0] == responses[1]
    assert responses[0]["status"] == "ABSTAIN"
    assert responses[0]["financial_mutation_check"] == "PASS"
    assert len(list((tmp_path / "private/input-objects").iterdir())) == 4
    # Fresh connection after the entire application/adapter session exited normally.
    engine = create_engine(owner_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM receipts")) == 1
            assert (
                connection.scalar(text("SELECT sum(unapplied_amount_paise) FROM receipts")) == 100
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("change", ["regression", "company", "snapshot", "conflict", "tie"])
def test_session_conflicts_fail_closed_before_database(change, tmp_path):
    m = message()
    stage = Stage(m)
    adapter = Adapter("not-a-database", tmp_path / "unused")
    adapter.binding = (m["run_id"], m["company"], "dev")
    adapter.cutoff = stage.cutoff
    adapter.manifest_hash = sha(canonical(stage.manifest))
    if change == "regression":
        m["request"]["as_of"] = "2026-01-18T00:00:00Z"
    elif change == "company":
        m["company"] = "other"
    elif change == "snapshot":
        adapter.snapshots[m["request"]["snapshot_id"]] = "other-request"
    elif change == "conflict":
        adapter.requests[m["request"]["request_id"]] = ("conflict", {})
    else:
        m["manifest"] = {}
        m["payload"] = {}
        m["files"] = []
    response = adapter.stage(Stage(m))
    assert response["status"] == "ERROR" and adapter.poisoned
    assert set(response["prediction"]) == {"receipt", "as_of"}
    assert adapter.stage(stage)["api_observations"]["error"] == "RUN_FAILED_DISCARD_DATABASE"


def test_frozen_settings_ignore_dotenv_and_deny_external(monkeypatch, tmp_path):
    from chronological_host import frozen_settings, host_environment

    (tmp_path / ".env").write_text("EXTERNAL_AI_ENABLED=true\nGEMINI_API_KEY=secret\n")
    monkeypatch.chdir(tmp_path)
    env = host_environment("postgresql+psycopg://u:p@localhost/d", uuid4(), tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert not frozen_settings().external_ai_enabled
    monkeypatch.setenv("EXTERNAL_AI_ENABLED", "true")
    with pytest.raises(ValueError, match="MISMATCH"):
        frozen_settings()


def test_jsonl_malformed_input_stdout_empty_and_no_secret_echo():
    result = subprocess.run(
        [sys.executable, "scripts/chronological_adapter.py"],
        input='{"secret":"do-not-echo"}\n',
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2 and result.stdout == ""
    assert "do-not-echo" not in result.stderr


def test_current_payload_consumption_never_opens_an_input_root(monkeypatch):
    m = message()
    monkeypatch.setenv("CL_INPUT_ROOT", "C:/never-open-an-operator-root")

    def forbidden(*args, **kwargs):
        raise AssertionError("No source filesystem reads permitted")

    monkeypatch.setattr(Path, "open", forbidden)
    plan = Deltas().plan(Stage(m))
    assert sum(value[1] for value in plan[0].values()) == 4


@pytest.mark.parametrize("error", [TimeoutError, RuntimeError])
def test_api_failure_timeout_minimal_bound_response_poisoned_run(error, monkeypatch, tmp_path):
    adapter = Adapter("not-used", tmp_path / "unused")

    def fail(stage):
        raise error("secret-credentials-must-not-be-reflected")

    monkeypatch.setattr(adapter, "start", fail)
    m = message()
    result = adapter.stage(Stage(m))
    assert result["status"] == "ERROR"
    assert result["financial_mutation_check"] == "NOT_EVALUABLE"
    assert result["prediction"] == {
        "receipt": m["request"]["transaction"],
        "as_of": m["request"]["as_of"],
    }
    assert "secret-credentials" not in canonical(result).decode()
    assert "capabilities" not in result and adapter.poisoned
    assert adapter.stage(Stage(m))["api_observations"]["error"] == "RUN_FAILED_DISCARD_DATABASE"


def test_bounded_api_deadline_prevents_even_login(monkeypatch):
    from chronological_host import BoundedAPI

    api = BoundedAPI(None, "not-visible", str(uuid4()))
    monkeypatch.setattr("chronological_host.time.monotonic", lambda: api.deadline + 1)
    with pytest.raises(TimeoutError, match="DEADLINE"):
        api.request("GET", "/customers")
    assert api.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///must-not-create.db",
        "postgresql+psycopg://owner:p@localhost/development",
        "postgresql+psycopg://admin:p@localhost/clearledger_chrono_" + "a" * 32 + "?options=x",
    ],
)
def test_database_boundary_rejects_before_any_connection(url, monkeypatch):
    import chronological_host

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid runner URLs must not be opened")

    monkeypatch.setattr(chronological_host, "create_engine", forbidden)
    with pytest.raises(ValueError, match="FRESH_UNPRIVILEGED"):
        chronological_host.initialize_owned(url, "unit", str(uuid4()))


def test_private_provenance_is_exclusive_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr("chronological_adapter.MAX_ARTIFACT_BYTES", 4)
    adapter = Adapter("not-used", tmp_path)
    adapter.save(tmp_path / "original", b"ab")
    with pytest.raises(FileExistsError):
        adapter.save(tmp_path / "original", b"x")
    assert (tmp_path / "original").read_bytes() == b"ab"
    with pytest.raises(RuntimeError, match="STORAGE_BUDGET"):
        adapter.save(tmp_path / "excess", b"abc")
    assert not (tmp_path / "excess").exists()


@pytest.mark.parametrize("bad", ["header", "float", "duplicate", "removed"])
def test_delta_rejects_invalid_contract_or_removed_keys(bad):
    delta = Deltas()
    if bad == "header":
        raw = b"external_reference,name,extra\nc,Test,x\n"
    elif bad == "float":
        raw = csv_bytes("invoices", {**INVOICE, "original_amount_paise": "1.01"})
        with pytest.raises(ValueError, match="INVALID_CONTRACT"):
            delta.plan(Stage(message(inputs={"imports/invoices.csv": raw})))
        return
    elif bad == "duplicate":
        raw = csv_bytes("customers", CUSTOMER, {**CUSTOMER, "name": "Conflict"})
    else:
        delta.commit(delta.plan(Stage(message())))
        raw = csv_bytes("customers")
    with pytest.raises(ValueError):
        delta.plan(Stage(message(inputs={"imports/customers.csv": raw})))
