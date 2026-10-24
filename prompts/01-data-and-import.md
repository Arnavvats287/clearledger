# CODEX TASK 01 — Synthetic dataset + bank/invoice imports

Read `AGENTS.md`, `PROJECT_SPEC.md`, `PLANS.md`, `docs/DOMAIN_AND_ACCOUNTING.md`, `docs/API_AND_STATES.md`, `STATUS.md`. Require task 00 completed and observed tests passing.

## Goal
Make a local financial data substrate that can import deterministic synthetic customer, invoice and bank receipt information. No matching yet.

## Implement
1. Models/migrations: customers, verified payer aliases, invoices, bank_transactions, receipts, source imports, audit events. Amounts integer paise, currency INR, tenant/company scope, unique source identity. All mutable records versioned.
2. Typed CSV import with row-level validation, error reporting, and a clear atomic/quarantine policy. Store file digest and ingestion run metadata.
3. Idempotent receipt creation from bank import: same bank transaction from identical or renamed statement file must not generate duplicate receipt or duplicate bank recognition.
4. Seeded synthetic data generator plus demonstration fixture `fixtures/demo-case.json` to create customers, invoices and one receipt with a realistic, deterministic UTR and timestamps.
5. API endpoints to upload/import datasets and query customers, invoices, receipts. No financial mutation beyond initial receipt registration.
6. Audit source creation and duplicate detection, including who/when and source digest.

## Tests
- Valid import; bad monetary values rejected; cross-company references blocked; exact and renamed duplicate bank records do not duplicate receipt; repeated seed is idempotent; inserted amounts and balances are correct; data survives restart.

## Non-goals
No deduction acceptance, invoice matching, tax calculations, journals/posted bank GL, LLM, frontend, arbitrary file execution. Leave bank recognition journal for task 08 after the ledger core exists.

## Exit
Run migrations, pytest, lint, ingestion smoke and report actual results. Update `STATUS.md`. STOP.
