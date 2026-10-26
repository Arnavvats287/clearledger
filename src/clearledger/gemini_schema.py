"""Provider decoder hints, not ClearLedger's validation/financial contract.

Google documents numeric/array bounds as decoder-complexity risks and ignores
string-length constraints. Keep those checks in the unchanged strict host schema.
References, field names, required/null semantics, enums and closed objects survive.
"""

from typing import Any, cast

from clearledger.document_contract import Extraction

PROVIDER_SCHEMA_VERSION = "gemini-remittance-shape-v1"
_HOST_ONLY_BOUNDS = frozenset(
    {
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
    }
)


def remittance_response_schema() -> dict[str, Any]:
    def simplify(node: Any) -> Any:
        if isinstance(node, list):
            return [simplify(item) for item in node]
        if not isinstance(node, dict):
            return node
        return {
            key: (
                {name: simplify(child) for name, child in value.items()}
                if key in {"properties", "$defs"}
                else simplify(value)
            )
            for key, value in node.items()
            if key not in _HOST_ONLY_BOUNDS
        }

    return cast(dict[str, Any], simplify(Extraction.model_json_schema()))
