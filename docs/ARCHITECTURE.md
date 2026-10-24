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
fixtures/                    # deterministic synthetic cases
scripts/                     # dev setup, seed, bench
 tests/                      # unit/integration/property/e2e
```

Phase 00 can choose a simpler conventional Python package layout. Avoid creating empty skeletons for every future package.
