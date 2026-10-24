# API contracts and state machines (target, evolve via migrations)

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
