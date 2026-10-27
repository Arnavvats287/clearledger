"""Exact isolated worker startup with a mocked SDK; never accesses Google."""

import json
import subprocess
import sys


def test_ar_schema_is_preloaded_before_guard_and_mock_sdk_completes():
    script = """
from types import SimpleNamespace as N
from google import genai
class Client:
    def __init__(self, **kwargs): self.models = self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, **kwargs):
        return N(name='models/isolated-unit-model', supported_actions=['generateContent'],
                 input_token_limit=10000, output_token_limit=10000, version='offline')
    def count_tokens(self, **kwargs): return N(total_tokens=10)
    def generate_content(self, **kwargs):
        assert 'NumericObservation' in str(kwargs['config'].response_json_schema)
        assert 'including contextual remittance records' in kwargs['config'].system_instruction
        return N(text='{"plan":null,"synthesis":null}',
                 usage_metadata=N(prompt_token_count=10,candidates_token_count=10,
                                  total_token_count=20,thoughts_token_count=None,
                                  cached_content_token_count=None))
genai.Client = Client
from clearledger.gemini_worker import main
main()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        input=json.dumps(
            {
                "key": "isolated-unit-key",
                "model": "isolated-unit-model",
                "timeout_ms": 1000,
                "pages": ["synthetic"],
                "task": "investigation_ar",
                "max_input_tokens": 3072,
                "max_output_tokens": 512,
            }
        ),
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    response = json.loads(result.stdout)
    assert "error" not in response, response
    assert response["input_tokens"] == 10
    assert response["validated_model"]["version"] == "offline"
    assert "isolated-unit-key" not in result.stdout + result.stderr


def test_guard_still_rejects_late_application_import():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "from clearledger.worker_security import install_guard; install_guard(); "
            "from clearledger.investigation_ai_contract import ARReply",
        ],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode != 0 and "WORKER_FILESYSTEM_DENIED" in result.stderr


def test_provider_enums_preserve_strict_host_literals_and_no_private_diagnostics():
    import pytest
    from pydantic import ValidationError

    from clearledger.investigation_ai_contract import (
        EvidencePlan,
        ar_response_schema,
        schema_errors,
    )

    schema = ar_response_schema()
    props = schema["$defs"]["EvidencePlan"]["properties"]
    assert props["support_test"]["enum"] == ["AUTHENTICATED_REQUIRED_RECORDS_MATCH_CLAIM"]
    assert "const" not in props["support_test"]
    with pytest.raises(ValidationError):
        EvidencePlan.model_validate({"support_test": "PRIVATE-CANARY"})
    safe = schema_errors(
        [{"type": "missing", "loc": ["plan", "support_test"], "input": "PRIVATE-CANARY"}]
    )
    assert safe == [{"code": "missing", "path": ["plan", "support_test"]}]
    assert "PRIVATE-CANARY" not in json.dumps(safe)
