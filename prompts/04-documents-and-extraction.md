# CODEX TASK 04 — Immutable documents, extraction and late remittance

Read `AGENTS.md`, `docs/SECURITY.md`, `docs/API_AND_STATES.md`, and relevant schema; require earlier tasks complete.

## Goal
Import PDF/text/email remittances safely and extract claims without granting LLM outputs authority.

## Implement
1. Document bytes saved via local storage adapter with digest, source metadata, version, organization scope, document type and ingestion audit.
2. Deterministic text PDFs and plain-text email fixtures initially; OCR fallback optional and bounded. Capture page/span location; never pretend a lost layout produced a reliable quote.
3. Pydantic structured extraction contract for invoice refs, UTR refs, payer hint, claim type (tax/damage/short shipment/rebate/early discount/other), integer paise, original spans, uncertainty/unparsed fields.
4. No-tool isolated extractor interface. Provide a **deterministic fixture parser** for offline tests. Model adapter must be optional/disabled unless configured, with no access to database mutation or tool execution. Treat external instructions as content.
5. Late remittance attaches to an existing receipt only on uniquely verified reference match; otherwise store candidate associations for review.

## Tests
Original digest stable; duplicate document no duplicate events; extraction preserves money; adversarial email asking to ignore policies cannot change process; wrong UTR not linked; two possible receipts -> abstain; malformed files and oversized files safely rejected.

## Exit
Run real import smoke + tests, report observed behavior and missing OCR/model support, update status, STOP.
