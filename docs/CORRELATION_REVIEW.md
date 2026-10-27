# Source-backed correlation review — v1

This is nonfinancial exception-case association, not payment intent inferred from a
model, cash allocation, approval of a deduction, customer communication or posting.
No new agent, service, framework or dependency. CSV1.0 and evidence-1.0 are unchanged.

## Working sequence

1. Upload/extract through the existing `/documents` APIs. Validated SUCCEEDED or
   NEEDS_REVIEW facts publish their original transactional outbox event. The existing
   case consumer creates claims/ClaimSource links; no manual duplicate claim entry.
2. With `CASE_AUTO_CORRELATE_EXTRACTIONS=true`, the worker creates an immutable,
   source-snapshot-keyed correlation task. Default false preserves legacy behavior.
3. It searches **current independent authenticated REMITTANCE evidence manifests for
   that exact immutable document**. Existing HMAC source registry, manifest/original/
   canonical hashes, span labels, document version, chronology, effective dates and
   signed/approved source status are revalidated. The UTR is parsed from the signed
   excerpt, not taken as verified intent from an LLM output or operator checkbox.
4. Receipt/UTR equality, immutable bank-import provenance, available receipt amount,
   open invoice/version, exact extracted invoice reference and independently resolved
   receipt customer must agree with the authenticated source owner. Model UTRs, if
   present, must not conflict. Names, amounts alone and invoice strings grant no intent.
5. A unique complete proof yields READY_FOR_REVIEW, **not automatic confirmation**.
   Missing/ambiguous/conflicting evidence yields an actionable task. Controller
   confirmation cannot override absent proof. Rejection records a terminal decision.
6. Confirmed proof creates the existing immutable LINKED DocumentAssociation and
   merges case metadata using the existing monotonic merge logic. The exact invoice
   is exposed through the correlation decision, without fabricating a matching
   proposal. Financial balances, journals and allocations remain unchanged.
7. With `CASE_AUTO_INVESTIGATE_EXTRACTIONS=true`, merge/confirmation reevaluation
   starts or refreshes the existing bounded deterministic LangGraph. Relevant new
   evidence invalidates affected findings; original claims are retained. Unknowns
   cannot become a supported financial decision. A correlated uncertain extraction
   may retrieve scoped evidence/citations while still returning insufficient/review.

Both options are default-off and must be set for the existing worker, using the
configured company/database/store. External AI and investigation flags remain false:

```powershell
$env:CASE_AUTO_CORRELATE_EXTRACTIONS = "true"
$env:CASE_AUTO_INVESTIGATE_EXTRACTIONS = "true"
uv run --frozen python -m clearledger.case_worker --once --limit 100
```

The ordinary ongoing worker drains later events; a bounded `--once` batch may need
another drain. Already-delivered historic extraction events are not automatically
replayed; existing cases may use the explicit refresh API, without recreating claims.

## Frontend-facing APIs

All new routes use the existing ReviewIdentity boundary. Reviewer authority is
rechecked under the company lock. No document bearer or X-Actor-ID promotion.
Missing trusted identity fails closed. Explicit loopback demo roles authorize only
local operational review and are labelled LOCAL_DEMO_ONLY; they do not authenticate
source manifests, grant production identity or authorize finance. Real deployment
requires the existing reviewed identity adapter/REVIEW_ACCESS_ENABLED profile.

|Method/path|Use|
|---|---|
|GET `/review/cases`, `/review/cases/{case_id}`|Canonical cases and linked receipt/invoice/document IDs|
|GET `/review/cases/{case_id}/correlation-tasks`|Latest task per document; limit/offset; `history=true` for immutable snapshots|
|POST `/review/cases/{case_id}/correlation-tasks/refresh`|Analyst/controller recomputes proof; strict empty JSON `{}`, idempotent by source snapshot, Idempotency-Key required|
|POST `/review/correlation-tasks/{task_id}/decision`|Controller CONFIRM/REJECT; expected case version/context and task input hash; Idempotency-Key|
|GET `/review/correlation-tasks/{task_id}/decisions`|Immutable decision/actor/association IDs and current staleness|
|GET `/cases/{case_id}/claims`, `/events`, `/versions`, `/work`|Original claim provenance, lifecycle history, pending worker/error state|
|GET `/documents/{document_id}/text`, `/extractions`, `/associations`|Original extraction and current/stale association provenance|
|GET `/cases/{case_id}/investigations`|Current/stale persisted investigations|
|GET `/investigations/{run_id}/findings`, `/trace`|Citations, unknowns, verification, next action and execution trace|
|Existing `/cases/{case_id}/evidence/records/{record_id}` and native pointers|Privileged source evidence and exact hashes/spans|

Investigation lists are canonical-case scoped. Pre-merge runs remain immutable and
addressable through `/investigations/{run_id}` and their original findings/trace;
their currentness becomes stale after merge. They are not copied into the new case.

Decision body uses current server values, never invented hashes:

```json
{
  "expected_case_version": 7,
  "expected_context_sha256": "<current-case-context-sha256>",
  "expected_task_sha256": "<task-input-sha256>",
  "decision": "CONFIRM"
}
```

Role/scope/authority failures deny access; stale evidence/versions and already-decided
tasks return conflicts. A manual task proposer cannot confirm their own task. Both
confirmed and rejected decisions are append-only. A rejected task stays rejected for
unchanged evidence. Changed evidence creates a distinct snapshot; old decisions stay
visible/stale. Same-key replay returns the same decision only for current proof and
identical content; conflicting replays cannot create a new association.

Task responses expose reason, candidates, `next_action`, status and `is_stale`.
Missing proof requests an authenticated remittance with a UTR; ambiguity requires a
unique bank reference; source/identity conflicts require correction; exhausted search
requires bounded review. Every response explicitly has financial_authority=false.
Confirmation never manufactures a source signature or an approval. The old
`POST /documents/{id}/correlate` cannot bypass review once this document has a task.

## Bounds, persistence and remaining scope

Migration0012_correlation adds only correlation_tasks/correlation_decisions, scoped
foreign keys, unique snapshot/decision/request keys and immutable/deferred integrity
triggers. It does not rewrite financial tables or historical case relationships.
Apply with `uv run --frozen alembic upgrade head` against the intended application
database before enabling these options. This task tested upgrades/roundtrips only in
disposable databases; it did not upgrade, reset or downgrade the shared development DB.
One company lock serializes decisions and snapshot checks; concurrent different keys
yield one committed decision and one conflict. Source change and reevaluation events
are deduplicated; unchanged record replays publish no new work. New association
currentness includes signature trust, source revisions and financial input versions;
missing trusted runtime configuration fails closed. Legacy context ordering is kept.

Hard limits:50 current remittance manifests,100 receipt/source proof checks,50 distinct
candidates; >100 same-reference bank rows is incomplete. Budget exhaustion overrides
any apparent uniqueness. Source-change task fanout is capped at200 documents. All
existing investigation tool/claim/token/time/lease limits remain binding.
Manual refresh is limited to100 case documents; linked invoice analysis to2000 IDs.

This first workflow requires one unambiguous document/receipt/invoice scope and an
eligible open/available snapshot. Multi-UTR/multi-invoice, missing identifiers, absent
bank/customer proof, settled-only cases or conflicting authorities remain review;
no arbitrary selection or inferred settlement. Case merges preserve immutable history;
this does not implement unmerging/accounting reversals. A source signature validates
the scoped manifest contract, not PDF PKI or a real bank connection. Production G1,
upstream key custody and real-customer validation are not resolved by fixture signatures.

`tests/test_correlation_workflow.py` exercises actual APIs, PostgreSQL, outbox and
LangGraph with fake extraction and independent **test-only** signing/identity roots.
It covers complete/uncertain, missing/conflicting/ambiguous, rejected, late/revised
evidence, replay/concurrency, authority/tenant/immutability, migration and budget cases.
No Gemini call or new live-accuracy claim;229 paise authorization remains unchanged.


## Task-bound proof inspection before association
GET `/review/correlation-tasks/{task_id}/proof?expected_task_sha256=<server hash>`
returns `RecordView[]` only for authenticated/current records already captured in
that owned task's snapshot and exact document. Review READ identity is required;
company lock and current task/context validation reject stale basis409. Unknown/
other-tenant tasks404; actor labels do not authenticate. Revoked/unsigned source
records never become trusted proof. This enables reviewer inspection before a
customer association exists without relaxing the Investigator's verified-customer
scope or seven evidence tools. No mutation, financial authority or schema change.
Frontend sends the exact server-provided hash; mismatch requires refresh/review.
