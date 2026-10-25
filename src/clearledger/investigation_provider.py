"""Restricted structured investigator; no DB, tools or executable model instructions."""

from collections import deque
from functools import lru_cache
from threading import Lock

from clearledger.investigation_contract import InvestigatorReply, Proposal

_gateway_lock = Lock()


@lru_cache(maxsize=8)
def shared_gateway(
    key, model, timeout_ms, input_tokens, output_tokens, rpm, input_rate, output_rate
):
    from clearledger.extraction_provider import Gateway, GeminiTransport

    return Gateway(
        GeminiTransport(
            key,
            model,
            timeout_ms,
            max_input_tokens=input_tokens,
            max_output_tokens=output_tokens,
            task="investigation",
        ),
        attempts=1,
        requests_per_minute=rpm,
        input_rate=input_rate,
        output_rate=output_rate,
        max_input_tokens=input_tokens,
        max_output_tokens=output_tokens,
    )


class DeterministicInvestigator:
    name = "deterministic"

    def generate(self, request):
        remaining = [t for t in request.objective.tools if t not in request.searched_tools]
        if remaining and not request.objective.unknowns:
            return InvestigatorReply(action="SEARCH", tool=remaining[0])
        return InvestigatorReply(
            action="HYPOTHESIS",
            proposal=Proposal(
                classification=request.objective.category,
                suggested_state="INSUFFICIENT_EVIDENCE",
                citations=request.offered,
                unknowns=request.objective.unknowns,
                inference="NO_BACKED_CONCLUSION",
                next_action="HUMAN_REVIEW",
            ),
        )


class FakeInvestigator:
    name = "fake"

    def __init__(self, replies):
        self.replies = deque(replies)
        self.calls = []

    def generate(self, request):
        self.calls.append(request.model_dump(mode="json"))
        if not self.replies:
            return DeterministicInvestigator().generate(request)
        result = self.replies.popleft()
        if isinstance(result, Exception):
            raise result
        return result(request) if callable(result) else InvestigatorReply.model_validate(result)


def configured_provider(runtime):
    """Explicit, synthetic-only opt-in; the isolated SDK transport has no tools."""
    import json

    from sqlalchemy.orm import Session

    from clearledger.case_domain import CaseError
    from clearledger.extraction_provider import decode_output
    from clearledger.matching import owned
    from clearledger.models import Document
    from clearledger.provider_budget import reserve

    settings = runtime.settings
    if not (
        settings.external_ai_enabled
        and settings.investigation_external_enabled
        and runtime.snapshot["allow_external"]
        and settings.privacy_review_reference
        and settings.gemini_api_key
        and settings.gemini_model
    ):
        raise CaseError("INVESTIGATION_EXTERNAL_DISABLED", 403)
    rates = [
        settings.llm_input_paise_per_million_tokens,
        settings.llm_output_paise_per_million_tokens,
    ]
    if any(rate is None for rate in rates):
        raise CaseError("PROVIDER_PRICE_UNVERIFIED")
    # Every original in scope must be explicitly approved synthetic content.
    with Session(runtime.engine) as session:
        from clearledger.case_models import CaseDocument
        from clearledger.case_repository import group_rows, members, root

        ids = members(session, runtime.org, root(session, runtime.org, runtime.case_id))
        for link in group_rows(session, CaseDocument, runtime.org, ids):
            document = owned(session, Document, runtime.org, link.document_id)
            if not document.synthetic_approved:
                raise CaseError("SYNTHETIC_DOCUMENT_REQUIRED", 403)
    with _gateway_lock:
        gateway = shared_gateway(
            settings.gemini_api_key.get_secret_value(),
            settings.gemini_model,
            min(settings.llm_timeout_ms, runtime.limits.timeout_ms),
            settings.llm_max_input_tokens,
            settings.llm_max_output_tokens,
            settings.llm_requests_per_minute,
            rates[0],
            rates[1],
        )

    class GeminiInvestigator:
        name = "gemini"
        reserved_cost_paise = (
            settings.llm_max_input_tokens * rates[0]
            + settings.llm_max_output_tokens * rates[1]
            + 999999
        ) // 1000000

        def generate(self, request):
            with Session(runtime.engine) as session:
                for identifier in {h.document_id for h in request.hits if h.document_id}:
                    if not owned(session, Document, runtime.org, identifier).synthetic_approved:
                        raise CaseError("SYNTHETIC_DOCUMENT_REQUIRED", 403)
            reply, metrics = gateway.generate(
                [json.dumps(request.model_dump(mode="json"))],
                before_attempt=lambda: reserve(runtime.engine, runtime.org, "gemini", settings),
            )
            self.metrics = {
                name: metrics.get(name)
                for name in (
                    "input_tokens",
                    "output_tokens",
                    "latency_ms",
                    "estimated_cost_paise",
                    "usage_complete",
                )
            }
            return InvestigatorReply.model_validate(decode_output(reply.json_text))

    return GeminiInvestigator()
