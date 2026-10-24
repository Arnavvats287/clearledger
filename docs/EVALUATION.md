# Evaluation and experiment specification

## Objective
Prove the product improves accurate financial case handling, not merely that an LLM generates plausible deduction labels. Benchmark the SAME hidden-ground-truth synthetic cases across three variants:
- A — deterministic matching, basic static exception routing, no LLM investigator.
- B — deterministic matching + single bounded evidence investigator.
- C — deterministic matching + rule-based Director coordinating bounded Investigator, validators and case re-evaluation.

## Dataset construction
Argon exclusively researches and constructs demonstration/evaluation data and frozen ground truth. Codex must not generate, download, curate or seed that dataset. Consume versioned Argon artifacts through `docs/DATA_CONTRACT.md`; report unavailable data as unverified rather than fabricate it. Argon controls train/dev/test separation and held-out customer/template/layout patterns. Codex may write only minimal isolated application test fixtures.

The original coverage targets are retained as **Argon-owned deliverables**, not Codex generation tasks: reproducible INR environments with 50 customers, approximately 2000 invoices, approximately 500 receipts, at least 250 evaluation situations (adjust size for the developer machine as originally allowed), at least 100 realistic text/PDF-like documents, and at least 30 attack/abuse scenarios. Keep train/dev/test templates separated, avoid repeated narrative-template leakage, and hold out combinations of scenario categories and document layouts. Dataset ownership changes responsibility, not these coverage or hidden-ground-truth requirements. No target is claimed achieved until Argon's artifacts and executed evaluation demonstrate it.

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
