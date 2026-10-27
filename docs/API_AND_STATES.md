# API contracts and state machines (target, evolve via migrations)

Optional AR AI planning/synthesis uses the existing investigation start/findings/trace
APIs, not a new agent endpoint. Typed review recommendations and validated numeric
comparisons are stored in trace metadata; legacy financial finding/state enums remain
unchanged. Live acceptance is still open. See [AI_INVESTIGATOR.md](AI_INVESTIGATOR.md).

Post-M09 correlation review adds immutable pending/source-snapshot tasks and terminal
CONFIRM/REJECT decisions through existing review roles. No financial state transition
is inferred. Task/API/currentness and frontend integration: [CORRELATION_REVIEW.md](CORRELATION_REVIEW.md).

Milestone 04's separate authenticated `/documents` ingestion/read/extract/span/correlation APIs and strict versioned schema are defined in [DOCUMENTS.md](DOCUMENTS.md). Document parse states are READY/NEEDS_OCR/PARSE_FAILED; immutable extraction runs are SUCCEEDED/NEEDS_REVIEW/FAILED/BLOCKED; immutable associations are LINKED/CANDIDATES/UNRESOLVED/SEARCH_INCOMPLETE with computed staleness. These extraction/association metadata operations never mutate financial balances, approvals or posting. Milestone 05 consumes their committed events separately into versioned case/claim review metadata. "Linked" confirms only the locally attested reference association; schema success never grants authenticity or financial authority. Existing financial CSV and matching APIs are unchanged.

Milestone 02's implemented verification, matching and stale-snapshot endpoints are specified in [MATCHING.md](MATCHING.md). They create proposals only; exact matching does not enable the later allocation/posting transitions below.

Milestone 03 adds GET `/receipts/{id}/advanced-matching-context` and POST `/receipts/{id}/match-advanced` using the same evidence, actor/idempotency and proposal-history conventions. Advanced outcomes are UNIQUE/AMBIGUOUS/UNRESOLVED/SEARCH_INCOMPLETE with explicit search completeness, intent and candidate allocations; details/bounds/partial evidence are in MATCHING. These are immutable analysis outcomes, not receipt/case/posting state transitions. Exact-v1 remains unchanged and no financial application endpoint is enabled.

## Stable identifiers and fields
Internal IDs are UUIDs (or consistent server-generated IDs); external references (UTR, invoice number, BOL reference) are scoped to the organization and source system. Amounts: `amount_paise: int`, currency fixed to `INR`. Created/occurred times are stored as UTC timestamps with the original timezone/source text kept as provenance; financial dates use the relevant India local calendar. Every mutable aggregate has `version: int`.

## Domain states
- Receipt: `NEW` -> `UNAPPLIED` -> `PARTIALLY_APPLIED` -> `FULLY_APPLIED`; `QUARANTINED` for invalid or suspect intake; undo through compensating events, not destructive deletion.
- Claim: `EXTRACTED` -> `INVESTIGATING` -> (`SUPPORTED` | `CONTRADICTED` | `INSUFFICIENT_EVIDENCE` | `NEEDS_TAX_REVIEW`) -> (`ACCEPTED` | `DISPUTED` | `AWAITING_CUSTOMER_EVIDENCE`) -> `RESOLVED`. Analyst decision and rule evidence are separate fields.
- Case: `NEW` -> `MATCHING` -> `INVESTIGATING` -> (`AWAITING_EVIDENCE` | `AWAITING_REVIEW` | `READY_TO_APPLY`) -> (`PARTIALLY_SETTLED` | `CLOSED`); may return from evidence waiting to investigation; closed cases can reopen with versioned events subject to policy.
- Journal proposal: `DRAFT` -> `VALIDATED` -> `PENDING_APPROVAL` -> (`APPROVED` | `REJECTED`) -> `SIMULATED_POSTED`; stale proposals -> `INVALIDATED` and require regeneration. Posting is not a LangGraph LLM node.

## Suggested API surface
- `GET /health`, `GET /ready`
- `POST /imports/customers`, `/imports/invoices`, `/imports/bank-transactions`, `/imports/documents`
- `GET /receipts`, `GET /receipts/{id}`, `POST /receipts/{id}/match`
- `GET /cases`, `GET /cases/{id}`, `GET /cases/{id}/events`, `POST /cases/{id}/investigate`
- `GET /claims/{id}/evidence`, `POST /cases/{id}/attach-evidence`
- `POST /cases/{id}/proposals`, `GET /proposals/{id}`
- `POST /proposals/{id}/request-approval`, `POST /proposals/{id}/approve`, `POST /proposals/{id}/reject`
- `POST /proposals/{id}/simulate-post`, `GET /audit/events`, `GET /analytics/summary`
- `POST /cases/{id}/draft-evidence-request`, `POST /cases/{id}/record-response`

Exact endpoint shape may be adjusted in early implementation, but maintain these semantic boundaries and typed payloads. Mutation endpoints must accept idempotency keys or expected aggregate versions; return conflicts instead of silently double applying.

## Safety of GET vs mutation
GET endpoints never mutate. `investigate` can enqueue jobs but must not post journals. Only `simulate-post` can create accounting journal entries, and only after backend transactional guards.

## Persistence model highlights
Tables: organizations, users, user_roles, customers, payer_aliases, invoices, invoice_lines, bank_transactions, receipts, receipt_allocations, documents, document_spans, contracts, promotions, delivery_records, tax_rule_versions, tax_evidence, cases, claims, hypotheses, investigations, evidence_links, journal_proposals, journal_lines, approvals, posted_journals, dispute_actions, domain_events, outbox_events.

Bank transactions: unique `(organization_id, source_system, account_ref, external_transaction_id_or_fingerprint)`; receipts: unique source bank transaction; posted journals: unique proposal/version; allocations: unique immutable application key. Enforce FKs, status constraints, `CHECK (amount_paise > 0)` where appropriate and DB transaction protection with row locking on receipt/invoice balances.

## Correlation for late documents
Remittance may arrive before/after receipt. Extract invoice references / UTR / payer hints and create case-document candidate links. Auto-bind only when deterministic strong identifiers uniquely agree. Otherwise create candidate associations for analyst confirmation. New evidence increments case version and invalidates stale unposted proposals.

## Milestone 05 implemented contract

[CASES.md](CASES.md) defines persistent cases/claims, typed transitions, source-backed merges, exact evidence relationships, local read/write authentication, expected versions/idempotency, immutable histories and leased transactional outbox delivery. Settlement/adjudication states retain the normative vocabulary above but require later validated capabilities; current APIs reject attempts to assert them. The placeholder hypothesis is UNASSESSED with no financial authority.

## Milestone 06 implemented contract

[EVIDENCE.md](EVIDENCE.md) defines separate immutable evidence-1.0 manifests, authenticated
registration, database-read-only case search/verification and stable reviewer pointers.
Verifier outcomes SUPPORTED/CONTRADICTED/INSUFFICIENT/NOT_APPLICABLE describe source facts
only and carry no financial authority; they do not perform claim state transitions.
All previous claim/settlement capability gates remain. Case/customer/invoice/version
scope and exact citations are required. Both existing financial CSV and matching APIs
remain compatible. No arbitrary SQL, model invocation, approvals or posting is exposed.

## Milestone 07 investigation contract

[INVESTIGATIONS.md](INVESTIGATIONS.md) defines authenticated, tenant-scoped start/resume
commands and run/findings/trace read APIs. States are QUEUED, RUNNING, COMPLETED,
AWAITING_REVIEW and STALE; terminal histories cannot be rewritten. Typed hypothesis
states are SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE and NEEDS_TAX_REVIEW, always
requiring human review and carrying no financial authority. The Investigator has seven
read-only capabilities through a trusted scoped broker. Optional external extraction
is disabled; it does not expose a general model/tool invocation endpoint. Existing
claim transitions, financial CSV/matching contracts and approval/posting gates remain.

## Milestone 08 implemented contract

[ACCOUNTING_SIMULATOR.md](ACCOUNTING_SIMULATOR.md) specifies verified-source/policy APIs,
`/cases/{id}/journal-proposals`, version/hash-bound submission/review/simulate-post, and
ledger/balance/audit reads. Existing matching proposal bindings remain separate. Financial
identity defaults unavailable; local tokens/actor labels cannot grant permission.
Normative journal states, maker-checker, fresh evidence/policy/approval and DB conservation
are enforced. Proven posting can advance settlement metadata to PARTIALLY_SETTLED;
closure/recovery and broader reviewer workflow remain M09. Unknown claims remain review.

## Milestone 09 implemented contract

[REVIEW_RECOVERY.md](REVIEW_RECOVERY.md) defines demo login/logout and safe role-based reads, reviewer comments, draft-evidence-request/request-evidence/record-response and explicit close/reopen commands. Financial submission and approve/reject reuse M08 version/hash-bound endpoints with no authorization relaxation. Late responses invalidate unposted work and reopen affected claims/cases without reversing settled money. CLOSED requires verified current controller authority, zero financial outstanding, resolved current claims and completed mandatory actions/work. Local tokens/actor labels cannot close or grant financial permission.


## Frontend consumption
The local React workstation consumes existing case/document/investigation/review
contracts without changing state machines. New read-only task proof inspection:
GET `/review/correlation-tasks/{task_id}/proof` with required `expected_task_sha256`;
response `RecordView[]`, READ role, tenant/snapshot/document scoped, stale409.
Financial CSV1.0 and source evidence semantics are unchanged. FRONTEND.md documents
all operational routes, error handling, local identity limitations and test commands.
