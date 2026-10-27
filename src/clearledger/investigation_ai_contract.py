"""Compact review-only AR reasoning contract; no hidden reasoning or capabilities."""

from typing import Annotated, Any, Literal, cast
from uuid import UUID

from pydantic import Field

from clearledger.document_contract import Category
from clearledger.evidence_contract import Kind, Question, Strict
from clearledger.investigation_contract import Tool

VERSION = "ar-investigator-v2"


class EvidencePlan(Strict):
    assertion: Question
    category: Category
    amount_paise: Annotated[int, Field(strict=True, ge=0)] | None
    tools: Annotated[list[Tool], Field(min_length=1, max_length=7)]
    evidence_types: Annotated[list[Kind], Field(min_length=1, max_length=7)]
    support_test: Literal["AUTHENTICATED_REQUIRED_RECORDS_MATCH_CLAIM"]
    contradiction_test: Literal["VERIFIED_RECORDS_DISAGREE_OR_AMOUNT_DIFFERS"]
    unresolved_test: Literal["MISSING_UNVERIFIED_STALE_OR_INCOMPLETE_PROOF"]
    financial_authority: Literal[False]


class NumericObservation(Strict):
    record_id: UUID
    field: Literal[
        "damaged_quantity",
        "delivered_quantity",
        "shipped_quantity",
        "unit_value_paise",
        "amount_paise",
        "limit_paise",
    ]
    value: Annotated[int, Field(strict=True, ge=0)]


class Synthesis(Strict):
    amount_paise: Annotated[int, Field(strict=True, ge=0)] | None
    state: Literal["SUPPORTED", "INSUFFICIENT_EVIDENCE", "CONFLICTING_EVIDENCE"]
    next_action: Literal["HUMAN_REVIEW", "REQUEST_EVIDENCE", "ESCALATE_CONFLICT"]
    record_ids: Annotated[list[UUID], Field(max_length=20)]
    observations: Annotated[list[NumericObservation], Field(max_length=12)]
    missing_evidence_types: Annotated[list[Kind], Field(max_length=7)]
    rationale: Literal[
        "Verified required evidence supports the claimed amount.",
        "Required authenticated evidence is missing or incomplete.",
        "Verified source facts conflict; no resolution is authorized.",
    ]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    uncertainty: Literal["NONE", "MISSING_EVIDENCE", "CONFLICTING_EVIDENCE"]
    financial_authority: Literal[False]


class ARReply(Strict):
    plan: EvidencePlan | None
    synthesis: Synthesis | None


def ar_response_schema() -> dict[str, Any]:
    """Provider enum constraints; strict host literals/semantics remain unchanged."""

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(x) for x in node]
        if not isinstance(node, dict):
            return node
        result = {key: convert(value) for key, value in node.items()}
        if isinstance(result.get("const"), str):
            result["enum"] = [result.pop("const")]
        return result

    return cast(dict[str, Any], convert(ARReply.model_json_schema()))


def schema_errors(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Fixed field/type diagnostics only; no inputs, messages or URLs."""
    fields = (
        set(EvidencePlan.model_fields)
        | set(Synthesis.model_fields)
        | set(NumericObservation.model_fields)
        | {"plan", "synthesis"}
    )
    codes = {
        "missing",
        "extra_forbidden",
        "int_type",
        "int_parsing",
        "literal_error",
        "list_type",
        "model_type",
        "dict_type",
        "uuid_parsing",
        "greater_than_equal",
        "too_long",
    }
    result: list[dict[str, object]] = []
    for row in rows[:20]:
        code = row.get("type", row.get("code"))
        path = row.get("loc", row.get("path", []))
        result.append(
            {
                "code": code if isinstance(code, str) and code in codes else "VALIDATION",
                "path": [
                    part
                    if (type(part) is int and 0 <= part <= 20)
                    or (isinstance(part, str) and part in fields)
                    else "UNKNOWN"
                    for part in path
                ]
                if isinstance(path, (list, tuple))
                else ["UNKNOWN"],
            }
        )
    return result
