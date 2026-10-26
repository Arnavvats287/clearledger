"""Content-free diagnostics: code locations, fixed codes and controlled route templates.

Never format exception messages, traceback source lines, locals, URLs or request bodies.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "chronological_adapter.py",
    "chronological_host.py",
    "chronological_protocol.py",
    "chronological_diagnostics.py",
    "application_eval_host.py",
    "application_eval_runtime.py",
    "application_eval_contract.py",
    "application_eval_inputs.py",
    "pilot_runtime.py",
}
CODES = {
    "PRIVATE_PROVENANCE_STORAGE_BUDGET",
    "PRIVATE_SOURCE_ARCHIVE_CHANGED",
    "CSV_API_ERROR",
    "PREVIOUS_FINANCIAL_RECORD_CHANGED",
    "DOCUMENT_API_ERROR",
    "DUPLICATE_RECEIPT_NATURAL_KEY",
    "MATCHING_API_ERROR",
    "FINANCIAL_INVARIANT_FAILED",
    "RESPONSE_LIMIT",
    "STALE_CASE_REFRESH_API_ERROR",
    "EVIDENCE_API_ERROR",
    "INVESTIGATION_API_ERROR",
    "STAGE_DEADLINE",
    "OUTBOX_RETRY_OR_FAILURE_DISCARD_RUN",
    "BOUNDED_WORKER_FAILED",
    "OUTBOX_DRAIN_BUDGET",
    "WORKER_OUTPUT_INVALID",
}
LEGACY_CODES = {
    "Evaluation role login failed": "ROLE_LOGIN_FAILED",
    "Pagination budget exceeded": "PAGINATION_BUDGET",
    "API exited before readiness": "API_EXITED_BEFORE_READINESS",
    "API readiness deadline": "API_READINESS_DEADLINE",
    "Matching replay changed immutable result": "MATCHING_REPLAY_CHANGED",
    "Original document integrity failure": "ORIGINAL_DOCUMENT_INTEGRITY",
    "Canonical pages integrity failure": "CANONICAL_PAGES_INTEGRITY",
    "Canonical span verification boundary failed": "CANONICAL_SPAN_BOUNDARY",
    "Offline extraction/authority boundary failed": "OFFLINE_EXTRACTION_BOUNDARY",
    "Unattested source unexpectedly linked": "UNATTESTED_SOURCE_LINKED",
}
PARTS = {
    "review",
    "demo",
    "login",
    "cases",
    "documents",
    "receipts",
    "finance",
    "journals",
    "customers",
    "payer-aliases",
    "invoices",
    "bank-transactions",
    "imports",
    "matching-context",
    "match",
    "advanced-matching-context",
    "match-advanced",
    "original",
    "text",
    "verify-span",
    "extract",
    "correlate",
    "claims",
    "refresh",
    "evidence",
    "search",
    "investigations",
    "findings",
}


def route(path):
    return "/" + "/".join(
        p if p in PARTS else "{id}" for p in path.split("?", 1)[0].split("/") if p
    )


def diagnostic(error, component):
    cls = type(error)
    trusted = cls.__module__.split(".")[0] in {
        "builtins",
        "httpx",
        "httpcore",
        "sqlalchemy",
        "psycopg",
        "json",
        "pydantic_core",
        "subprocess",
        "chronological_diagnostics",
    } or (
        cls.__module__.split(".")[0] == "clearledger"
        and cls.__name__
        in {"CaseError", "ExtractionError", "ProviderFailure", "ImportFailure", "Exhausted"}
    )
    name = (
        cls.__name__
        if trusted and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", cls.__name__)
        else "Exception"
    )
    code = "UNCLASSIFIED_FAILURE"
    if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in CODES:
        code = error.args[0]
    elif len(error.args) == 1 and type(error.args[0]) is str:
        code = LEGACY_CODES.get(error.args[0], code)
    location = None
    tb = error.__traceback__
    while tb is not None:
        frame = tb.tb_frame.f_code
        try:
            relative = Path(frame.co_filename).resolve().relative_to(ROOT)
            approved = (
                relative.parts[:1] == ("scripts",)
                and len(relative.parts) == 2
                and relative.name in SCRIPTS
            ) or (
                relative.parts[:2] == ("src", "clearledger")
                and len(relative.parts) == 3
                and re.fullmatch(r"[a-z_]+\.py", relative.name)
            )
            if approved:
                function = frame.co_name
                location = {
                    "file": relative.as_posix(),
                    "line": tb.tb_lineno,
                    "function": function
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", function)
                    else "module",
                }
        except (ValueError, OSError):
            pass
        tb = tb.tb_next
    result = {"component": component, "exception_type": name, "code": code, "source": location}
    if isinstance(error, WorkerFailure):
        result["worker_failure"] = error.details
    return result


def worker_diagnostic(value):
    """Accept only a content-free child diagnostic, never arbitrary child stderr."""
    if not isinstance(value, dict) or set(value) != {
        "component",
        "exception_type",
        "code",
        "source",
    }:
        return None
    source = value["source"]
    if source is not None and (
        not isinstance(source, dict)
        or set(source) != {"file", "line", "function"}
        or not isinstance(source["file"], str)
        or not re.fullmatch(r"(?:scripts|src/clearledger)/[a-z_]+\.py", source["file"])
        or type(source["line"]) is not int
        or not 1 <= source["line"] <= 100000
        or not isinstance(source["function"], str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", source["function"])
    ):
        return None
    if (
        source is not None
        and source["file"].startswith("scripts/")
        and (Path(source["file"]).name not in SCRIPTS)
    ):
        return None
    if (
        value["component"] != "worker"
        or not isinstance(value["code"], str)
        or (value["code"] not in CODES | set(LEGACY_CODES.values()) | {"UNCLASSIFIED_FAILURE"})
    ):
        return None
    if not isinstance(value["exception_type"], str) or value["exception_type"] not in {
        "RuntimeError",
        "ValueError",
        "TypeError",
        "KeyError",
        "TimeoutError",
        "OSError",
        "OperationalError",
        "IntegrityError",
        "DBAPIError",
        "ProgrammingError",
        "InterfaceError",
        "InvalidRequestError",
        "StatementError",
        "ValidationError",
        "JSONDecodeError",
        "FileNotFoundError",
        "PermissionError",
        "MemoryError",
        "Exception",
        "CaseError",
        "ExtractionError",
        "ProviderFailure",
        "ImportFailure",
        "Exhausted",
    }:
        return None
    return value


class WorkerFailure(RuntimeError):
    def __init__(self, code, details=None):
        super().__init__(code)
        self.details = details
