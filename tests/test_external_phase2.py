"""Offline transport admission, no-retry behavior and failure-denominator equivalence."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from external_eval.contracts import Box, DocilePacket, Page, Word  # noqa: E402
from external_eval.failure_denominator import score_with_input_failures  # noqa: E402
from external_eval.gemini_http import GeminiHTTP, ProviderError, generation_request  # noqa: E402
from external_eval.scorers import GoldInvoice, score_docile  # noqa: E402
from external_gemini_worker import Worker, parse_text, usage  # noqa: E402


@pytest.mark.parametrize("status", [400, 401, 403, 429, 503, 504])
def test_one_http_attempt_and_sanitized_error(status):
    calls = []

    def handle(request):
        calls.append(request)
        assert "secret-test-key" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "secret-test-key"
        return httpx.Response(
            status,
            json={"error": {"status": "INVALID_ARGUMENT", "message": "sensitive source body"}},
        )

    client = GeminiHTTP("secret-test-key", transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as caught:
        client.request("generateContent", {})
    client.close()
    assert len(calls) == 1
    assert caught.value.http_status == status
    assert "sensitive" not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_timeout_has_no_retry():
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("private URL and prompt")

    client = GeminiHTTP("unit", transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
        client.request("generateContent", {})
    assert len(calls) == 1
    client.close()


def test_request_configuration_and_thought_isolation():
    body = generation_request({"text": "synthetic"}, "unchanged prompt", {"type": "object"}, 12)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert "tools" not in body
    response = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"thought": True, "text": "never persisted"},
                        {"text": '{"answers":[]}'},
                    ]
                },
            }
        ]
    }
    assert parse_text(response) == {"answers": []}
    assert usage({})["thoughtsTokenCount"] is None


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"candidates": []},
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]},
    ],
)
def test_truncated_or_missing_response_is_failure(value):
    with pytest.raises(ValueError, match="SCHEMA_PARSE_FAILURE"):
        parse_text(value)


def test_plan_unknown_and_missing_ids_rejected():
    payload = {"hypotheses": [{"hypothesis_id": "h1"}]}
    with pytest.raises(ValueError):
        Worker.validate_plan({"questions": []}, payload)
    row = dict.fromkeys(
        ("hypothesis_id", "question", "support_test", "contradiction_test", "unresolved_test"),
        "not-h1",
    )
    with pytest.raises(ValueError):
        Worker.validate_plan({"questions": [row]}, payload)
    row["hypothesis_id"] = "h1"
    Worker.validate_plan({"questions": [row]}, payload)


def test_inflight_marker_prevents_retry(tmp_path):
    worker = Worker.__new__(Worker)
    worker.root = tmp_path
    marker = tmp_path / "attempts" / "phase" / "unit" / "plan.started.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}")
    with pytest.raises(ValueError, match="UNKNOWN_INFLIGHT_NO_RETRY"):
        worker.attempt("phase", "unit", "plan", {}, 10, 10)


def test_completed_attempt_is_reused_without_http(tmp_path):
    worker = Worker.__new__(Worker)
    worker.root = tmp_path
    result = tmp_path / "attempts" / "phase" / "unit" / "plan.json"
    result.parent.mkdir(parents=True)
    result.write_text(
        json.dumps({"typed_result": {"questions": []}, "metadata": {"status": "SUCCESS"}})
    )
    assert worker.attempt("phase", "unit", "plan", {}, 10, 10)[1]["status"] == "SUCCESS"


def test_input_failure_bridge_preserves_frozen_metric():
    packets = {
        k: DocilePacket(
            document_id=k,
            pages=[
                Page(
                    page=0,
                    text="Invoice A",
                    words=[Word(start=0, end=9, box=Box(left=0.1, top=0.1, right=0.5, bottom=0.5))],
                )
            ],
        )
        for k in ("valid", "invalid-invoice", "invalid-other")
    }
    gold = [
        GoldInvoice("valid", True, ("A",)),
        GoldInvoice("invalid-invoice", True, ("B",)),
        GoldInvoice("invalid-other", False, ()),
    ]
    original = score_docile(packets, [], gold)
    bridged = score_with_input_failures(
        {"valid": packets["valid"]}, [], gold, {"invalid-invoice", "invalid-other"}
    )
    for key in original:
        assert bridged[key] == original[key]


def test_worker_has_no_gold_or_product_imports():
    path = Path(__file__).resolve().parents[1] / "scripts" / "external_gemini_worker.py"
    import ast

    tree = ast.parse(path.read_text())
    modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(
        n.startswith(("clearledger", "external_eval.gold", "external_eval.scorers"))
        for n in modules
    )
