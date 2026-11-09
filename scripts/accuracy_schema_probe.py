"""Synthetic-only Gemini schema admission, with append-only sanitized observations."""

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from external_eval.accuracy_nli import DecisionResponse, provider_shape
from external_eval.gemini_http import MODEL, GeminiHTTP, ProviderError, generation_request
from external_eval.source import write_json

TRANSIENT = {429, 500, 502, 503, 504}
PROMPT = (
    "Synthetic schema test. Return one item with id H01, label Entailment and evidence E01. "
    "If asked for answers, use hypothesis_id H01, predicted_label Entailment, aliases [E01], "
    "relation SUPPORT and contradiction_basis NONE. Do not return fields outside the schema."
)
PAYLOAD = {"synthetic": "Archival copies may be retained.", "id": "H01", "alias": "E01"}


def minimal_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }


def feature_probes() -> list[tuple[str, dict[str, Any]]]:
    base = minimal_schema()
    outer = base["properties"]["items"]
    row = outer["items"]
    evidence = row["properties"]["evidence"]
    changes = [
        ("label-enum", row["properties"]["label"], {"enum": ["Entailment", "Contradiction"]}),
        ("alias-enum", evidence["items"], {"enum": ["E01", "E02"]}),
        ("outer-minItems", outer, {"minItems": 1}),
        ("outer-maxItems", outer, {"maxItems": 17}),
        ("inner-minItems", evidence, {"minItems": 0}),
        ("inner-maxItems", evidence, {"maxItems": 12}),
        ("required", row, {"required": ["id", "label", "evidence"]}),
        ("additionalProperties", row, {"additionalProperties": False}),
        ("type-union", row["properties"]["id"], {"type": ["string", "null"]}),
        ("description", row, {"description": "One synthetic evidence selection."}),
        ("defs-only", base, {"$defs": {"identifier": {"type": "string"}}}),
    ]
    probes = [("minimal", deepcopy(base))]
    for name, node, delta in changes:
        original = node.copy()
        node.update(delta)
        probes.append((name, deepcopy(base)))
        node.clear()
        node.update(original)
    with_defs = deepcopy(probes[-1][1])
    with_defs["properties"]["items"]["items"]["properties"]["id"] = {"$ref": "#/$defs/identifier"}
    probes.append(("ref-with-defs", with_defs))
    union = deepcopy(base)
    union["properties"]["items"]["items"]["properties"]["id"] = {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }
    probes.append(("anyOf", union))
    probes.append(("exact-pydantic", DecisionResponse.model_json_schema()))
    return probes


def retryable(error: ProviderError) -> bool:
    return error.http_status in TRANSIENT or (
        error.http_status is None and error.category in {"PROVIDER_TIMEOUT", "PROVIDER_ERROR"}
    )


def synthesis_probes() -> list[tuple[str, dict[str, Any]]]:
    exact = DecisionResponse.model_json_schema()
    no_outer = deepcopy(exact)
    del no_outer["properties"]["answers"]["maxItems"]
    no_inner = deepcopy(exact)
    del no_inner["$defs"]["DecisionRow"]["properties"]["aliases"]["maxItems"]
    no_both = deepcopy(no_outer)
    del no_both["$defs"]["DecisionRow"]["properties"]["aliases"]["maxItems"]
    return [
        ("simple-synthesis", provider_shape(exact)),
        ("exact-without-outer-maxItems", no_outer),
        ("exact-without-inner-maxItems", no_inner),
        ("exact-without-both-maxItems", no_both),
    ]


def run_probe(
    root: Path,
    client: GeminiHTTP,
    *,
    sleep: Callable[[float], None] = time.sleep,
    synthesis: bool = False,
) -> None:
    root.mkdir(parents=True, exist_ok=False)
    sequence = 0

    def check(name: str, schema: dict[str, Any]) -> int | None:
        nonlocal sequence
        encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        for retry in range(3):
            if sequence:
                sleep(10 * (2**retry))
            sequence += 1
            started = time.monotonic()
            record = {
                "delta": name,
                "schema_sha256": hashlib.sha256(encoded).hexdigest(),
                "schema_bytes": len(encoded),
                "model": MODEL,
                "timestamp": datetime.now(UTC).isoformat(),
                "attempt": retry + 1,
            }
            path = root / f"{sequence:02d}-{name}"
            write_json(path.with_suffix(".started.json"), record)
            status: int | None
            try:
                data = client.request(
                    "generateContent", generation_request(PAYLOAD, PROMPT, schema, 4096)
                )
                metadata = data.get("usageMetadata", {})
                status, safe_status, again = 200, "OK", False
            except ProviderError as error:
                status, safe_status, again = (
                    error.http_status,
                    error.provider_status,
                    retryable(error),
                )
                metadata = {}
            write_json(
                path.with_suffix(".json"),
                {
                    **record,
                    "http_status": status,
                    "provider_status": safe_status,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "usage": {
                        k: metadata[k]
                        for k in (
                            "promptTokenCount",
                            "candidatesTokenCount",
                            "thoughtsTokenCount",
                            "totalTokenCount",
                        )
                        if type(metadata.get(k)) is int
                    },
                },
            )
            print(f"{name} attempt {retry + 1}: {status} {safe_status}", flush=True)
            if not again:
                return status
        return status

    if synthesis:
        for name, schema in synthesis_probes():
            status = check(name, schema)
            if status != 200 and (name == "simple-synthesis" or status != 400):
                return
        return

    probes = feature_probes()
    for name, schema in probes:
        status = check(name, schema)
        if status == 200:
            continue
        if status == 400 and name != "minimal":
            # Explicit one-variable A/B confirmation, separate from transient retries.
            if check("remove-" + name, probes[0][1]) == 200:
                check("restore-" + name, schema)
        return


if __name__ == "__main__":
    from external_phase2 import key

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--synthesis", action="store_true")
    args = parser.parse_args()
    client = GeminiHTTP(key())
    try:
        run_probe(args.root, client, synthesis=args.synthesis)
    finally:
        client.close()
