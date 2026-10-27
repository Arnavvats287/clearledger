"""One-shot evaluation HTTP client. No SDK, redirects, middleware or model retries."""

from dataclasses import dataclass
from typing import Any

import httpx

MODEL = "gemini-3.5-flash-lite"
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
SAFE_STATUS = {
    "INVALID_ARGUMENT",
    "FAILED_PRECONDITION",
    "RESOURCE_EXHAUSTED",
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "UNAVAILABLE",
    "DEADLINE_EXCEEDED",
    "INTERNAL",
    "NOT_FOUND",
    "CANCELLED",
    "UNKNOWN",
}


@dataclass
class ProviderError(Exception):
    category: str
    http_status: int | None = None
    provider_status: str = "UNKNOWN"


class GeminiHTTP:
    def __init__(self, key: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.client = httpx.Client(
            transport=transport or httpx.HTTPTransport(retries=0),
            timeout=httpx.Timeout(90, connect=15),
            follow_redirects=False,
            trust_env=False,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        )

    def close(self) -> None:
        self.client.close()

    def request(self, operation: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if operation not in {"model", "countTokens", "generateContent"}:
            raise ValueError("OPERATION_NOT_ALLOWLISTED")
        url = BASE + MODEL + ("" if operation == "model" else f":{operation}")
        try:
            response = self.client.get(url) if body is None else self.client.post(url, json=body)
        except httpx.TimeoutException:
            raise ProviderError("PROVIDER_TIMEOUT") from None
        except httpx.TransportError:
            raise ProviderError("PROVIDER_ERROR") from None
        try:
            data = response.json()
        except ValueError:
            raise ProviderError("PROVIDER_ERROR", response.status_code) from None
        if not isinstance(data, dict):
            raise ProviderError("PROVIDER_ERROR", response.status_code)
        if response.status_code != 200:
            error = data.get("error")
            status = error.get("status", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
            status = status if isinstance(status, str) else "UNKNOWN"
            status = status if status in SAFE_STATUS else "UNKNOWN"
            code = (
                "AUTH_FAILURE"
                if response.status_code in {401, 403}
                else "PROVIDER_RATE_LIMIT"
                if response.status_code == 429
                else "PROVIDER_ERROR"
            )
            raise ProviderError(code, response.status_code, status)
        return data


def generation_request(
    payload: Any, prompt: str, schema: dict[str, Any], limit: int
) -> dict[str, Any]:
    import json

    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        )
                    }
                ],
            }
        ],
        "systemInstruction": {"parts": [{"text": prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": limit,
            "thinkingConfig": {"thinkingLevel": "MINIMAL"},
        },
    }
