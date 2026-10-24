# CODEX TASK 03 — Advanced multi-invoice matching (approved extension)

Read AGENTS, STATUS, PLANS, REQUIREMENTS_AUDIT, `03-subset-and-partials.md`, MATCHING, domain/accounting, API and DATA_CONTRACT. The original milestone 03 numbered requirements, tests and exit gate remain mandatory. This file records the user's approved extensions and terminology; no implementation is claimed here. Resolve/report audit blockers before advancing.

## Preserved original checklist plus approved additions

1. Pure integer-paise one-receipt/many-invoice service: bounded DP/meet-in-the-middle, or a justified alternative such as OR-Tools with documented complexity/performance benefit. Avoid unnecessary dependencies. Only the same verified customer, tenant, open eligible invoices and permitted dates may enter search. Respect current outstanding/unapplied balances.
2. Support explicit multi-invoice references and mathematical subset search when references are unavailable. Return all feasible combinations up to configured top-K, deterministic ordering and `search_exhaustive`. Never arbitrarily select one of competing combinations. A mathematically unique subset is not proof of payment intent or authority to apply it.
3. Support explicit remittance-driven partial allocations **separately** from subset-sum. Partial-payment analysis is required, not silently deferred to a later milestone. Missing/ambiguous allocation instructions must remain unresolved/reviewable; never infer discounts, taxes, write-offs or unauthorized settlement from short payment.
4. Configurable candidate-count, combination-size, execution-time and search-work budgets, plus top-K. Exhaustion/incomplete enumeration must never be interpreted as uniqueness. Preserve incomplete-search reporting and the original worst-case-cap benchmark exit requirement.
5. Explainable persistent, immutable, idempotent proposals containing algorithm version, evidence references, input versions, competing candidate allocations and explicit incompleteness. Preserve tenant isolation, optimistic concurrency, stale-balance/evidence detection, financial non-mutation and immutable history. Expose candidates through the API, never post or apply them.

## Approved outcome-name crosswalk

Primary outcomes requested by the user are UNIQUE, AMBIGUOUS, UNRESOLVED and SEARCH_INCOMPLETE. Preserve the original semantics:
- Original UNIQUE_WITH_EVIDENCE: UNIQUE **with independently verified intent evidence**. Mathematical uniqueness without such evidence must be labeled as mathematical candidate analysis requiring review; it must not acquire the evidence-qualified meaning.
- MULTIPLE_CANDIDATES → AMBIGUOUS; retain all bounded competing candidates.
- NO_MATCH → UNRESOLVED, with reason (including missing identity/partial instructions where applicable).
- BUDGET_EXCEEDED → SEARCH_INCOMPLETE; `search_exhaustive=false` forbids a uniqueness claim even when only one candidate was found.

## Required verification and exit

Retain every original test: competing equal-total subsets, no combination, one provably exact subset, equal amounts across customers, oversized pools, integer edge cases, referenced split payments and deterministic ordering. Add explicit multi-reference/partial-receipt/duplicate-amount cases, candidate/size/work/time/performance boundaries, incomplete search after a candidate, concurrent requests, stale balances, tenant isolation, evidence/proposal idempotency and financial non-mutation. Use property-based comparison to a small exhaustive oracle where beneficial, with only minimal isolated code fixtures.

Run focused checks during development, worst-case cap benchmark, and `uv run --frozen python scripts/verify.py` including all regressions/migrations/integrity/static checks. Save detailed logs locally, report unmet criteria, review intended staged changes/secrets, checkpoint only after required checks pass, record hashes/results and leave a clean tree. No datasets, tax/deduction processing, agents/LangGraph, Redis/MCP, posting or frontend. STOP after milestone 03.
