# CODEX TASK 01 — Financial data engine and contract-based imports

Read `AGENTS.md`, `PROJECT_SPEC.md`, `PLANS.md`, `docs/DOMAIN_AND_ACCOUNTING.md`, `docs/API_AND_STATES.md`, `STATUS.md`. Require task 00 completed and observed tests passing.

## Goal
Implement a tenant-scoped financial data engine and a versioned data contract that Argon can target without schema changes. No matching yet. Argon exclusively researches and constructs demonstration/evaluation data. Codex must NOT generate, download, research, curate or seed datasets, or modify Argon's dataset or the existing demo fixture. Only minimal isolated code-test fixtures are permitted.

## Implement
1. Models/migrations: customers, verified payer aliases, invoices, bank_transactions, receipts, source imports, audit events. Amounts integer paise, currency INR, tenant/company scope, unique source identity. All mutable records versioned.
2. Typed CSV import with row-level validation, error reporting, and a clear atomic/quarantine policy. Store file digest and ingestion run metadata.
3. Idempotent receipt creation from bank import: same bank transaction from identical or renamed statement file must not generate duplicate receipt or duplicate bank recognition.
4. Define `docs/DATA_CONTRACT.md`: exact required tables/fields/types/keys, CSV headers, relationships, dates/timezones, integer paise, import order, validation, duplicate/conflict/rejection policy and versioning. Implement imports compatible with that contract; do not create or seed demonstration/evaluation data.
5. Validated CSV import endpoints and read-only APIs for customers, aliases, invoices, bank transactions, receipts/payments and import results. No financial mutation beyond initial receipt registration.
6. Audit source creation and duplicate detection, including who/when and source digest.

## Tests
- Valid import; strict currency/date/money rejection; cross-company references blocked; duplicate, renamed, conflicting and concurrent bank imports; exact opening balances; immutable sources/audit; scoped reads; reversible migrations and restart persistence. Use only minimal isolated test fixtures.

## Non-goals
No deduction acceptance, invoice matching, tax calculations, journals/posted bank GL, LLM, frontend, arbitrary file execution. Leave bank recognition journal for task 08 after the ledger core exists.

## Exit
Run migrations, complete Docker PostgreSQL pytest, lint/format/dependency checks and ingestion smoke. Report the contract/import commands/results in `STATUS.md`. Follow verified Git checkpoint rules. STOP before milestone 02.
