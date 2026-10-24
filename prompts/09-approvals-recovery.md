# CODEX TASK 09 — Role-checked review, dispute and recovery operations

Read security, API/state and domain docs. Implement task 09 only.

## Goal
Make exception resolution a controlled workflow between analysts, controllers and customers (through draft correspondence only).

## Implement
1. Single-organization local user/role support suitable for demo. Backend authorization: AR_ANALYST, CONTROLLER, AUDITOR. Do not represent demo login as production SSO.
2. Proposals with expected versions, approve/reject/request-evidence endpoints and maker-checker enforcement. Audit every reviewer action and decision reason.
3. Create evidence-request/customer-follow-up **drafts** from verified invoice, delivery and case facts; no automatic transmission. Show source references.
4. Record a customer response, attach newly provided evidence, reopen/re-evaluate affected claim, invalidate stale unposted proposal, preserve prior review history.
5. Case closure only when financial outstanding balance and operational claim status permit it; enable partially settled state.

## Tests
Self approval denied for restricted action, read-only cannot mutate, late response reopens case, old proposal cannot be posted, drafted email does not send, audit history preserved, closure rejects unresolved mandatory actions.

## Exit
Run authenticated API tests, report commands, status update, STOP.
