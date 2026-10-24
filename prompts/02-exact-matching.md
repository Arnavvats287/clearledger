# CODEX TASK 02 — Deterministic customer resolution and exact payment proposals

Canonical milestone 02 prompt (the older `02-entity-and-exact-match.md` remains a reference). Read AGENTS, STATUS, PLANS, architecture/domain/accounting, API and DATA_CONTRACT before modifying code. Build on the verified milestone 01 substrate; do not redesign imports or generate datasets.

## Implement
1. Resolve customers only from verified alias/mapping evidence or source-backed, explicitly verified invoice references. Keep identity and invoice intent separate. Source names/memos/amounts alone are untrusted hints; equal amounts do not prove intent. Return customer candidates and verification basis.
2. Pure deterministic single-invoice matching in integer paise; explicit EXACT_MATCH, AMBIGUOUS and NO_SUPPORTED_MATCH outcomes/reasons. Require verified reference intent and exact current invoice-open/receipt-unapplied equality. Handle conflicting identity/intent, unknown payer, wrong customer, multiple same-amount invoices, closed/zero/future invoices and unsupported amounts. Bounded incomplete search must abstain.
3. Persist immutable, idempotent proposals and source-linked evidence/audit. Repeat identical requests/state reuses a proposal; concurrency cannot duplicate it. No receipt/invoice/customer/bank balance or status mutations, allocations or GL entries.
4. Require optimistic receipt and selected-invoice versions; capture versions and actual balances/evidence in snapshots. Detect stale balances even when a version was not incremented. Reads report staleness without rewriting history; stale retries conflict. New evidence invalidates prior snapshots. Enforce tenant scope in every query/FK/API.
5. Matching trigger/query and explicit verification APIs with strict payloads, source IDs/hashes/row/field/spans. Local asserted operator provenance is not authentication or accounting approval. Preserve old evidence/proposals, including on reverification.
6. Cross-platform complete verification command, GitHub Actions with PostgreSQL disposable integration databases, and strict practical typing for financial domain code. Save detailed logs locally. No automatic push.

## Required tests/exit
Focused checks during development; full existing regression suite plus matching/ambiguity, source validation, cross-tenant, idempotency/concurrency, stale versions/balances, non-mutation and immutable history tests. Run migrations/drift/integrity checks on disposable PostgreSQL databases, lint, format, typecheck and dependency checks. Never skip/weaken failing tests to pass. Record real results/limitations in STATUS, review intended/staged diff and secrets, create verified milestone Git checkpoint, record its hash and leave a clean tree.

No multi-invoice/partial search, deductions, tax, posting, agents, Redis/MCP, frontend or dataset generation. Proposals may compare already partially open balances but cannot apply anything. STOP after milestone 02.
