"""Offline synthetic failures: SDK and worker are mocked, never contacted."""

import io
import json
import logging
import sys
from types import SimpleNamespace

import pytest

from clearledger.document_contract import ExtractionError
from clearledger.extraction_provider import Gateway, GeminiTransport, ProviderRunError
from clearledger.provider_diagnostics import diagnostic, sanitized

CANARY = "PRIVATE-KEY-PROMPT-BODY-https://secret.invalid/private"


@pytest.mark.parametrize(
    "phase,kind,status,category,provider_status",
    [
        ("MODEL_LOOKUP", "http", 403, "HTTP_API", "PERMISSION_DENIED"),
        ("TOKEN_COUNT", "http", 400, "HTTP_API", "INVALID_ARGUMENT"),
        ("CONTENT_GENERATION", "http", 400, "HTTP_API", "FAILED_PRECONDITION"),
        ("CONTENT_GENERATION", "http", 429, "HTTP_API", "RESOURCE_EXHAUSTED"),
        ("CONTENT_GENERATION", "http", 503, "HTTP_API", "UNAVAILABLE"),
        ("CONTENT_GENERATION", "http", 400, "HTTP_API", None),
        ("CONTENT_GENERATION", "http", 400, "HTTP_API", CANARY),
        ("TOKEN_COUNT", "timeout", None, "TIMEOUT", None),
        ("CONTENT_GENERATION", "timeout", None, "TIMEOUT", None),
        ("MODEL_LOOKUP", "security", None, "SECURITY", None),
        ("MODEL_LOOKUP", "domain", None, "DOMAIN_VALIDATION", None),
        ("RESPONSE_DECODING", "decode", None, "DECODE", None),
    ],
)
def test_mock_sdk_failure_phases_never_expose_body(
    monkeypatch, phase, kind, status, category, provider_status
):
    from google import genai
    from google.genai.errors import APIError

    from clearledger import gemini_worker

    visited = []

    def maybe_fail(current):
        visited.append(current)
        if current != phase:
            return
        if kind == "http":
            raise APIError(status, {"error": {"message": CANARY, "status": provider_status}})
        if kind == "timeout":
            raise TimeoutError(CANARY)
        if kind == "security":
            raise PermissionError(CANARY)
        if kind == "domain":
            raise ExtractionError(CANARY)
        raise json.JSONDecodeError(CANARY, CANARY, 0)

    class Response:
        @property
        def usage_metadata(self):
            maybe_fail("RESPONSE_DECODING")

    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, **kwargs):
            maybe_fail("MODEL_LOOKUP")
            return SimpleNamespace(
                name="models/unit-model",
                supported_actions=["generateContent"],
                input_token_limit=8192,
                output_token_limit=4096,
                version="unit",
            )

        def count_tokens(self, **kwargs):
            maybe_fail("TOKEN_COUNT")
            return SimpleNamespace(total_tokens=100)

        def generate_content(self, **kwargs):
            maybe_fail("CONTENT_GENERATION")
            return Response()

    output = io.StringIO()
    monkeypatch.setattr(genai, "Client", Client)
    monkeypatch.setattr(logging, "disable", lambda _: None)
    monkeypatch.setattr("clearledger.worker_security.install_guard", lambda **_: None)
    monkeypatch.setattr("clearledger.worker_security.posix_limits", lambda: None)
    request = {"key": CANARY, "model": "unit-model", "pages": ["Invoice I-1"], "timeout_ms": 1000}
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(request).encode())))
    monkeypatch.setattr(sys, "stdout", output)
    gemini_worker.main()
    result = json.loads(output.getvalue())
    assert result == {
        "error": "PROVIDER_FAILED",
        "retryable": status in (429, 503),
        "diagnostic": diagnostic(phase, category, status, provider_status),
    }
    assert visited[-1] == phase
    assert CANARY not in output.getvalue() and "secret.invalid" not in output.getvalue()
    # Confirm the diagnostic survives the actual transport/gateway boundaries.
    monkeypatch.setattr("clearledger.document_runtime.run_worker", lambda *a, **kw: result)
    with pytest.raises(ProviderRunError) as failure:
        Gateway(GeminiTransport(CANARY, "unit-model"), attempts=1).generate(["Invoice I-1"])
    assert str(failure.value) == "PROVIDER_FAILED"
    assert failure.value.metrics["diagnostic"] == diagnostic(
        phase, category, status, provider_status
    )
    assert CANARY not in json.dumps(failure.value.metrics)


@pytest.mark.parametrize(
    "error,phase,category",
    [
        (ExtractionError("PARSER_TIMEOUT"), "WORKER_TIMEOUT", "TIMEOUT"),
        (ExtractionError("PARSER_RESOURCE_FAILURE"), "WORKER_PROCESS", "RESOURCE"),
        (ExtractionError("PARSER_SANDBOX_UNAVAILABLE"), "WORKER_PROCESS", "RESOURCE"),
        (OSError(CANARY), "WORKER_PROCESS", "PROCESS"),
        (json.JSONDecodeError(CANARY, CANARY, 0), "RESPONSE_DECODING", "DECODE"),
    ],
)
def test_worker_process_and_timeout_are_distinct(monkeypatch, error, phase, category):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr("clearledger.document_runtime.run_worker", fail)
    with pytest.raises(ProviderRunError) as failure:
        Gateway(GeminiTransport(CANARY, "unit-model"), attempts=1).generate(["synthetic"])
    assert failure.value.metrics["diagnostic"] == diagnostic(phase, category)
    assert failure.value.metrics["attempts"] == 1
    assert not failure.value.metrics["usage_complete"]
    assert CANARY not in json.dumps(failure.value.metrics)


@pytest.mark.parametrize("status", [True, "429", 99, 600, {"body": CANARY}])
def test_untrusted_diagnostic_fields_are_allowlisted(status):
    result = sanitized(
        {
            "phase": CANARY,
            "exception_category": CANARY,
            "http_status": status,
            "body": CANARY,
            "key": CANARY,
        }
    )
    assert result == {"phase": "UNKNOWN", "exception_category": "INTERNAL"}


@pytest.mark.parametrize("reply", [[], {"json_text": 42}, {}])
def test_invalid_worker_response_is_not_success(monkeypatch, reply):
    monkeypatch.setattr("clearledger.document_runtime.run_worker", lambda *a, **kw: reply)
    with pytest.raises(ProviderRunError) as failure:
        Gateway(GeminiTransport(CANARY, "unit-model"), attempts=1).generate(["synthetic"])
    assert failure.value.metrics["diagnostic"] == diagnostic("RESPONSE_DECODING", "DECODE")


@pytest.mark.parametrize(
    "value", [None, CANARY, "invalid_argument", True, [CANARY], {"body": CANARY}]
)
def test_provider_status_unknown_never_reads_or_copies_error_body(value):
    result = sanitized(
        {
            "phase": "CONTENT_GENERATION",
            "exception_category": "HTTP_API",
            "http_status": 400,
            "provider_status": value,
            "body": CANARY,
        }
    )
    assert result == {
        "phase": "CONTENT_GENERATION",
        "exception_category": "HTTP_API",
        "http_status": 400,
        "provider_status": "UNKNOWN",
    }
    assert CANARY not in json.dumps(result)


def test_same_http_code_is_not_used_to_infer_provider_status():
    for status in ("INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE"):
        assert (
            diagnostic("CONTENT_GENERATION", "HTTP_API", 400, status)["provider_status"] == status
        )
    assert diagnostic("CONTENT_GENERATION", "HTTP_API", 400)["provider_status"] == "UNKNOWN"
