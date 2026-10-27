"""Real locked SDK serialization through local MockTransport: zero provider calls."""

import copy
import json

import httpx
import pytest
from google import genai
from google.genai import types
from pydantic import ValidationError
from test_document_domain import minimal_model_result

from clearledger.document_contract import Extraction
from clearledger.documents import semantic_cache_key
from clearledger.gemini_schema import PROVIDER_SCHEMA_VERSION, remittance_response_schema
from clearledger.gemini_worker import SYSTEM_INSTRUCTION


def serialized(schema):
    captured = []

    def local(request):
        assert request.url.path.endswith(":generateContent")
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "{}"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    with genai.Client(
        api_key="offline-unit-not-a-secret",
        vertexai=False,
        http_options=types.HttpOptions(
            client_args={"transport": httpx.MockTransport(local), "trust_env": False},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    ) as client:
        client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=json.dumps({"untrusted_pages": ["Invoice I-1"]}),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=512,
                candidate_count=1,
                temperature=0,
                tools=[],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    assert len(captured) == 1
    return captured[0]


def test_exact_sdk_wire_change_is_schema_only_and_no_tool_control_leaks():
    strict = Extraction.model_json_schema()
    before = copy.deepcopy(strict)
    wire = remittance_response_schema()
    old, new = serialized(strict), serialized(wire)
    assert new["generationConfig"]["responseJsonSchema"] == wire
    assert old["generationConfig"].pop("responseJsonSchema") == strict
    assert new["generationConfig"].pop("responseJsonSchema") == wire
    assert old == new
    assert new["generationConfig"] == {
        "responseMimeType": "application/json",
        "temperature": 0.0,
        "maxOutputTokens": 512,
        "candidateCount": 1,
    }
    assert new["tools"] == []
    assert "automaticFunctionCalling" not in json.dumps(new)
    assert Extraction.model_json_schema() == before
    assert len(json.dumps(wire)) < len(json.dumps(strict))


def test_provider_preserves_shapes_enums_nulls_and_closed_objects_only_bounds_differ():
    original = Extraction.model_json_schema()
    wire = remittance_response_schema()
    assert wire["properties"].keys() == original["properties"].keys()
    assert wire["required"] == original["required"]
    assert wire["$defs"].keys() == original["$defs"].keys()
    assert wire["$defs"]["ExtractedClaim"]["properties"]["amount_paise"]["anyOf"] == [
        {"type": "integer"},
        {"type": "null"},
    ]
    assert wire["properties"]["uncertainty"] == original["properties"]["uncertainty"]
    assert wire["properties"]["payer_hint"] == original["properties"]["payer_hint"]
    assert wire["additionalProperties"] is False
    assert all(item["additionalProperties"] is False for item in wire["$defs"].values())
    assert not any(
        f'"{name}":' in json.dumps(wire)
        for name in ("minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength")
    )


@pytest.mark.parametrize("amount", [True, 1.01, "101", -1, 2**63])
def test_internal_integer_money_remains_strict(amount):
    body = minimal_model_result("Invoice I-1")
    body["claims"] = [
        {
            "category": "damage",
            "description": {"page": 1, "start": 0, "end": 11, "quote": "Invoice I-1"},
            "amount_paise": amount,
            "amount_span": None,
            "reason_code": None,
        }
    ]
    with pytest.raises(ValidationError):
        Extraction.model_validate(body)


def test_wire_version_does_not_reuse_legacy_semantic_cache_identity():
    values = {
        name: "unit"
        for name in (
            "document_sha256",
            "canonical_sha256",
            "document_version",
            "parser_version",
            "schema_version",
            "privacy_version",
            "provider",
            "model",
            "review_reference_sha256",
        )
    }
    assert semantic_cache_key(values) != semantic_cache_key(
        {**values, "provider_schema_version": PROVIDER_SCHEMA_VERSION}
    )
    assert semantic_cache_key(values) == semantic_cache_key(
        {**values, "provider_schema_version": "strict-domain-v1"}
    )
    assert semantic_cache_key(
        {**values, "provider_schema_version": PROVIDER_SCHEMA_VERSION}
    ) != semantic_cache_key({**values, "provider_schema_version": "gemini-remittance-shape-v5"})


def test_explicit_damage_with_unknown_amount_retained_without_invented_money():
    from clearledger.document_contract import ExtractionError, validate_semantics

    source = "Invoice I-1: damage amount unknown; review required."
    body = minimal_model_result(source)
    body["claims"] = [
        {
            "category": "damage",
            "description": {"page": 1, "start": 0, "end": len(source), "quote": source},
            "amount_paise": None,
            "amount_span": None,
            "reason_code": None,
        }
    ]
    result = Extraction.model_validate(body)
    validate_semantics(result, [source])
    assert "Do not omit an explicit damage claim" in SYSTEM_INSTRUCTION
    result.claims[0].amount_paise = 101
    with pytest.raises(ExtractionError, match="MISSING_AMOUNT_EVIDENCE"):
        validate_semantics(result, [source])
