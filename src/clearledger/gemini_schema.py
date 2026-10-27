"""Provider decoder hints, not ClearLedger's validation/financial contract.

Google documents numeric/array bounds as decoder-complexity risks and ignores
string-length constraints. Keep those checks in the unchanged strict host schema.
References, field names, required/null semantics, enums and closed objects survive.
"""

import json
import re
from itertools import islice
from typing import Any, cast

from clearledger.document_contract import Extraction

PROVIDER_SCHEMA_VERSION = "gemini-remittance-shape-v6"
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


def remittance_contents(pages: list[str]) -> str:
    """Position hints over projected text only; never guessed or repaired citations.

    Every boundary refers to exact page-local Unicode positions. The model may
    select wider excerpts but host validation still checks the original spans.
    """
    boundaries = (
        [page, match.start(), match.end(), match.group()]
        for page, text in enumerate(pages, 1)
        for match in re.finditer(r"\w+(?:[-.]\w+)*|[^\w\s]", text)
    )
    return json.dumps(
        {
            "untrusted_pages": pages,
            "source_token_boundaries": list(islice(boundaries, 512)),
        }
    )
