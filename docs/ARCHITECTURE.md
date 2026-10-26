# Architecture and runtime boundaries

The opt-in first-investigation bridge reuses case_processing.reevaluate and
investigation_service.schedule_affected inside the existing outbox transaction.
Source-backed extraction -> case/ClaimSource creation was already implemented;
only the first deterministic investigation trigger was missing. No new worker,
queue, model framework, schema/migration or finance capability is introduced.
Reason-code validation and privacy projection distinguish explicit field evidence
from status/category words before any claim enters this path. Contracts:
[DOCUMENTS.md](DOCUMENTS.md), [INVESTIGATIONS.md](INVESTIGATIONS.md).

## Deployment V1
Local Compose: `api` (FastAPI/Python), `db` (PostgreSQL), and later `worker` + `redis` and `web` (Next.js). A local file-store adapter persists immutable raw bytes in a volume. No production integrations. One company, INR only. Database = authoritative transactional source; job queue = delivery mechanism; graph checkpoint = investigation progress, never ledger truth.

## Layer split
1. **Ingestion** — CSV/document ingestion, hashes, parse validation, provenance, idempotency keys.
2. **Domain** — `Receipt`, `Invoice`, `Allocation`, `Claim`, `Case`, `Document`, `Approval`, `JournalProposal`, `PostedJournal`.
3. **Deterministic matching** — customer verification, exact matching, constrained subset candidates, payment dates and partial allocation.
4. **Evidence** — allowlisted typed read-only retrieval and exact source pointers. Initially indexed relational/FTS search; add semantic search only if justified by evaluation.
5. **AI investigation** — isolated document extraction; deterministic director choosing objectives; optional structured LLM investigator, with strict step/time/token budgets.
6. **Policy** — versioned preconditions, tax scope guardrails, authorization, approved treatment.
7. **Accounting** — balanced journal proposals; transactional simulator with locks, idempotency, allocation ledgers and status checks.
8. **Case lifecycle** — persistent events, late evidence, dispute drafting, reviewer actions, audit timeline.
9. **UI** — cash inbox, case workbench, proposal approvals, analytics.

## Trust boundary
Untrusted PDF, bank memo, remittance emails and OCR -> parse/extraction node with NO tools -> typed data + source offsets. Downstream Investigator only receives typed claims/search hints; retrieved source snippets remain untrusted and never authorize calls or change instructions. Evidence validator checks ID, hash, span, customer, effective date and record status. Only deterministic services with authenticated actor and transactions can mutate financial tables.

## Directed investigation: actual rationale
The so-called Alien-inspired design is a **separation of responsibilities**, not a requirement for two LLMs. Director (initially code) has global unresolved claim amounts, available evidence types and budgets; sends scoped search objectives. Investigator has local read-only evidence tools; returns structured candidate hypotheses. Validator and policy engine decide whether hypotheses have backing. If no additional useful evidence is available or budget expires, abstain. Benchmark against single-investigator and deterministic-only alternatives.

## Event path
`source.accepted` -> `receipt.created` / `document.added` -> `matching.requested` -> `allocation.proposed` OR `case.opened` -> `evidence.requested` -> `investigation.completed` -> `decision.proposed` -> `approval.requested` -> `journal.approved` -> `journal.simulated_posted` -> `reconciliation.completed`. For late docs: `document.added` with candidate case reference -> `case.version_incremented` -> only affected claims re-evaluated.

Use transactional outbox to enqueue work without losing updates when DB commits but worker delivery fails. Consumer deduplicates event IDs and retains retry count / dead-letter statuses.

## Data isolation and practical scale
- Row ownership key per organization. Initial single-organization UI is not permission to omit backend scoping.
- Use indexes on external receipt reference, normalized payer, invoice customer/status, claims case/status, evidence source/type and created_at.
- Match search is bounded by maximum open invoice count, time limit, and top-K candidate limit; return `AMBIGUOUS_OR_BUDGET_EXCEEDED` if incomplete.
- Optional invoice combinations may have equal sums. A single exact subset is NOT proof of intent.

## Repository target (evolve only when milestone requires it)
```
apps/api/                    # API route, app startup, dependencies
apps/web/                    # Later Next.js UI
packages/core/               # pure money/matching/policy/accounting domain
packages/intelligence/       # extraction/director/investigator
packages/services/           # ingestion/case/application/posting
infra/                       # docker, migrations, storage
fixtures/                    # existing references; Argon owns demo/evaluation data
scripts/                     # dev setup, verification, bench (no dataset generation)
 tests/                      # unit/integration/property/e2e
```

Phase 00 can choose a simpler conventional Python package layout. Avoid creating empty skeletons for every future package.

## Milestone 04 implementation boundary

The implementation stays in `src/clearledger`, extending the existing service/SQLAlchemy layout. `document_api` authenticates local document access and derives company scope; `documents` is the transactional metadata orchestrator; `document_runtime.LocalOriginals` stores exclusive content-addressed originals. `document_parse` runs in `document_worker`, with bounded PDF/MIME processing and no network. `document_contract`, `remittance_parser` and `document_privacy` define typed untrusted facts, deterministic-first parsing, independent source/semantic validation and private offset-preserving projection/restoration. That milestone introduced no persistent claims/cases or general evidence adjudicator; milestone 05 now adds the case subsystem below.

Approved Gemini transport exception: the typed `extraction_provider.Transport` receives only sanitized pages. `gemini_worker` uses the official SDK in a separate minimal-environment process; `worker_security` denies tools, local DB/arbitrary network and application-file reads. Only the configured Google host/public TLS endpoints are allowed. This transport is not an investigator, agent, tool runtime or policy service. The parser retains zero network. Shared Python audit/OS resource guards are defense in depth, not a separate OS-principal/container sandbox against arbitrary dependency RCE; deployment remains local/synthetic-only.

External AI is disabled by default and requires explicit synthetic approval, server/provider/model/key/review configuration and request opt-in. The orchestrator independently validates provider output before appending immutable extraction/audit metadata; no DB/session is passed to the provider. Raw bytes and private mappings never enter model content. Synchronous requests retain the existing company transaction lock through bounded processing, favoring consistent idempotency over throughput; there is no Redis/worker queue. Gateway/worker concurrency and attempt limits are per API process. Milestone 04B adds independently committed, append-only PostgreSQL reservations under a separate company/provider advisory lock for shared daily request/token budgets and rolling-minute RPC admission. This is not an account-global Google quota; see docs/DOCUMENTS.md for conservative charging, cache identity and limits.

Five additive immutable tables record documents, extractions, candidate/reference associations, operation keys and document audit events. Exact UTR correlation is separately attested, bounded, scoped and version checked; conflicting/unknown owners, stale extraction or multiple receipts abstain. It never creates financial allocations, changes receipt/invoice versions/balances or grants authenticity/legitimacy. Milestone 05 supplies case/claim lifecycle and late-evidence event replay; milestone 06 supplies generalized financial evidence validation. Full document/API/privacy/format contracts are in [DOCUMENTS.md](DOCUMENTS.md); CSV DATA_CONTRACT 1.0 is unchanged.

## Milestone 05 persistent case boundary

`case_domain` and strict `case_schemas` define state/paise rules and typed contracts.
`case_models` supplies scoped PostgreSQL aggregates/history; `case_repository`
encapsulates bounded membership/lookups. `case_sources` independently revalidates
existing financial/document contracts; `case_lifecycle` records revision/invalidation
transactions. `case_service` owns versioned commands, `case_api` authentication and
safe typed transport. `case_events` publishes with the original source transaction;
`case_processing` handles only known event kinds and deterministic review metadata.
`case_outbox` leases/acks/retries with transactionally deduped effects; `case_worker`
is the separate bounded polling process. No queue framework, Redis or new dependency
is introduced. This keeps database ownership outside extraction and preserves the
existing application/matching services. Details and operational bounds: [CASES.md](CASES.md).

Immutable case-local proposal bindings/invalidation overlays preserve existing
matching proposal history. Merges retain physical source IDs and canonical redirects.
Company locks plus CAS, compound tenant FKs, commit-required revisions and append-only
triggers protect case writes. No case component calls Gemini or financial posting.

## Milestone 06 evidence boundary

`evidence_contract` defines the separate evidence-1.0 schema and typed read capabilities;
`evidence_domain` contains source-signature/span/date/numeric checks. `evidence_models`
and `evidence_repository` implement immutable scoped revisions/provenance and bounded
structured/FTS selection. `evidence_ingestion` is the authenticated writer and existing
outbox publisher, outside the tool boundary. `evidence_reader` runs in PostgreSQL READ
ONLY transactions; `evidence_verification` checks factual predicates and contradictions.
`evidence_runtime` bounds request-local original reuse. `evidence_api` provides typed
read-only search/verification and privileged immutable reviewer pointers.

No new database/queue/model framework or dependency. Existing matching/document row
locks remain unchanged outside the enforced read-only scope. Case-source contexts now
include relevant external evidence; per-claim bases filter category/invoice relevance,
and batch reevaluation/hypothesis reads reuse one consistent context. Empty external
contexts retain existing hashes. See [EVIDENCE.md](EVIDENCE.md) for trust, limits and
protocol. This adds factual verification, not financial policy or claim approval.

## Milestone 07 bounded investigation

`investigation_contract/director` define typed objectives, hypotheses and conservative
consistency independently of the graph framework. `investigation_models/service`
own snapshots, scoped request identity, selective invalidation and run read models.
`investigation_broker` is the trusted bridge to the seven existing read-only tools and
deterministic verifier; only projected DTOs reach `investigation_provider`.
`investigation_graph` implements the original required LangGraph nodes.
`investigation_checkpoint` persists native JSON checkpoints/pending writes in PostgreSQL;
`investigation_runtime` fences short metadata transactions and durable reservations
against the exact leased outbox/run. No write transaction spans a model/tool call.
`investigation_api` exposes authenticated start/resume and bounded read/history views.

The existing outbox dispatches investigation events to the checkpointed host outside
its ordinary single-transaction consumer; other consumers retain existing semantics.
Crash recovery reuses committed operations, never refunds uncertain calls and rejects
expired workers. New evidence invalidates only affected claim findings. The existing
isolated Gemini worker supports a fixed optional investigation schema; external
execution and LangSmith telemetry stay disabled. LangGraph is required by the original
07 prompt; its locked dependencies introduce no extra service. See
[INVESTIGATIONS.md](INVESTIGATIONS.md). No policy/posting or approval capability is added.

## Milestone 08 accounting boundary

`finance_contract/domain` define exact money, policies, journals and state transitions;
`finance_identity` is a trusted identity port, denied by default. `finance_models` and
additive 0010 persist scoped policies/reviews/approvals/ledger/allocations/history.
`finance_repository/validation` separate snapshots and read-only evidence/rule checks;
`finance_service` owns proposal/review/CAS; `finance_posting` locks/rechecks/commits
atomic simulation. `finance_lifecycle/invalidation` derive proven settlement metadata
and conservative invalidations. `finance_api` is separate from document-token access.
Case contexts add posted T1 ownership only when it exists; unposted hashes are retained.
Claim settled counters derive from ledger records, not hypotheses. No graph receives
finance tools/credentials; no new dependency/service/queue is introduced. Contract:
[ACCOUNTING_SIMULATOR.md](ACCOUNTING_SIMULATOR.md).

## Milestone 09 review boundary

`review_contract` defines strict operational DTOs; `review_identity/password/users` isolate local demo authentication from the trusted finance identity port. `review_sources` uses the existing PostgreSQL READ ONLY evidence reader. `review_lifecycle` independently checks closure; `review_service` owns versioned transactions, invalidations and immutable records; `review_api` enforces current roles and safe denial audit. Additive 0011 adds seven scoped tables. No mail transport, new worker, AI tool or financial service is added. See [REVIEW_RECOVERY.md](REVIEW_RECOVERY.md).

`review_access` supplies an opt-in whole-application admission boundary, activated
also by demo mode. Existing DB/company dependencies recheck grants under their locks;
legacy case/document/evidence access accepts only this server-created identity context.
No credential headers are synthesized. Finance keeps its independent M08 authority
port. Default legacy compatibility is local-only and does not resolve G1 deployment.
