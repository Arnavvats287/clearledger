"""Two bounded reasoning phases inside the original durable LangGraph host."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.case_repository import scoped
from clearledger.evidence_contract import SearchResult
from clearledger.evidence_reader import TOOLS
from clearledger.investigation_ai_contract import VERSION, ARReply, EvidencePlan, Synthesis
from clearledger.investigation_broker import offered
from clearledger.investigation_contract import Proposal
from clearledger.investigation_director import SEARCH
from clearledger.investigation_grounding import evidence_catalog, validate_span_selection
from clearledger.investigation_models import Investigation, InvestigationResult, InvestigationTrace
from clearledger.matching import digest


def basis(objective):
    return {
        "contract": VERSION,
        **objective.model_dump(mode="json", exclude={"claim_version", "basis_sha256", "unknowns"}),
    }


def validate_plan(plan, objective):
    if (
        plan.assertion != objective.question
        or plan.category != objective.category
        or plan.amount_paise != objective.amount_paise
        or len(set(plan.tools)) != len(plan.tools)
        or not set(SEARCH[objective.question]).issubset(plan.tools)
        or not set(plan.tools).issubset(objective.tools)
        or set(plan.evidence_types) != {TOOLS[t] for t in plan.tools}
    ):
        raise CaseError("INVALID_AI_PLAN")


def default_plan(objective):
    return EvidencePlan(
        assertion=objective.question,
        category=objective.category,
        amount_paise=objective.amount_paise,
        tools=SEARCH[objective.question],
        evidence_types=[TOOLS[t] for t in SEARCH[objective.question]],
        support_test="AUTHENTICATED_REQUIRED_RECORDS_MATCH_CLAIM",
        contradiction_test="VERIFIED_RECORDS_DISAGREE_OR_AMOUNT_DIFFERS",
        unresolved_test="MISSING_UNVERIFIED_STALE_OR_INCOMPLETE_PROOF",
        financial_authority=False,
    )


def expected_assessment(finding):
    if finding.contradictions or "CONFLICTING_EVIDENCE" in finding.unknowns:
        return "CONFLICTING_EVIDENCE", "ESCALATE_CONFLICT", "CONFLICTING_EVIDENCE", 2
    if finding.state == "SUPPORTED":
        return "SUPPORTED", "HUMAN_REVIEW", "NONE", 0
    return "INSUFFICIENT_EVIDENCE", "REQUEST_EVIDENCE", "MISSING_EVIDENCE", 1


RATIONALES = [
    "Verified required evidence supports the claimed amount.",
    "Required authenticated evidence is missing or incomplete.",
    "Verified source facts conflict; no resolution is authorized.",
]


def rejection(error, default):
    allowed = {
        "SPEND_LIMIT",
        "TOKEN_LIMIT",
        "ROUND_LIMIT",
        "TIMEOUT",
        "STALE_INPUTS",
        "PROVIDER_FAILURE",
        "INVALID_AI_SOURCE_FACT",
        "INVALID_AI_SOURCE_SPAN",
        "AI_CONFLICT_FACTS_REQUIRED",
        "AI_NUMERIC_PROOF_REQUIRED",
        "INVALID_AI_MISSING_EVIDENCE",
        "UNVERIFIED_AI_SCOPE",
    }
    return error.code if isinstance(error, CaseError) and error.code in allowed else default


def validate_synthesis(value: Synthesis, objective, finding, summaries=()):
    state, action, uncertainty, rationale = expected_assessment(finding)
    allowed = {p.record_id for p in finding.citations}
    facts = {r["record_id"]: r["facts"] for r in summaries}
    missing = {TOOLS[t] for t in SEARCH[objective.question]} - {r["kind"] for r in summaries}
    if set(value.missing_evidence_types) != missing:
        raise CaseError("INVALID_AI_MISSING_EVIDENCE")
    for observation in value.observations:
        if (
            observation.record_id not in value.record_ids
            or facts.get(str(observation.record_id), {}).get(observation.field) != observation.value
        ):
            raise CaseError("INVALID_AI_SOURCE_FACT")
    if state == "SUPPORTED" and not value.observations:
        raise CaseError("AI_NUMERIC_PROOF_REQUIRED")
    if "CONFLICTING_DELIVERY_RECORDS" in finding.contradictions:
        if not any(
            len({o.value for o in value.observations if o.field == field}) > 1
            for field in (
                "damaged_quantity",
                "delivered_quantity",
                "shipped_quantity",
                "unit_value_paise",
            )
        ):
            raise CaseError("AI_CONFLICT_FACTS_REQUIRED")
    if (
        value.amount_paise != objective.amount_paise
        or value.state != state
        or value.next_action != action
        or value.uncertainty != uncertainty
        or value.rationale != RATIONALES[rationale]
        or len(set(value.record_ids)) != len(value.record_ids)
        or not set(value.record_ids).issubset(allowed)
        or (state in {"SUPPORTED", "CONFLICTING_EVIDENCE"} and not value.record_ids)
        or (state == "SUPPORTED" and set(value.record_ids) != allowed)
    ):
        raise CaseError("INVALID_AI_SYNTHESIS")


def note(runtime, node, claim, data):
    key = digest({"ai_node": node, "claim": str(claim), "data": data})
    with runtime.transaction() as (session, run, row):
        if not scoped(session, InvestigationTrace, runtime.org, run_id=run.id, trace_key=key):
            session.add(
                InvestigationTrace(
                    organization_id=runtime.org, run_id=run.id, trace_key=key, node=node, data=data
                )
            )


def install(graph, runtime, provider, broker, wrapped, check, advance, emit):
    """Install phase nodes in the existing StateGraph, saver, runtime and executor."""
    from langgraph.graph import END, START

    from clearledger.investigation_contract import Objective

    def objective(frame):
        return frame.objectives[frame.index]

    def route(frame):
        frame.objectives = [Objective.model_validate(o) for o in runtime.snapshot["objectives"]]
        note(
            runtime,
            "director_route",
            objective(frame).claim_id,
            {"provider": provider.name, "financial_authority": False},
        )

    def call(phase, payload, frame):
        o = objective(frame)
        if frame.rounds >= runtime.limits.max_rounds:
            raise CaseError("ROUND_LIMIT")
        frame.rounds += 1

        def generate():
            reply = ARReply.model_validate(provider.reason({"phase": phase, **payload}))
            return {
                "reply": reply.model_dump(mode="json"),
                "phase": phase,
                "basis": digest(basis(o)),
                "metrics": getattr(provider, "metrics", {}),
            }

        value = runtime.operation(
            digest({"phase": phase, "basis": basis(o)}),
            "PROVIDER",
            generate,
            input_tokens=runtime.settings.llm_max_input_tokens,
            output_tokens=runtime.settings.llm_max_output_tokens,
            cost=getattr(provider, "reserved_cost_paise", 0),
            metadata={"provider": provider.name, "claim_id": str(o.claim_id), "attempt": 1},
        )
        return ARReply.model_validate(value["reply"])

    def plan(frame):
        o = objective(frame)
        try:
            if o.unknowns or o.category == "tax":
                raise CaseError("UNVERIFIED_AI_SCOPE")
            # Only assertion planning is reusable; never evidence or conclusions.
            with Session(runtime.engine) as session:
                cached = session.scalar(
                    select(InvestigationResult)
                    .join(
                        Investigation,
                        (Investigation.id == InvestigationResult.run_id)
                        & (Investigation.organization_id == InvestigationResult.organization_id),
                    )
                    .where(
                        Investigation.organization_id == runtime.org,
                        Investigation.case_id == runtime.case_id,
                        Investigation.provider == runtime.snapshot["provider"],
                        Investigation.snapshot["configuration_sha256"].astext
                        == runtime.snapshot["configuration_sha256"],
                        InvestigationResult.organization_id == runtime.org,
                        InvestigationResult.value["result"]["phase"].astext == "investigator_plan",
                        InvestigationResult.value["result"]["basis"].astext == digest(basis(o)),
                    )
                    .order_by(InvestigationResult.created_at.desc())
                    .limit(1)
                )
                value = cached.value["result"]["reply"] if cached else None
            reply = (
                ARReply.model_validate(value)
                if value
                else call(
                    "investigator_plan",
                    {
                        "objective": basis(o),
                        "document_ids": [],
                        "required_evidence_types": [TOOLS[t] for t in SEARCH[o.question]],
                    },
                    frame,
                )
            )
            if reply.plan is None or reply.synthesis is not None:
                raise CaseError("INVALID_AI_PLAN")
            validate_plan(reply.plan, o)
            frame.ai_plan = reply.plan.model_dump(mode="json")
            note(
                runtime,
                "investigator_plan",
                o.claim_id,
                {"plan": frame.ai_plan, "cached": bool(value), "fallback": False},
            )
        except Exception as error:
            frame.ai_fallback = True
            frame.ai_rejection = rejection(error, "INVALID_AI_PLAN")
            frame.ai_plan = default_plan(o).model_dump(mode="json")
            note(
                runtime,
                "investigator_plan",
                o.claim_id,
                {"plan": frame.ai_plan, "fallback": True, "rejection": frame.ai_rejection},
            )

    def tools(frame):
        o = objective(frame)
        plan = EvidencePlan.model_validate(frame.ai_plan)
        selected = list(
            dict.fromkeys([*plan.tools, "get_invoice_evidence", "get_remittance_evidence"])
        )
        for tool in selected:
            result = SearchResult.model_validate(
                runtime.operation(
                    digest({"ai_tool": tool, "claim": str(o.claim_id)}),
                    "TOOL",
                    lambda tool=tool: broker.search(o, tool).model_dump(mode="json"),
                    metadata={"tool": tool, "claim_id": str(o.claim_id)},
                )
            )
            frame.incomplete |= not result.search_complete or result.has_more
            if len(frame.hits) + len(result.items) > 50:
                frame.incomplete = True
            frame.hits = (frame.hits + result.items)[:50]
            frame.searched_tools.append(tool)
        frame.offered = [
            p for h in frame.hits if h.source_authenticated and (p := offered(h)) is not None
        ]
        if len(frame.offered) > 20:
            frame.incomplete = True
        frame.offered = list({p.record_id: p for p in frame.offered}.values())[:20]
        note(runtime, "evidence_tool", o.claim_id, {"tools": frame.searched_tools})

    def verify(frame):
        o = objective(frame)
        frame.proposal = Proposal(
            classification=o.category,
            suggested_state="INSUFFICIENT_EVIDENCE",
            citations=frame.offered,
            unknowns=o.unknowns,
            inference="NO_BACKED_CONCLUSION",
            next_action="HUMAN_REVIEW",
        )
        frame.verification, frame.offered = broker.verify(
            o, frame.proposal, frame.offered, authenticated_only=True
        )
        note(
            runtime,
            "evidence_verify",
            o.claim_id,
            {
                "verification": frame.verification.model_dump(mode="json")
                if frame.verification
                else None
            },
        )

    def synthesize(frame):
        from clearledger.investigation_director import consistency

        o = objective(frame)
        finding = consistency(
            o, frame.proposal, frame.verification, frame.offered, incomplete=frame.incomplete
        )
        if frame.ai_fallback or frame.incomplete or o.unknowns:
            frame.ai_fallback = True
            note(
                runtime,
                "investigator_synthesize",
                o.claim_id,
                {"fallback": True, "rejection": "UNVERIFIED_OR_INCOMPLETE_SCOPE"},
            )
            return
        # Summaries contain only authenticated source facts and deterministic validation.
        ids = {p.record_id for p in finding.citations}
        summaries = [
            {"record_id": str(h.id), "kind": h.kind, "facts": h.metadata.get("facts", {})}
            for h in frame.hits
            if h.id in ids and h.source_authenticated and h.source_integrity and h.is_current
        ]
        sources, span_catalog = evidence_catalog(frame.hits, finding.citations, o, runtime.org)
        try:
            reply = call(
                "investigator_synthesize",
                {
                    "objective": basis(o),
                    "plan": frame.ai_plan,
                    "required_evidence_types": [TOOLS[t] for t in SEARCH[o.question]],
                    "verified_assessment": {
                        "outcomes": [v.outcome for v in finding.source_facts],
                        "reasons": sorted(
                            {
                                reason
                                for v in finding.source_facts
                                for f in v.findings
                                for reason in f.reasons
                            }
                        ),
                    },
                    "evidence": summaries,
                    "evidence_spans": span_catalog,
                    "record_ids": [str(p.record_id) for p in finding.citations],
                    "document_ids": [str(p.document_id) for p in finding.citations],
                },
                frame,
            )
            if reply.synthesis is None or reply.plan is not None:
                raise CaseError("INVALID_AI_SYNTHESIS")
            validate_span_selection(
                reply.synthesis,
                sources,
                span_catalog,
                required=getattr(provider, "span_grounded", False),
            )
            validate_synthesis(reply.synthesis, o, finding, summaries)
            frame.ai_synthesis = reply.synthesis.model_dump(mode="json")
            note(
                runtime,
                "investigator_synthesize",
                o.claim_id,
                {"synthesis": frame.ai_synthesis, "fallback": False},
            )
        except Exception as error:
            frame.ai_fallback = True
            frame.ai_rejection = rejection(error, "INVALID_AI_SYNTHESIS")
            note(
                runtime,
                "investigator_synthesize",
                o.claim_id,
                {"fallback": True, "rejection": frame.ai_rejection},
            )

    def policy(frame):
        check(frame)
        finding = frame.findings[-1]
        if frame.ai_fallback:
            finding.state = (
                "INSUFFICIENT_EVIDENCE" if finding.classification != "tax" else "NEEDS_TAX_REVIEW"
            )
            finding.next_action = (
                "HUMAN_REVIEW" if finding.classification != "tax" else "TAX_REVIEW"
            )
            finding.unknowns = sorted(
                set(finding.unknowns)
                | {
                    "BUDGET_EXHAUSTED"
                    if frame.ai_rejection
                    in {"SPEND_LIMIT", "TOKEN_LIMIT", "TIMEOUT", "ROUND_LIMIT"}
                    else "PROVIDER_FAILURE"
                }
            )
        note(
            runtime,
            "policy_validate",
            objective(frame).claim_id,
            {"state": finding.state, "fallback": frame.ai_fallback, "financial_authority": False},
        )

    def review(frame):
        finding = frame.findings[-1]
        # Keep the existing financial state enum; expose the typed AI action in trace.
        action = (
            "HUMAN_REVIEW"
            if frame.ai_fallback or frame.error_code
            else expected_assessment(finding)[1]
        )
        if finding.classification == "tax":
            action = "TAX_REVIEW"
        note(
            runtime,
            "human_review_or_request_evidence",
            objective(frame).claim_id,
            {"state": finding.state, "next_action": action, "financial_authority": False},
        )
        advance(frame)
        frame.ai_plan = frame.ai_synthesis = None
        frame.ai_fallback = False
        frame.ai_rejection = None

    nodes = {
        "director_route": route,
        "investigator_plan": plan,
        "evidence_tool": tools,
        "evidence_verify": verify,
        "investigator_synthesize": synthesize,
        "policy_validate": policy,
    }
    policy.safe_finalizer = review.safe_finalizer = True
    for name, function in nodes.items():
        graph.add_node(name, wrapped(function))
    graph.add_node("emit", emit)
    graph.add_edge(START, "director_route")
    names = list(nodes)
    for left, right in zip(names[:-1], names[1:], strict=True):
        graph.add_conditional_edges(
            left,
            lambda s, right=right, left=left: (
                ("emit" if left == "director_route" else "policy_validate")
                if s["frame"]["error_code"]
                else right
            ),
        )

    def review_edge(state):
        f = state["frame"]
        finding = f["findings"][-1]
        if f["ai_fallback"] or f["error_code"] or finding["classification"] == "tax":
            return "human_review"
        if finding["contradictions"] or "CONFLICTING_EVIDENCE" in finding["unknowns"]:
            return "escalate_conflict"
        return "human_review" if finding["state"] == "SUPPORTED" else "request_evidence"

    graph.add_conditional_edges("policy_validate", review_edge)
    for name in ("human_review", "escalate_conflict", "request_evidence"):
        graph.add_node(name, wrapped(review))
        graph.add_conditional_edges(
            name,
            lambda s: (
                "emit"
                if s["frame"]["index"] >= len(s["frame"]["objectives"])
                else "investigator_plan"
            ),
        )
    graph.add_edge("emit", END)
