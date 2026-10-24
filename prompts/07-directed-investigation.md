# CODEX TASK 07 — Director–Investigator workflow with bounded LangGraph

Read specs and previous modules. Do NOT invent legal rules or posting privileges.

## Goal
Investigate unresolved deductions using a deterministic Director and read-only tool-restricted Investigator, with evidence-backed structured hypotheses and human-visible outcomes.

## Implement
1. Director (Python) takes case version, unresolved claims, available source types and configured tool/token/round limits. Emits typed investigative objectives. No Director LLM required.
2. LangGraph nodes: plan objectives -> investigator -> evidence verifier -> rule/consistency check -> next objective or stop -> emit recommendation. Graph durable checkpoints keyed to case/run IDs; DB remains source of truth.
3. Investigator has only allowlisted tools from milestone 06, scoped in server code. Add optional structured LLM adapter and deterministic replay/stub for no-credential tests.
4. Hypotheses include precise source pointers, proposed claim classification, unknowns and next action. States are `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, `NEEDS_TAX_REVIEW`, etc. Never confuse hypothesis with acceptance.
5. Strict max rounds, max tool calls, timeout and spend budget; on failure/timeout yield safe `AWAITING_REVIEW` with trace.
6. Emit investigation trace into event history with sanitized model/tool metadata. New evidence should re-run only affected claims.

## Tests
Missing evidence, contradictory proof, repeated tools/loop budget, forged quote, prompt injection document, cross-company retrieval, graph resume/retry, deterministic stub producing identical output. Confirm graph has NO posting or arbitrary SQL tool.

## Exit
Run no-API-key test flow and optional model smoke only when credentials provided; report actual costs if measured. Update status. STOP.
