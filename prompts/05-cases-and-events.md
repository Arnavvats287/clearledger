# CODEX TASK 05 — Persistent claims/cases and late evidence lifecycle

Read specs/state; implement task 05 only.

## Goal
Turn one-time matching/extraction into a durable long-running business process.

## Implement
1. Models for cases, receipt/invoice links, claims, claim states, hypotheses placeholder, domain events, outbox events and case versions.
2. Deterministic creation or update of cases from unresolved receipts and parsed remittance claims. Each deduction claim is separately tracked. Sum of customer-claimed deductions may differ from verified settled amounts.
3. Typed legal transitions and clear error on invalid state transition. Append-only event history.
4. New evidence/doc event increments version, marks affected hypotheses stale, invalidates unposted proposals, and schedules precise re-evaluation rather than duplicating case or cash application.
5. Implement background outbox delivery if asynchronous processing is now needed; safe retry and event ID dedupe.

## Tests
Document before receipt/after receipt; duplicate event replay; two claims one receipt; reopening from evidence pending; malformed transition; missing source; versions prevent stale updates; immutable event history.

## Exit
Run actual migrations and tests, update status, STOP.
