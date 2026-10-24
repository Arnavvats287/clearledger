# CODEX TASK 06 — Evidence retrieval and verification

Read `docs/SECURITY.md`, `docs/DOMAIN_AND_ACCOUNTING.md`, `docs/TAX_SCOPE.md`, status. Task 06 ONLY.

## Goal
Build reliable read-only evidence search and checks BEFORE giving an LLM access to retrieved materials.

## Implement
1. Support contract clauses, promotions, WMS deliveries, proof of delivery and tagged tax evidence supplied by Argon; do not construct a dataset. Use only minimal isolated fixtures for application tests.
2. Typed read-only allowlisted functions with case/customer/organization scope; no general SQL tool exposed to AI.
3. PostgreSQL structured filtering and FTS as appropriate; return stable document/record IDs, document version, offsets and excerpts.
4. Evidence verifier: source ID/version/hash/span text, customer ownership, date validity, signed/approved status and numeric relevance; return `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT`, `NOT_APPLICABLE` plus reasons. Do not promote excerpt-matching alone to financial authority.
5. Provide immutable pointer retrieval API for reviewer UI; avoid generic upload searching by model supplied raw SQL.

## Tests
Correct clause, expired clause, wrong company/customer, changed hash, forged span, missing signed POD, contradictory WMS evidence, external record asking model to change system instructions.

## Exit
Tests, lint, evidence demo, status update, STOP.
