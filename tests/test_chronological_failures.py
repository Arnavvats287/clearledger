"""Application-owned synthetic failures. No operator inputs or benchmark answers."""

import base64
import json
import sys
import time
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from test_chronological_evaluation import message
from test_chronological_evaluation import owner_url as owner_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chronological_adapter as module  # noqa: E402
import chronological_host as host  # noqa: E402
from application_eval_inputs import sha  # noqa: E402
from chronological_adapter import Adapter  # noqa: E402
from chronological_diagnostics import WorkerFailure, diagnostic, route  # noqa: E402
from chronological_protocol import Stage, canonical  # noqa: E402


def empty_adapter(tmp_path, monkeypatch):
    """Isolated unit doubles; these observations never enter benchmark outputs."""
    m = message(inputs={})
    a = Adapter("unused", tmp_path / "private")
    a.output.mkdir()
    a.binding = (m["run_id"], m["company"], "dev")
    a.engine = object()
    a.org, a.env = uuid4(), {}
    a.api = SimpleNamespace(
        observations=[], calls=[], remaining=lambda: 10, collection=lambda _: []
    )

    def request(method, path):
        call = {"method": method, "path": path, "status": 503, "elapsed_ns": 1}
        a.api.calls.append(call)
        a.api.observations.append({**call, "response": {"detail": "unit authority unavailable"}})
        return SimpleNamespace(status_code=503)

    a.api.request = request
    monkeypatch.setattr(module, "rows", lambda *args: {})
    monkeypatch.setattr(module, "documents", lambda *args: {})
    monkeypatch.setattr(module, "drain_owned", lambda *args: 0)
    return a, m


def retained(a, m, response):
    path = a.output / m["request"]["request_id"] / "observations.json"
    raw = path.read_bytes()
    assert sha(raw) == response["raw_observation_sha256"]
    assert response["api_observations"]["raw_provenance"] == "RETAINED"
    return json.loads(raw)


def test_partial_api_failure_retained_in_canonical_stage_path_without_diagnostic_secrets(
    tmp_path, monkeypatch, capsys
):
    a, m = empty_adapter(tmp_path, monkeypatch)
    secret = "PRIVATE_ACCOUNT_DOCUMENT_AND_API_KEY"

    def fail(api, *args):
        api.calls.append(
            {
                "method": "GET",
                "path": "/documents/" + secret + "/text",
                "status": 422,
                "elapsed_ns": 1,
            }
        )
        api.observations.append({**api.calls[-1], "response": {"detail": secret}})
        raise RuntimeError(secret)

    monkeypatch.setattr(module, "documents", fail)
    response = a.stage(Stage(m))
    assert response["status"] == "ERROR" and a.poisoned
    assert response["financial_mutation_check"] == "NOT_EVALUABLE"
    assert set(response["prediction"]) == {"receipt", "as_of"}
    raw = retained(a, m, response)
    assert raw["calls"] == a.api.observations and raw["complete"] is False
    assert raw["calls"][0]["response"]["detail"] == secret  # Actual unit response, private only.
    safe = response["api_observations"]["diagnostic"]
    assert safe["component"] == "documents" and safe["exception_type"] == "RuntimeError"
    assert safe["source"]["file"] == "scripts/chronological_adapter.py"
    assert type(safe["source"]["line"]) is int
    public = canonical(response["api_observations"]).decode() + capsys.readouterr().err
    assert secret not in public and str(tmp_path) not in public
    assert response["api_observations"]["recent_http"][0]["route"] == "/documents/{id}/text"


def test_storage_exhaustion_uses_reserved_space_without_raising_total_cap(tmp_path, monkeypatch):
    a, m = empty_adapter(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "MAX_ARTIFACT_BYTES", 1024 * 1024)
    a.artifact_bytes = module.MAX_ARTIFACT_BYTES - module.MAX_ARTIFACT_BYTES // 16
    response = a.stage(Stage(m))
    assert response["status"] == "ERROR"
    assert response["api_observations"]["diagnostic"]["code"] == "PRIVATE_PROVENANCE_STORAGE_BUDGET"
    assert response["api_observations"]["diagnostic"]["component"] == "persist_observations"
    assert retained(a, m, response)["calls"] == a.api.observations
    assert a.artifact_bytes <= module.MAX_ARTIFACT_BYTES


def test_failure_after_observations_keeps_the_original_valid_hash(tmp_path, monkeypatch):
    a, m = empty_adapter(tmp_path, monkeypatch)
    original = a.save

    def fail_response(path, raw, **kwargs):
        if path.name == "response.json" and not kwargs.get("emergency"):
            raise RuntimeError("PRIVATE_PROVENANCE_STORAGE_BUDGET")
        return original(path, raw, **kwargs)

    monkeypatch.setattr(a, "save", fail_response)
    response = a.stage(Stage(m))
    raw = retained(a, m, response)
    assert "records" in raw and raw["calls"] == a.api.observations
    assert response["status"] == "ERROR" and "capabilities" not in response
    assert response["api_observations"]["diagnostic"]["component"] == "persist_response"


def test_real_storage_failure_never_fabricates_a_hash(tmp_path, monkeypatch, capsys):
    a, m = empty_adapter(tmp_path, monkeypatch)

    def unavailable(*args, **kwargs):
        raise OSError("PRIVATE_VOLUME_AND_CREDENTIAL")

    monkeypatch.setattr(a, "save", unavailable)
    response = a.stage(Stage(m))
    assert response["status"] == "ERROR" and "raw_observation_sha256" not in response
    assert response["api_observations"]["raw_provenance"] == "UNAVAILABLE"
    assert "PRIVATE_VOLUME_AND_CREDENTIAL" not in capsys.readouterr().err


def test_conflicting_request_cannot_reuse_or_modify_old_provenance(tmp_path, monkeypatch):
    a, m = empty_adapter(tmp_path, monkeypatch)
    first = a.stage(Stage(m))
    path = a.output / m["request"]["request_id"] / "observations.json"
    original = path.read_bytes()
    m["request"]["as_of"] = "2026-01-20T12:00:00+05:30"
    failure = a.stage(Stage(m))
    assert failure["status"] == "ERROR" and "raw_observation_sha256" not in failure
    assert path.read_bytes() == original and sha(original) == first["raw_observation_sha256"]


def test_diagnostic_does_not_reflect_unknown_exception_class_or_message():
    private = type("PRIVATE_CUSTOMER_ACCOUNT", (Exception,), {"__module__": "untrusted"})
    value = diagnostic(private("PRIVATE_PASSWORD"), "documents")
    assert value == {
        "component": "documents",
        "exception_type": "Exception",
        "code": "UNCLASSIFIED_FAILURE",
        "source": None,
    }
    assert route("/receipts/PRIVATE_BANK_KEY/match?token=PRIVATE") == "/receipts/{id}/match"


def test_transport_error_records_only_a_failed_attempt_without_body_or_credentials():
    def fail(request):
        raise httpx.ReadTimeout("PRIVATE_URL_TOKEN_PASSWORD", request=request)

    with httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(fail)) as client:
        api = host.BoundedAPI(client, "PRIVATE_LOGIN_PASSWORD", str(uuid4()))
        api.token, api.logged_at = "PRIVATE_SESSION_TOKEN", time.monotonic()
        with pytest.raises(httpx.ReadTimeout):
            api.request("GET", "/receipts/PRIVATE_BANK_KEY/matching-context?token=PRIVATE")
        assert api.calls == [] and len(api.observations) == 1
        observation = api.observations[0]
        assert observation["status"] is None and "response" not in observation
        assert observation["failure"]["exception_type"] == "ReadTimeout"
        assert "PRIVATE" not in canonical(observation).decode()


def test_worker_emits_only_structured_content_free_failure(monkeypatch, capsys):
    def fail():
        raise RuntimeError("PRIVATE_DATABASE_URL_PASSWORD")

    monkeypatch.setattr(host, "frozen_settings", fail)
    assert host.worker_main() == 1
    output = capsys.readouterr()
    assert output.out == "" and "PRIVATE_DATABASE_URL_PASSWORD" not in output.err
    value = json.loads(output.err)["worker_error"]
    assert value["component"] == "worker" and value["exception_type"] == "RuntimeError"
    assert value["source"]["file"] == "scripts/chronological_host.py"


@pytest.mark.parametrize(
    "stderr", ["PRIVATE_CHILD_STDERR", '{"worker_error":{"secret":"PRIVATE"}}']
)
def test_parent_does_not_reflect_untrusted_worker_stderr(stderr, monkeypatch):
    engine = SimpleNamespace(connect=lambda: SimpleConnection())
    monkeypatch.setattr(
        host.subprocess, "run", lambda *args, **kwargs: CompletedProcess(args, 1, "", stderr)
    )
    with pytest.raises(WorkerFailure) as error:
        host.drain_owned(engine, uuid4(), {}, SimpleNamespace(remaining=lambda: 10))
    assert error.value.details is None
    assert "PRIVATE" not in canonical(diagnostic(error.value, "worker_after_documents")).decode()


class SimpleConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def scalars(self, query):
        return ["PENDING"]

    def execute(self, query):
        return [("PENDING", None)]


def test_parent_retains_valid_content_free_worker_diagnostic(monkeypatch):
    child = {
        "component": "worker",
        "exception_type": "RuntimeError",
        "code": "UNCLASSIFIED_FAILURE",
        "source": {"file": "src/clearledger/case_outbox.py", "line": 1, "function": "deliver"},
    }
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, 1, "", json.dumps({"worker_error": child})),
    )
    with pytest.raises(WorkerFailure) as error:
        host.drain_owned(
            SimpleNamespace(connect=lambda: SimpleConnection()),
            uuid4(),
            {},
            SimpleNamespace(remaining=lambda: 10),
        )
    assert diagnostic(error.value, "investigation_worker")["worker_failure"] == child


def test_outbox_failure_reports_only_fixed_codes_not_private_database_values():
    class Failed(SimpleConnection):
        def execute(self, query):
            return [("RETRY", "CASE_MEMBERSHIP_LIMIT"), ("DEAD", "PRIVATE_SOURCE_EXCEPTION")]

    with pytest.raises(WorkerFailure) as error:
        host.drain_owned(
            SimpleNamespace(connect=lambda: Failed()),
            uuid4(),
            {},
            SimpleNamespace(remaining=lambda: 10),
        )
    value = diagnostic(error.value, "worker_after_documents")
    assert value["worker_failure"] == {
        "states": {"RETRY": 1, "DEAD": 1},
        "error_codes": ["CASE_MEMBERSHIP_LIMIT", "UNKNOWN"],
    }
    assert "PRIVATE_SOURCE_EXCEPTION" not in canonical(value).decode()


@pytest.mark.postgres
def test_real_api_failure_after_success_keeps_partial_observations(owner_url, tmp_path, capsys):
    a = Adapter(owner_url, tmp_path / "private")
    first = message()
    try:
        success = a.stage(Stage(first))
        assert success["status"] == "ABSTAIN"
        later = message(run=first["run_id"], cutoff="2026-01-20T12:00:00+05:30")
        name = "app_visible/evidence_corpus/remittances/private_input.pdf"
        secret = b"%PDF-1.7\nPRIVATE_SOURCE_VALUE\n%%EOF"
        later["payload"][name] = base64.b64encode(secret).decode()
        later["manifest"][name] = sha(secret)
        later["files"] = [name]
        failure = a.stage(Stage(later))
        assert failure["status"] == "ERROR" and a.poisoned
        raw = retained(a, later, failure)
        assert raw["calls"] and any(c.get("status", 0) >= 400 for c in raw["calls"])
        assert failure["api_observations"]["diagnostic"]["exception_type"] == "RuntimeError"
        public = canonical(failure["api_observations"]).decode() + capsys.readouterr().err
        assert "PRIVATE_SOURCE_VALUE" not in public and "private_input.pdf" not in public
        assert failure["financial_mutation_check"] == "NOT_EVALUABLE"
        old = a.output / first["request"]["request_id"] / "observations.json"
        assert sha(old.read_bytes()) == success["raw_observation_sha256"]
    finally:
        a.close()
