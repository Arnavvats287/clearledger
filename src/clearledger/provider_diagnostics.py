"""Closed diagnostic vocabulary. Never serialize exception messages or provider data."""

import json

PHASES = frozenset(
    {
        "UNKNOWN",
        "WORKER_STARTUP",
        "MODEL_LOOKUP",
        "TOKEN_COUNT",
        "CONTENT_GENERATION",
        "RESPONSE_DECODING",
        "SCHEMA_VALIDATION",
        "SOURCE_VALIDATION",
        "LOCAL_VALIDATION",
        "PROVIDER_TRANSPORT",
        "ADMISSION",
        "WORKER_TIMEOUT",
        "WORKER_PROCESS",
    }
)
CATEGORIES = frozenset(
    {
        "HTTP_API",
        "TIMEOUT",
        "TLS",
        "VALIDATION",
        "DECODE",
        "PROCESS",
        "RESOURCE",
        "SECURITY",
        "INTERNAL",
        "DOMAIN_VALIDATION",
    }
)


def diagnostic(phase: str, category: str, http_status: object = None) -> dict[str, object]:
    result: dict[str, object] = {
        "phase": phase if phase in PHASES else "UNKNOWN",
        "exception_category": category if category in CATEGORIES else "INTERNAL",
    }
    if type(http_status) is int and 100 <= http_status <= 599:
        result["http_status"] = http_status
    return result


def sanitized(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return diagnostic("UNKNOWN", "INTERNAL")
    phase = value.get("phase")
    category = value.get("exception_category")
    return diagnostic(
        phase if isinstance(phase, str) else "UNKNOWN",
        category if isinstance(category, str) else "INTERNAL",
        value.get("http_status"),
    )


def exception_category(error: Exception) -> str:
    # Class names are compared only, never returned; arbitrary class/message text cannot leak.
    names = {cls.__name__ for cls in type(error).__mro__}
    if isinstance(error, TimeoutError) or names & {
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
    }:
        return "TIMEOUT"
    if names & {"SSLError", "SSLCertVerificationError", "CertificateError"}:
        return "TLS"
    if isinstance(error, json.JSONDecodeError):
        return "DECODE"
    if isinstance(error, PermissionError):
        return "SECURITY"
    if isinstance(error, MemoryError):
        return "RESOURCE"
    if isinstance(error, (ValueError, TypeError, IndexError, RecursionError)):
        return "VALIDATION"
    if isinstance(error, OSError):
        return "PROCESS"
    return "INTERNAL"
