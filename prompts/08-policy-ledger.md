# CODEX TASK 08 — Configured policies, tax abstention, accounting simulator

Read domain/accounting, tax-scope and security docs. This phase is correctness-critical; do NOT broaden legal coverage.

## Goal
Convert verified claim treatment + valid receipt applications into balanced journal proposals, gated approval, and atomic idempotent **simulated** posting.

## Implement
1. Chart-of-accounts config, versioned demo approval policies, tax evaluation interface (`SUPPORTED` based on reviewed/fixture policy, `NEEDS_TAX_REVIEW` otherwise). Do not implement universal TDS assumptions.
2. Compose journal A for receipt bank recognition exactly once: Dr Bank / Cr Unapplied Receipts; journal B for validated application and noncash approved tax receivable/allowance. Keep unsupported commercial deduction as open AR.
3. Generate a proposal with source versions, evidence IDs, rule IDs, exact paise lines. Validator checks balanced debit/credit, open invoice/customer identity, allowed accounts, no over-allocation, available cash, approvals and staleness.
4. Transactional simulated posting service: row locks/unique keys and atomic updates of receipt/invoice/ledger balances. Repeat concurrent calls produce one ledger result or idempotent replay.
5. Use fixture CASE-204: bank receipt INR 116,500, synthetic approved withholding INR 1,000, damage claim INR 2,500 unsupported, invoice INR 120,000 -> remaining AR INR 2,500; two journals as in `fixtures/demo-case.json`.
6. Do not treat journal balance alone as sufficient. Do not allow any auto writeoff or issue GST credit notes.

## Tests
Double entry per journal, fractional paise rejection, bank entry once, duplicate post attempt, concurrent same proposal, stale approvals, changed invoice balance, unsupported tax -> review, wrong customer, missing source, proper open AR after partial settlement, simulated reversal entry under explicitly approved case if implemented.

## Exit
Postgres integration test including concurrency, audit evidence, status update. STOP.
