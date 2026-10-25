# Architecture and runtime boundaries

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

The implementation stays in `src/clearledger`, extending the existing service/SQLAlchemy layout. `document_api` authenticates local document access and derives company scope; `documents` is the transactional metadata orchestrator; `document_runtime.LocalOriginals` stores exclusive content-addressed originals. `document_parse` runs in `document_worker`, with bounded PDF/MIME processing and no network. `document_contract`, `remittance_parser` and `document_privacy` define typed untrusted facts, deterministic-first parsing, independent source/semantic validation and private offset-preserving projection/restoration. No persistent claims/cases or general evidence adjudicator are introduced.

Approved Gemini transport exception: the typed `extraction_provider.Transport` receives only sanitized pages. `gemini_worker` uses the official SDK in a separate minimal-environment process; `worker_security` denies tools, local DB/arbitrary network and application-file reads. Only the configured Google host/public TLS endpoints are allowed. This transport is not an investigator, agent, tool runtime or policy service. The parser retains zero network. Shared Python audit/OS resource guards are defense in depth, not a separate OS-principal/container sandbox against arbitrary dependency RCE; deployment remains local/synthetic-only.

External AI is disabled by default and requires explicit synthetic approval, server/provider/model/key/review configuration and request opt-in. The orchestrator independently validates provider output before appending immutable extraction/audit metadata; no DB/session is passed to the provider. Raw bytes and private mappings never enter model content. Synchronous requests retain the existing company transaction lock through bounded processing, favoring consistent idempotency over throughput; there is no Redis/worker queue. Gateway/worker concurrency and attempt limits are per API process. Milestone 04B adds independently committed, append-only PostgreSQL reservations under a separate company/provider advisory lock for shared daily request/token budgets and rolling-minute RPC admission. This is not an account-global Google quota; see docs/DOCUMENTS.md for conservative charging, cache identity and limits.

Five additive immutable tables record documents, extractions, candidate/reference associations, operation keys and document audit events. Exact UTR correlation is separately attested, bounded, scoped and version checked; conflicting/unknown owners, stale extraction or multiple receipts abstain. It never creates financial allocations, changes receipt/invoice versions/balances or grants authenticity/legitimacy. Milestone 05 will supply case/claim lifecycle and late-evidence event replay; milestone 06 supplies generalized financial evidence validation. Full document/API/privacy/format contracts are in [DOCUMENTS.md](DOCUMENTS.md); CSV DATA_CONTRACT 1.0 is unchanged.
