import os
import subprocess
import sys
from uuid import uuid4

import pytest
from test_documents import auth, extract, get, upload
from test_documents import documents_environment as documents_environment
from test_imports import CUSTOMER, INVOICE, post
from test_imports import environment as environment
from test_matching import setup

from clearledger.document_contract import (
    ExtractedClaim,
    ExtractionError,
    Reference,
    Span,
    empty_extraction,
    validate_semantics,
)


@pytest.mark.parametrize("gateway", [False, True])
def test_real_worker_guard_denies_files_tools_and_database_network(tmp_path, gateway):
    script = tmp_path / "guard_check.py"
    script.write_text(
        """
import socket, subprocess, sys
from clearledger.worker_security import install_guard
install_guard(allow_gemini=sys.argv[1] == "yes")
actions = [lambda: open(".env").read(),
           lambda: open("forbidden-worker-output", "w"),
           lambda: subprocess.Popen([sys.executable,"-c","print(1)"]),
           lambda: socket.create_connection(("127.0.0.1",5432),timeout=0.1)]
for action in actions:
    try:
        action()
    except PermissionError:
        continue
    raise AssertionError("A forbidden capability succeeded")
print("capabilities denied")
""",
        encoding="utf-8",
    )
    env = {
        k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(script), "yes" if gateway else "no"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "capabilities denied"


def test_real_sdk_with_mock_http_and_actual_worker_guard(tmp_path):
    script = tmp_path / "sdk_guard_check.py"
    script.write_text(
        """
import io,json,sys,httpx
from google import genai
from clearledger.gemini_worker import main
original = genai.Client
calls=[]
answer={"invoice_references":[],"utr_references":[],"payer_hint":None,"claims":[],
        "uncertainty":"unknown","unparsed_fields":[]}
def handle(request):
    assert request.url.host == "generativelanguage.googleapis.com"
    if request.method == "GET":
        calls.append(("get",str(request.url)))
        return httpx.Response(200,json={"name":"models/unit-model","version":"unit",
            "inputTokenLimit":8192,"outputTokenLimit":4096,
            "supportedGenerationMethods":["generateContent"]})
    payload=json.loads(request.content)
    if request.url.path.endswith(":countTokens"):
        calls.append(("count",payload))
        return httpx.Response(200,json={"totalTokens":100})
    calls.append(("generate",payload))
    return httpx.Response(200,json={"candidates":[{"content":{"parts":[
        {"text":json.dumps(answer)}],"role":"model"},"finishReason":"STOP"}],
        "usageMetadata":{"promptTokenCount":1,"candidatesTokenCount":2,"totalTokenCount":3}})
def factory(**kwargs):
    options=kwargs["http_options"]
    options.httpx_client=httpx.Client(transport=httpx.MockTransport(handle),trust_env=False)
    return original(**kwargs)
genai.Client=factory
request={"key":"unit-only-offline-key","model":"unit-model","timeout_ms":1000,
         "pages":["sanitized text"]}
sys.stdin=io.TextIOWrapper(io.BytesIO(json.dumps(request).encode()))
out=io.StringIO()
stdout=sys.stdout
sys.stdout=out
main()
sys.stdout=stdout
result=json.loads(out.getvalue())
assert json.loads(result.get("json_text","null")) == answer,(result,calls)
assert result["total_tokens"] == 3
assert [call[0] for call in calls]==["get","count","generate"]
assert calls[2][1]["generationConfig"]["responseMimeType"] == "application/json"
counted=calls[1][1]["generateContentRequest"]
assert counted.pop("model")=="models/unit-model"
assert counted==calls[2][1], (counted,calls[2][1])
print("official SDK and real guard: offline PASS")
""",
        encoding="utf-8",
    )
    env = {
        k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "offline PASS" in result.stdout


@pytest.mark.parametrize("invalid", ["\ud800", "\u0000"])
def test_invalid_unicode_or_controls_are_not_extraction_values(invalid):
    with pytest.raises(ValueError):
        Reference(value=invalid, span=Span(page=1, start=0, end=1, quote="x"))


@pytest.mark.postgres
def test_later_extraction_stales_association_and_blocks_old_result(documents_environment):
    _, _, _, client, _ = documents_environment
    receipt = setup(client)
    doc = upload(client).json()
    run = extract(client, doc["id"]).json()
    body = {
        "extraction_id": run["id"],
        "expected_document_version": 1,
        "verified_utr_values": ["t"],
        "expected_receipt_versions": {receipt: 1},
    }
    path = f"/documents/{doc['id']}/correlate"
    key = uuid4()
    assert client.post(path, json=body, headers=auth(key)).json()["status"] == "LINKED"
    assert extract(client, doc["id"], revision_label="recheck").json()["extraction_version"] == 2
    assert get(client, f"/documents/{doc['id']}/associations").json()[0]["is_stale"]
    assert client.post(path, json=body, headers=auth(key)).status_code == 409
    assert client.post(path, json=body, headers=auth()).json()["status"] == "CANDIDATES"


@pytest.mark.postgres
@pytest.mark.parametrize("known", [False, True])
def test_unverified_or_conflicting_invoice_owner_prevents_reference_link(
    documents_environment, known
):
    _, _, _, client, _ = documents_environment
    receipt = setup(client)
    if known:
        assert post(client, "customers", {**CUSTOMER, "external_reference": "d"}).status_code == 200
        assert (
            post(
                client, "invoices", {**INVOICE, "invoice_number": "x", "customer_reference": "d"}
            ).status_code
            == 200
        )
    doc = upload(client, b"INVOICE: x\nUTR: t").json()
    run = extract(client, doc["id"]).json()
    response = client.post(
        f"/documents/{doc['id']}/correlate",
        headers=auth(),
        json={
            "extraction_id": run["id"],
            "expected_document_version": 1,
            "verified_utr_values": ["t"],
            "expected_receipt_versions": {receipt: 1},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "CANDIDATES" and result["receipt_id"] is None
    assert result["result"]["reason"] == (
        "CONFLICTING_CUSTOMER_REFERENCES" if known else "UNKNOWN_INVOICE_REFERENCES"
    )


def test_verification_logs_redact_both_file_and_environment_secrets(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    source = Path(__file__).resolve().parents[1] / "scripts" / "verify.py"
    spec = importlib.util.spec_from_file_location("isolated_verify_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://unit-db-placeholder")
    monkeypatch.setenv("GEMINI_API_KEY", "CANARY_ENV_KEY_NOT_REAL")
    monkeypatch.setattr(
        module,
        "dotenv_values",
        lambda _: {
            "GEMINI_API_KEY": "CANARY_FILE_KEY_NOT_REAL",
            "DOCUMENT_API_TOKEN": "CANARY_DOC_TOKEN_NOT_REAL",
        },
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="CANARY_ENV_KEY_NOT_REAL CANARY_FILE_KEY_NOT_REAL CANARY_DOC_TOKEN_NOT_REAL",
            stderr="",
            returncode=0,
        ),
    )
    module.main()
    logs = list((tmp_path / "local-data" / "verification").glob("*.log"))
    assert len(logs) == 1
    contents = logs[0].read_text(encoding="utf-8")
    assert "CANARY_" not in contents and "<redacted>" in contents


@pytest.mark.parametrize(
    "source,quote,amount",
    [
        ("CLAIM damage: INR 1,000.00", "INR 1", 100),
        ("CLAIM damage: INR 1.001", "INR 1.00", 100),
        ("CLAIM damage: -1 paise", "1 paise", 1),
    ],
)
def test_partial_or_signed_amount_source_cannot_become_supported_money(source, quote, amount):
    start = source.index(quote)
    result = empty_extraction()
    result.claims = [
        ExtractedClaim(
            category="damage",
            amount_paise=amount,
            reason_code=None,
            description=Span(page=1, start=0, end=len(source), quote=source),
            amount_span=Span(page=1, start=start, end=start + len(quote), quote=quote),
        )
    ]
    with pytest.raises(ExtractionError, match="AMOUNT_NOT_DELIMITED"):
        validate_semantics(result, [source])
