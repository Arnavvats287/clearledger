# Director–Investigator contract v1

Milestone 07 implements the original `prompts/07-directed-investigation.md`.
Algorithm: `director-investigator-v1`. This is investigation metadata and factual
hypotheses, never claim acceptance, tax adjudication, settlement or posting.
Financial CSV `DATA_CONTRACT.md` v1.0 and document/evidence contracts are unchanged.

## Architecture and authority

The Python Director snapshots the canonical case version/context, unresolved claim
versions and per-claim bases, available source kinds, verified customer, unambiguous
invoice relationships, provider configuration digest and hard limits. Missing
customer/amount/invoice or uncertain extraction is explicit uncertainty. A referenced
invoice does not establish payment intent. Existing matching evidence is still required.

LangGraph 1.2.17 (locked) executes `plan -> investigator -> verifier -> consistency ->
next -> emit`, including bounded search loops. PostgreSQL is authoritative. A custom
JSON-only `BaseCheckpointSaver` implements native LangGraph checkpoints and pending
writes; no pickle, remote checkpoint service, vector database or extra queue is used.
Thread identity is organization/canonical-case/run. LangSmith tracing is explicitly
disabled even when tracing environment variables are present. There is no Director LLM.

The provider receives a strict `ProviderInput`, never an engine, session, original
document, source key, filesystem path, arbitrary URL or executable callback. Its only
possible requests are the seven existing milestone 06 capabilities. The trusted broker
sets company/customer/case/claim/invoice scope in server code and invokes the existing
reader in a fresh PostgreSQL READ ONLY transaction. Query/lock timeouts remain enforced.
The graph host alone writes workflow/outbox/case review metadata. This does not grant
the isolated Investigator a database mutation capability.

Search results have privacy-projected excerpts and safe typed facts. Model citations
must exactly equal offered pointers: record/document IDs, versions, hashes, page,
Unicode start/end offsets and projected excerpt. The broker independently resolves
the privileged original citation and invokes the existing deterministic verifier.
It also retains independently discovered contradictory/required pointers; selective
model citation cannot hide opposing records. Unknown conditions, unsigned origins,
missing signed POD, ambiguous invoices and incomplete search abstain. Source-attested
facts are not proof that a deduction is legitimate. Tax always requires specialist review.

## APIs

All routes use the existing strong local document bearer credential and tenant scope.
`X-Actor-ID` is provenance, not an authenticated role or financial permission.
`CASE_READ_TOKEN` is GET-only. Requests use bounded, duplicate-key rejecting JSON;
responses are no-store. List/trace pagination uses `limit` (1–100) and `offset`.

| Method/path | Contract |
|---|---|
| POST `/cases/{case_id}/investigations` | `StartInput`; Idempotency-Key UUID and actor headers required |
| GET `/cases/{case_id}/investigations` | Run summaries, newest first |
| GET `/investigations/{run_id}` | Persisted counters, input hash, source/result versions, stale flag |
| GET `/investigations/{run_id}/findings` | Immutable hypotheses plus current per-claim validity |
| GET `/investigations/{run_id}/trace` | Sanitized operation metadata, usage and reservations |
| POST `/investigations/{run_id}/resume` | `expected_run_version`; only resumable, non-active deliveries |

Example body, using actual IDs/versions from the case APIs:

```json
{
  "expected_case_version": 7,
  "expected_context_sha256": "<actual-64-character-case-context-sha256>",
  "claim_ids": ["<actual-claim-uuid>"],
  "allow_external": false
}
```

Creation atomically commits the run, immutable request provenance and existing outbox
event. Same-key different content conflicts; concurrent different keys for identical
snapshots share one run and event. No request changes receipt/invoice balances or
claims' adjudication states. Run processing uses the existing worker:

```text
uv run --frozen python -m clearledger.case_worker --once --limit 100
```

Run states: QUEUED -> RUNNING -> COMPLETED / AWAITING_REVIEW / STALE. Terminal rows and
histories cannot be rewritten. Findings separate classification, SOURCE_FACTS_ONLY
verification, precise projected citations, inference, contradictions, unknowns and next
action. States are SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE or NEEDS_TAX_REVIEW.
Every finding has `requires_human_review=true` and `financial_authority=false`.
COMPLETED means execution completed; the recommendation remains AWAITING_REVIEW.
Fresh cases move only through legal metadata transitions to AWAITING_REVIEW. Stale
runs never change a newer case. `is_current` is independently computed per claim;
the header `X-Investigation-Stale` describes the whole run snapshot. Historic supported
findings with `is_current=false` must never be consumed as current evidence.

## Bounds, recovery and new evidence

Defaults: 10 claims/run (configurable to 20), 24 Investigator rounds (max 32), 32 tool
calls (max 128), 65,536 reserved input tokens, 32,768 reserved output tokens, zero
permitted estimated external spend paise, 30,000 ms wall-clock decision deadline
(max 120,000), and two attempts per provider request (max three). Configure the typed
JSON `INVESTIGATION_LIMITS`; each run preserves its original limits across restarts.
Per-request input/output reservations use existing LLM_MAX_* limits. Offline stubs
reserve the same admission units to test limits; these are not measured API usage.
Search responses are bounded to 20 items/tool, 50 accumulated hits and 20 source
pointers/objective; overflow marks incomplete and cannot support a positive finding.
The existing verifier independently enforces its complete bounded contradiction scan.

PostgreSQL reservations commit before calls and never refund on failure/crash. Results
are immutable, keyed by operation/request digest and attempt. Resume reuses committed
successes without another provider call. A reserved operation without a committed
result yields INTERRUPTED_OPERATION/review, since remote completion cannot be known.
Round/tool/token/spend exhaustion, repeated tools, malformed output, failures and
deadline expiration yield explicit review with sanitized trace. No expensive-model
escalation exists. SDK transport calls are subprocess-bounded; process termination
and database cleanup may extend elapsed time beyond the decision deadline, but a late
result cannot support a positive finding. Infrastructure outages can leave a retryable
outbox delivery; exhausted delivery attempts remain visible as DEAD for operator review.

Every write/checkpoint is fenced by an unexpired matching outbox lease and its exact
organization/case/run event. Short transactions heartbeat leases; no company write
lock spans model or tool execution. An expired worker cannot write after replacement.
Resume uses optimistic run versions and never resets attempts, usage or deadline.

New evidence appends per-claim invalidations and schedules only previously investigated,
affected claims, using the existing source/category/invoice relevance logic. Unaffected
findings retain their histories and independent per-claim validity. If affected claims
exceed the configured run limit, an explicit investigation.limit_reached event lists
them and routes the case to AWAITING_REVIEW; nothing is silently truncated. Operators
can submit bounded subsets after reviewing/refreshing the case. Irrelevant evidence does
not trigger speculative investigation of other claims.

## Optional Gemini adapter (disabled)

Defaults are `INVESTIGATION_PROVIDER=deterministic`,
`INVESTIGATION_EXTERNAL_ENABLED=false`, `EXTERNAL_AI_ENABLED=false`. Tests additionally
force these defaults and inject `FakeInvestigator` only inside the trusted test host.
External calls require both enablement gates, explicit per-run allow_external, a privacy
review reference, approved synthetic originals (including retrieved external evidence),
configured key/model and known reviewed integer-paise token prices. Real financial
documents remain prohibited without explicit privacy/provider review and authorization.

The optional adapter reuses the existing isolated Google GenAI worker with a fixed
investigation schema/system instruction, tools=[], automatic function calling disabled,
exact model availability/full-request token validation and SDK retry limit one. Graph
attempt limits are persisted separately. The shared process-local gateway admits one
call per cached configuration; shared PostgreSQL company/provider minute/day quotas
also include document extraction. Configuration rotation may create a separate local
gateway; shared quotas remain authoritative. Original text and secrets are not logged.
Usage/latency/estimated cost are sanitized metadata when available; reservations remain
conservative. Caching here is durable per-run operation reuse, not evidence authority
or a cross-run semantic cache. Existing document extraction caching is unchanged.

No live Gemini call, provider accuracy, actual cost, production RBAC/RLS, publisher
PKI/key custody or Argon benchmark/ablation is claimed. Those limitations remain open.
The pilot ZIPs and hidden answers are not inputs to these isolated application tests.

## Verification traceability

`test_investigation_domain.py` checks independent abstention/authority properties,
strict capability schemas, tax review and deterministic replay. `test_investigations.py`
uses real PostgreSQL for missing/signed/contradictory evidence, forged quotes/hashes/
offsets/record IDs, injection/privacy/tracing isolation, limits, retries, concurrent
different-key requests, stale inputs, native checkpoint recovery, immutable history,
tenant/auth boundaries, selective reruns and lease ownership. Existing restart tests
fingerprint all new workflow/checkpoint tables across fresh processes/connections and,
with the isolated runner, an owned PostgreSQL container restart. All earlier checks
remain required. Actual executed commands, counts and private logs are in STATUS.md.

Every terminal result emits a sanitized trace/event even if admission failed before the first tool call. Checkpoint payloads are limited to 512,000 JSON characters; capacity/integrity failures produce explicit review. Terminal database results remain authoritative if a crash occurs after emission but before the final checkpoint/acknowledgement.
