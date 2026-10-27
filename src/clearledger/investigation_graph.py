"""Bounded Director -> Investigator -> verifier -> consistency LangGraph."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from clearledger.case_domain import CaseError
from clearledger.evidence_contract import SearchResult
from clearledger.investigation_broker import Broker, offered
from clearledger.investigation_checkpoint import PostgresSaver
from clearledger.investigation_contract import Frame, InvestigatorReply, Objective, ProviderInput
from clearledger.investigation_director import consistency
from clearledger.investigation_provider import DeterministicInvestigator
from clearledger.matching import digest


class State(TypedDict):
    frame: dict


def build(runtime, provider):
    broker = Broker(
        runtime.engine, runtime.org, runtime.case_id, runtime.snapshot, runtime.settings
    )

    def wrapped(function):
        def node(state):
            frame = Frame.model_validate(state["frame"])
            try:
                if function not in (check, advance) and not getattr(
                    function, "safe_finalizer", False
                ):
                    with runtime.transaction() as (session, run, row):
                        runtime.guard(session, run)
                function(frame)
            except Exception as error:
                code = error.code if isinstance(error, CaseError) else "WORKFLOW_FAILURE"
                frame.error_code = (
                    code
                    if code
                    in {
                        "TIMEOUT",
                        "STALE_INPUTS",
                        "FORGED_CITATION",
                        "TOOL_LIMIT",
                        "TOKEN_LIMIT",
                        "SPEND_LIMIT",
                        "ROUND_LIMIT",
                        "REPEATED_TOOL",
                        "PROVIDER_FAILURE",
                        "INTERRUPTED_OPERATION",
                    }
                    else "WORKFLOW_FAILURE"
                )
                frame.incomplete = True
            return {"frame": frame.model_dump(mode="json")}

        return node

    def plan(frame):
        frame.objectives = [Objective.model_validate(o) for o in runtime.snapshot["objectives"]]

    def investigate(frame):
        if frame.rounds >= runtime.limits.max_rounds:
            raise CaseError("ROUND_LIMIT")
        objective = frame.objectives[frame.index]
        request = ProviderInput(
            objective=objective,
            hits=frame.hits,
            offered=frame.offered,
            searched_tools=frame.searched_tools,
        )
        key = digest(
            {
                "round": frame.rounds,
                "objective": str(objective.claim_id),
                "request": request.model_dump(mode="json"),
            }
        )
        reply = None
        for attempt in range(runtime.limits.max_attempts):
            try:

                def generate():
                    output = provider.generate(request)
                    parsed = InvestigatorReply.model_validate(output)
                    return {
                        "reply": parsed.model_dump(mode="json"),
                        "metrics": getattr(provider, "metrics", {"external_calls": 0}),
                    }

                value = runtime.operation(
                    digest({"key": key, "attempt": attempt}),
                    "PROVIDER",
                    generate,
                    input_tokens=runtime.settings.llm_max_input_tokens,
                    output_tokens=runtime.settings.llm_max_output_tokens,
                    cost=getattr(provider, "reserved_cost_paise", 0),
                    metadata={
                        "provider": provider.name,
                        "claim_id": str(objective.claim_id),
                        "attempt": attempt + 1,
                    },
                )
                reply = InvestigatorReply.model_validate(value["reply"])
                break
            except CaseError as error:
                if error.code != "PROVIDER_FAILURE" or attempt + 1 == runtime.limits.max_attempts:
                    raise
        frame.rounds += 1
        if reply.action == "SEARCH":
            if reply.tool not in objective.tools:
                raise CaseError("TOOL_NOT_ALLOWED")
            if reply.tool in frame.searched_tools:
                raise CaseError("REPEATED_TOOL")
            result = SearchResult.model_validate(
                runtime.operation(
                    digest({"tool": reply.tool, "claim": str(objective.claim_id)}),
                    "TOOL",
                    lambda: broker.search(objective, reply.tool).model_dump(mode="json"),
                    metadata={"tool": reply.tool, "claim_id": str(objective.claim_id)},
                )
            )
            frame.searched_tools.append(reply.tool)
            frame.incomplete |= not result.search_complete or result.has_more
            if len(frame.hits) + len(result.items) > 50:
                frame.incomplete = True
            frame.hits = (frame.hits + result.items)[:50]
            pointers = [p for h in result.items if (p := offered(h)) is not None]
            if len(frame.offered) + len(pointers) > 20:
                frame.incomplete = True
            frame.offered = list({p.record_id: p for p in frame.offered + pointers}.values())[:20]
        else:
            frame.proposal = reply.proposal

    def verify(frame):
        objective = frame.objectives[frame.index]
        result, citations = broker.verify(objective, frame.proposal, frame.offered)
        frame.verification = result
        frame.offered = citations

    def check(frame):
        frame.findings.append(
            consistency(
                frame.objectives[frame.index],
                frame.proposal,
                frame.verification,
                frame.offered if frame.verification else [],
                error=frame.error_code,
                incomplete=frame.incomplete,
            )
        )

    def advance(frame):
        frame.index += 1
        frame.hits, frame.offered, frame.searched_tools = [], [], []
        frame.proposal = frame.verification = None
        if frame.error_code:
            for objective in frame.objectives[frame.index :]:
                frame.findings.append(
                    consistency(objective, None, None, [], error=frame.error_code, incomplete=True)
                )
            frame.index = len(frame.objectives)
        else:
            frame.incomplete = False

    def emit(state):
        frame = Frame.model_validate(state["frame"])
        # Planning may have failed before its output could be checkpointed.
        if not frame.objectives:
            frame.objectives = [Objective.model_validate(o) for o in runtime.snapshot["objectives"]]
        existing = {f.claim_id for f in frame.findings}
        for objective in frame.objectives:
            if objective.claim_id not in existing:
                frame.findings.append(
                    consistency(
                        objective,
                        None,
                        None,
                        [],
                        error=frame.error_code or "WORKFLOW_FAILURE",
                        incomplete=True,
                    )
                )
        runtime.emit(frame)
        frame.finished = True
        return {"frame": frame.model_dump(mode="json")}

    graph = StateGraph(State)
    if getattr(provider, "phased", False):
        from clearledger.investigation_ai import install

        install(graph, runtime, provider, broker, wrapped, check, advance, emit)
        return graph.compile(
            checkpointer=PostgresSaver(runtime), name="clearledger-investigation-v1"
        )
    for name, function in [
        ("plan", plan),
        ("investigator", investigate),
        ("verifier", verify),
        ("consistency", check),
        ("next", advance),
    ]:
        graph.add_node(name, wrapped(function))
    graph.add_node("emit", emit)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan", lambda s: "emit" if s["frame"]["error_code"] else "investigator"
    )
    graph.add_conditional_edges(
        "investigator",
        lambda s: (
            "consistency"
            if s["frame"]["error_code"]
            else "verifier"
            if s["frame"]["proposal"]
            else "investigator"
        ),
    )
    graph.add_edge("verifier", "consistency")
    graph.add_edge("consistency", "next")
    graph.add_conditional_edges(
        "next",
        lambda s: (
            "emit" if s["frame"]["index"] >= len(s["frame"]["objectives"]) else "investigator"
        ),
    )
    graph.add_edge("emit", END)
    return graph.compile(checkpointer=PostgresSaver(runtime), name="clearledger-investigation-v1")


def execute(runtime, provider=None):
    if provider is None:
        provider = DeterministicInvestigator()
        if runtime.snapshot["provider"] != provider.name:
            from clearledger.investigation_provider import configured_provider

            try:
                provider = configured_provider(runtime)
            except Exception:

                class Unavailable:
                    name = runtime.snapshot["provider"]

                    def generate(self, request):
                        raise CaseError("PROVIDER_FAILURE")

                provider = Unavailable()
    if provider.name != runtime.snapshot["provider"]:
        raise CaseError("INVESTIGATION_PROVIDER_MISMATCH")
    runtime.begin()
    from sqlalchemy.orm import Session

    from clearledger.investigation_models import Investigation
    from clearledger.matching import owned

    with Session(runtime.engine) as session:
        terminal = owned(session, Investigation, runtime.org, runtime.run_id).status in {
            "COMPLETED",
            "AWAITING_REVIEW",
            "STALE",
        }
    if terminal:
        runtime.acknowledge()
        return "DELIVERED"
    saver = PostgresSaver(runtime)
    config = {**saver.config(), "recursion_limit": 256, "callbacks": []}
    with tracing_context(enabled=False):
        try:
            previous = saver.get_tuple(config)
            build(runtime, provider).invoke(
                None if previous else {"frame": Frame().model_dump(mode="json")},
                config=config,
                durability="sync",
            )
        except CaseError as error:
            if error.code not in {
                "CHECKPOINT_LIMIT",
                "CHECKPOINT_INTEGRITY",
                "CHECKPOINT_CONFLICT",
                "CHECKPOINT_WRITE_CONFLICT",
            }:
                raise
            frame = Frame(
                objectives=[Objective.model_validate(o) for o in runtime.snapshot["objectives"]],
                error_code=error.code,
                incomplete=True,
            )
            frame.findings = [
                consistency(o, None, None, [], error="WORKFLOW_FAILURE", incomplete=True)
                for o in frame.objectives
            ]
            runtime.emit(frame)
    runtime.acknowledge()
    return "DELIVERED"
