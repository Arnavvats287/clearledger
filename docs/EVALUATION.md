# Evaluation and experiment specification

## Objective
Prove the product improves accurate financial case handling, not merely that an LLM generates plausible deduction labels. Benchmark the SAME hidden-ground-truth synthetic cases across three variants:
- A — deterministic matching, basic static exception routing, no LLM investigator.
- B — deterministic matching + single bounded evidence investigator.
- C — deterministic matching + rule-based Director coordinating bounded Investigator, validators and case re-evaluation.

## Dataset construction
Generate seeded, deterministic INR finance environments with named synthetic companies, 50 customers, ~2000 invoices, ~500 receipts, >=250 evaluation situations (adjust size for developer machine), >=100 realistic text/PDF-like documents, and >=30 attack/abuse scenarios. Keep train/dev/test templates separated; avoid leakage from repeated narrative templates. Hold out combinations of scenario categories and document layouts.

## Scenario classes
Exact single/multi invoice, candidate subset collisions, partial payment, unmatched payer, aliases, late remittance, remittance before receipt, valid and uncorroborated damage, short shipment, expired promotion, wrong early-pay window, duplicate UTR, split receipts across days, withholding reviewed/supported vs unsupported, government deductor conditions, conflicting delivery records, missing document, stale approval, race on posting, prompt injection, cross-company data attempt.

## Metrics
- Incorrect auto-application count and rate (hard blocker on held-out suite)
- Correct abstention rate on ambiguous evidence
- Allocation precision/recall under safe eligibility conditions
- Evidence support accuracy (incl. stale/wrong-customer sources)
- Valid citation pointer rate
- Per-case human actions and review time (measure on pilot; do not fabricate)
- Open AR and unapplied cash balance reconciliation
- Double-posting and over-allocation count
- LLM call count, tool calls, latency, token cost per resolved case
- Recovery-case closure workflow integrity

## Testing discipline
Use pure deterministic fixtures for financial invariants; property-based generators to stress allocations and monetary conversions; integration tests against real PostgreSQL for locking/idempotence; adversarial retrieval tests; full UI smoke flow via Playwright. Keep golden test labels hidden from runtime prompts. Tests should examine actual persisted journals and audit events, not only model text.

## Early stop / honesty
Do not claim production-level reliability from a few hundred synthetic cases. If an evaluation fails, provide failure examples and root causes. Director–Investigator separation remains optional if C does not outperform B on at least one predeclared outcome without harming correctness or introducing unacceptable cost.
