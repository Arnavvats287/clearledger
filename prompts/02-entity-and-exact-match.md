# CODEX TASK 02 — Verified payer resolution + exact cash allocation

The canonical expanded milestone 02 acceptance criteria are now in `prompts/02-exact-matching.md`. This original prompt remains as context; milestone 02 produces proposals only, never actual allocations.

Read standing instructions and prior implementations. Implement only milestone 02.

## Goal
For a receipt with unambiguous payer identity, propose a safe invoice match. Identity evidence and matching are separate concepts; same amount does not prove intended invoice.

## Implement
1. Deterministic payer identification from verified customer mapping/alias and direct invoice references where provenance supports it. Return candidate list + basis; unsupported payer -> unresolved.
2. Pure matching service returns candidate proposed allocations and explicit reason/status. Support one invoice exact match when uniquely identified by trusted evidence; do not auto-apply just because only one invoice has same value without reliable payer/reference evidence.
3. Preserve unopened/partially open invoice balances and receipt unapplied amounts. For task 02 generate **proposals**, not posted ledger entries; immutable proposals carry invoice versions.
4. Query and trigger match endpoints, with an explicit `AMBIGUOUS` and `NO_SUPPORTED_MATCH` result.

## Tests
Known payer+verified invoice reference; unknown payer; same amount across two invoices; wrong customer; paid/closed invoice; stale invoice balance; cross-company attempt; repeat match returns same deterministic proposal without mutation.

## Non-goals
Subset solver, deductions, tax, AI, posting. Update `STATUS.md` with tests, stop.
