# CODEX TASK 03 — Bounded multi-invoice candidate search

Read the specs and state; task 02 must be verified.

## Goal
Evaluate plausible multi-invoice and partial allocations with strict candidate-collision detection and bounded execution.

## Implement
1. Pure integer-paise subset-search service (bounded DP/meet-in-the-middle or OR-Tools with documented choice). Candidate filtering only on same verified customer, open invoices and permitted dates.
2. Return **all** candidates up to top-K plus `search_exhaustive` flag; unique only when full relevant search proves uniqueness. If budget exceeded, never auto-apply.
3. Support explicit remittance-driven partial invoice allocation separately from subset-sum. Never infer discounts/taxes as a generic tolerance.
4. Define `UNIQUE_WITH_EVIDENCE`, `MULTIPLE_CANDIDATES`, `NO_MATCH`, `BUDGET_EXCEEDED` and enforce upper bounds on invoice count/search time.
5. Show competing candidates via API; don't post them.

## Tests
Two combinations same total; no combination; one provable exact subset; same amount across customers; very large invoice pool exceeds budget safely; integer paise edge cases; split payment with supplied invoice reference; deterministic ordering.

## Exit
Test, lint, benchmark worst-case cap, update status, STOP.
