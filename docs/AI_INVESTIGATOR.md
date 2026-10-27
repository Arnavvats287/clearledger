# Bounded AR Investigator — ar-investigator-v2

Implementation and offline controls are verified. **Live acceptance has not passed.**
Real Gemini planning responses were rejected; no live AI synthesis, signed-support
or conflict result is claimed. Previous successful live extraction remains separate.
This optional mode is off by default and does not grant financial authority.

## Decisions and boundaries

The existing Python Director owns category/question routing, mandatory evidence,
tool admission, source verification, budgets, concurrency, currentness and transitions.
It uses the existing graph, PostgreSQL saver, immutable operation/results, outbox and
leases. No new framework, agent, service, migration or dependency.

Gemini has two bounded responsibilities:

- EvidencePlan: exact claim category/amount/assertion, relevant existing read-only
  tools and evidence types, explicit support/contradiction/unresolved tests. Damage
  requires WMS and signed POD. Tool order may be model-selected; the Director adds
  invoice/remittance context and will not allow omission of required proof.
- Synthesis: proposed SUPPORTED / INSUFFICIENT_EVIDENCE / CONFLICTING_EVIDENCE;
  HUMAN_REVIEW / REQUEST_EVIDENCE / ESCALATE_CONFLICT; offered record IDs, independently
  checkable numeric observations, missing evidence types, bounded rationale,
  confidence and uncertainty. It receives source facts and predicate results, **not
  a prefilled final recommendation to echo**. Rationale language is deliberately
  restricted to three review explanations; this is not an open-ended finance chatbot.

Input is scoped canonical claim/invoice IDs, integer paise and current authenticated
numeric evidence summaries. Extracted prose, arbitrary document instructions, names,
credentials, token maps, database handles, financial policy, write/posting tools and
network/filesystem capabilities are absent. All original documents in scope and new
cited source documents must be explicitly approved synthetic content. Unknown scope,
stale association, missing customer/invoice/amount and tax route to deterministic
review without a model call. Existing seven typed read-only evidence capabilities
remain the only retrieval surface; PostgreSQL enforces read-only tool transactions.

Broker/reader independently recheck company/customer/invoice relationships, original/
canonical SHA-256, exact spans, versions, chronology, relevance, source signatures,
contradictory records and completeness. Only authenticated pointers/facts enter AI
synthesis. Returned IDs must belong to those verified pointers; numeric observations
must exactly match supplied source fields and claim amount. Missing types must agree
with mandatory evidence. Conflict requires differing verified numeric observations.
Unsupported conclusions, invalid tools/amounts/citations/schema or provider failures
are rejected; deterministic retrieval/consistency remains the fallback. Invalid AI
cannot produce a supported finding; it becomes explicit insufficient/human review.
High model confidence grants no authority. No model output is rewritten or repaired.

Tax remains NEEDS_TAX_REVIEW with no AI tax conclusion. Existing domain Conclusion
and finance gates are preserved: conflicting evidence remains INSUFFICIENT_EVIDENCE
in the legacy financial finding, while the typed AI recommendation/trace explicitly
uses CONFLICTING_EVIDENCE/ESCALATE_CONFLICT. No deduction acceptance, claim settlement,
write-off, journal or cash/AR balance update occurs here.

## Why the existing LangGraph is justified

A single happy-path Python sequence would be enough for an in-memory demonstration.
This application already needs durable checkpoints, leased work, idempotent operation
results, concurrent/stale-source rejection and later evidence refresh. Reusing the
existing graph/saver makes each bounded phase resumable and inspectable without
repeating a potentially billed interrupted operation. There is no artificial agent
conversation or deliberating Director. The new path is a short per-claim graph:

`director_route -> investigator_plan -> evidence_tool -> evidence_verify ->
investigator_synthesize -> policy_validate -> request_evidence | escalate_conflict |
human_review -> emit`

Conditional edges use deterministically verified findings, completeness and rejection
state. The existing deterministic Investigator/graph path remains unchanged. The new
path makes at most one attempt per phase and obeys existing round/tool/token/spend/
time limits. All graph checkpoints and operation results are JSON, with no hidden
chain-of-thought, pickle, tracing service or raw prompts.

Only an assertion plan is reusable across runs. Cache scope includes company,
canonical case, claim, invoice, category, amount, question, tool allowlist, provider/
configuration and contract version. A cached plan is revalidated. Evidence facts,
currentness and synthesis are never reused across changed sources. Case/evidence
versions and financial snapshots are independently rechecked every phase and at emit.
Existing deterministic configuration digests are preserved; Gemini v2 changes cache
identity and makes older AI configurations stale rather than rewriting their history.

## Configuration and frontend APIs

Normal defaults remain deterministic, EXTERNAL_AI_ENABLED=false and
INVESTIGATION_EXTERNAL_ENABLED=false. For an explicitly approved synthetic run only,
set the actual server-side investigation_provider=gemini, gemini_model to the reviewed
model, both external flags, privacy_review_reference, ignored API key and reviewed
price/quota/budget limits. The request must also explicitly allow_external=true.
Automatic claim/outbox scheduling still starts deterministic investigations; flags
do not turn background work into paid autonomous calls. No automatic model escalation.

Frontend starts existing POST `/cases/{canonical_case_id}/investigations` with current
server version/hash and existing claim IDs:

```json
{
  "expected_case_version": 7,
  "expected_context_sha256": "<current-server-context-sha256>",
  "claim_ids": ["<existing-claim-uuid>"],
  "allow_external": true
}
```

Use the existing role/access boundary and Idempotency-Key; local bearer/X-Actor-ID
never supplies production or financial authority. The server chooses provider/model,
not client-supplied prompts, tool names or SQL. GET run/findings/trace and existing
case work/events/version endpoints expose:

- `investigator_plan.metadata.plan`: assertion, paise, evidence types/tests and tools;
  cached/fallback flags distinguish AI results from deterministic fallback plans.
- `evidence_tool` and `evidence_verify`: actual selected tools and deterministic
  factual predicates, contradictions, missing POD, source record IDs and hashes.
- `investigator_synthesize.metadata.synthesis`: only a strictly accepted AI proposal,
  numeric comparisons, references, rationale, confidence/uncertainty and review action.
- `policy_validate` and `human_review_or_request_evidence`: final deterministic state,
  selected action, fallback and financial_authority=false.
- Existing PROVIDER entries: reserved resources, known usage/latency/cost and fixed
  diagnostics. Schema errors expose only allowlisted fields/types; never values,
  messages, provider bodies, credentials or sensitive URLs.

Do not present a fallback plan as a successful AI plan, a provider generation as an
accepted recommendation, or SUPPORTED as approved credit. Human source/policy review
and independent finance maker-checker remain mandatory. After changing/disabled
provider configuration, ordinary currentness rules may mark historical AI runs stale;
their immutable trace remains accessible. Production identity/key custody is still G1.

## Actual live campaign — 2026-10-27 IST

Same existing Free-tier key/model gemini-3.5-flash-lite, operator-confirmed15 RPM/
250000 input TPM/500 RPD; no fresh real-time account counter or billing inspection
claimed. Conservative remaining-RPD CLI bounds420/414/408/402 account for known usage,
not external account activity. Exact-key model lookup passed before each attempt.
[Official pricing](https://ai.google.dev/gemini-api/docs/pricing) rechecked at
USD0.30 input/2.50 output per million including thinking. ECB2026-10-26 INR/USD
95.18546657132642116553450125; conservative110 plus20% ->3960/33000 paise per million.
3072-input/512-output reserves30 paise per attempt. Single sequential caller; SDK
attempts1, graph phase attempts1; PostgreSQL admission reserves3 HTTP operations.
Per-process slot/RPM and shared company/provider PostgreSQL quotas are distinct;
neither enforces global usage by another project/client. No billing/key/project change.

Only the existing minimal100-paise damage fixture and1000-paise invoice were used,
with deterministic extraction and actual FastAPI ASGI TestClient, PostgreSQL, outbox
and LangGraph. Planned later states use existing signed WMS/POD fixtures (one damaged
unit at100 paise; conflict two versus one). No LLM extraction, benchmark, original
pilot, hidden ground truth, realistic dataset, posting or frontend was touched.
All live attempts used ar-investigator-v1. The v2 enum request encoding was added
afterward and has not been sent to Gemini.

|Transport attempt|Actual result|Workflow latency|Known input/output tokens|Reservation|
|---|---|---|---|---|
|1|Pre-generation schema-import guard defect; deterministic fallback|3.4688551s|UNKNOWN|30 paise|
|2|Provider failure; original error/usage path lacked diagnostics; cause UNKNOWN|5.4975556s|UNKNOWN|30 paise|
|3|Response rejected; then-broad validation catch reported SCHEMA_VALIDATION; exact field not retained|6.6940002s|480/187|30 paise|
|4|SCHEMA_VALIDATION/literal_error for plan.support_test, contradiction_test, unresolved_test|6.1453727s|486/183|30 paise|

Attempt1's local defect is reproduced offline: importing the new application schema
after install_guard denies filesystem loading before token count/generate. Pure
schema loading now happens before the guard, like existing schema imports. Mocked
SDK startup passes and late imports remain denied. Attempt2's original cause cannot
be retrospectively proved. No successful observation is fabricated for either.

Attempts3/4 model generations returned, but no typed AI plan was accepted. Model
planning/synthesis usefulness **not established**. Observed WMS/POD selections are
the deterministic fallback plan, not claimed as AI success. Missing-case final state
INSUFFICIENT_EVIDENCE/HUMAN_REVIEW, MISSING_SIGNED_POD/PROVIDER_FAILURE; no AI citations,
no accepted AI rationale. Signed support and conflict were NOT RUN LIVE because each
campaign stopped on the first rejection. Offline scripted cases pass, separately.
All attempted live financial fingerprints were unchanged; allocations, settlements,
journals/lines, account balances and approvals all0. Source/financial authority=false.
HTTP/provider error status was not retained for these host validation failures:
UNKNOWN, not an invented400/429/outage. Hallucination or citation accuracy is NOT
EVALUABLE without an accepted plan/synthesis; three latest criterion literal violations
are demonstrated, not an assertion that all other generated facts were correct.

The exact latest blocker is literal noncompliance on the three criterion fields.
They were emitted as JSON Schema `const`. Google's supported constraint documentation
lists [string enum](https://ai.google.dev/gemini-api/docs/structured-output), not a
guarantee for string const. Provider-only serialization now uses single-value enums;
strict internal literals and semantic checks are unchanged. This is a documented
compatibility hypothesis supported by the field diagnostics, **not live-verified**
proof that the server ignored const. No model response was modified or reaccepted.

Campaign stopped after4 transport reservations, conservatively counted against the
four-attempt ceiling (one demonstrated pre-generation failure, two known returned
generations, one unknown). No SDK retries or further live calls. New reservations120;
prior323 -> **443 cumulative,57 paise remain** of500. Known conservative usage costs
9+8=17 paise for attempts3/4, not total spend or a bill; unknowns not invented/refunded.
Attempt2's original runner remainder display incorrectly used177 instead of its CLI
base147; accounting here derives from actual four reservations, not that display.
The helper now uses its supplied budget base; no reservation cap was bypassed and
the original observation file is retained unchanged.

Each generated database was upgraded/checked to0012_correlation then cleaned. Shared
development DB untouched. External AI, external investigation, extraction provider
and automation flags disabled in finally; .env unchanged. Future full proof needs
a separately reviewed two-phase smoke with v2 enum schema, current pricing/quota and
a reservation that fits the remaining57 paise. This task makes no further calls.

Ignored observations: local-data/live-gemini/d13b7b5f333045819aa815dbe0b61d25,
94d700c2e6664c87a5fd0a760009311f,242956c21869496c9aff6a9d497c8de5,
83200ec3410444d5a21b941a813d6d69. Logs and exact focused checks/results in STATUS.md.
