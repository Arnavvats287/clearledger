# Matching contract — exact-v1 (milestone 02)

This is a local, deterministic **proposal** engine. It never changes receipt/customer/invoice/bank balances, status or versions, creates allocations or journals, or accepts a proposal for execution. Existing CSV contract 1.0 is unchanged; Argon owns all demonstration/evaluation data. Only isolated code fixtures are used in tests.

## Identity, intent and abstention

Customer identity comes from an exact normalized payer/verified-alias mapping, an explicit CUSTOMER_MAPPING attestation, or ownership of an explicitly verified INVOICE_REFERENCE. The alias's source bytes/hash/typed row, customer association and supplied verification metadata are checked; future verification timestamps abstain. Normalization reuses the existing split/space/casefold rule. Matching names, unverified memo text and equal amounts alone are never sufficient.

EXACT_MATCH requires one supported customer and one verified invoice reference, correct ownership, an open INR invoice issued on/before the receipt's India-local date, and **current invoice open paise = current receipt unapplied paise > 0**. A verified reference can disambiguate other same-amount invoices. Without that intent, even a unique same-amount invoice with a known payer abstains. Multiple equal candidates without intent or conflicting customer/reference evidence return AMBIGUOUS. Unknown customer is UNRESOLVED within NO_SUPPORTED_MATCH. Closed/zero/future/unequal invoices, exhausted cash, stale/invalid evidence and unsupported references abstain with explicit reasons.

Limits: inspect at most 100 evidence records and 1000 customer invoice records (fetch one extra to detect incompleteness). Explicit references narrow invoice lookup. Exceeded budgets return AMBIGUOUS / AMBIGUOUS_OR_BUDGET_EXCEEDED. Existing partial balances may be compared exactly; no partial/subset search or application is implemented.

`X-Actor-ID` is still **locally asserted, unauthenticated** operator provenance. Alias verification fields are local supplied records, not proof of the external verifier's real-world identity. Source validation checks consistency/provenance; the operator attests the customer/intent association. These APIs are local development tools, not production identity verification or accounting approval. An exact proposal always requires an explicit source-backed reference attestation; bank text cannot approve itself or call a tool.

## Verification API

POST `/receipts/{id}/matching-evidence`: JSON plus `X-Actor-ID` and UUID `Idempotency-Key`. Required fields unless marked optional:

| Field | Type and constraint |
|---|---|
| kind | CUSTOMER_MAPPING or INVOICE_REFERENCE |
| customer_id | Existing company customer UUID |
| invoice_id | Company invoice UUID required for INVOICE_REFERENCE; otherwise null/omitted |
| expected_receipt_version, expected_customer_version | Strict INTEGER 1–2147483647 |
| expected_invoice_version | Strict positive INTEGER for INVOICE_REFERENCE; otherwise null/omitted |
| source_import_id, source_row | Receipt bank transaction's accepted source UUID and original CSV record number (2–10001) |
| source_field | payer_name or memo; invoice references require memo |
| start_offset, end_offset | Zero-based Unicode character span, inclusive/exclusive; strict integers, 0 ≤ start < end ≤ source length ≤2000 |
| exact_quote | Exact nonblank source substring, max 2000 characters |

No unknown fields, float/bool versions or tenant selectors. The source must belong to **this receipt**, row and company. Bytes are rehashed; the typed CSV row, semantic payload and source/UTC timestamps are checked against the bank original. The operator's reference must equal the entire invoice_number and be delimited: surrounding alphanumerics or `-_./` indicate another identifier, so INV-1 inside INV-10 is rejected. The invoice must belong to the supplied customer. An exact span alone does not establish authorization; it is combined with this explicit local attestation.

Stale versions → 409; unknown/cross-company IDs → 404; wrong source/owner/span/reference → 422. Same key/body returns the original evidence without writes; same evidence with a fresh key reuses it. Reverification of an identical source locator and customer/invoice target at newer aggregate versions appends evidence and supersedes that locator's older version during evaluation. Different targets remain conflicts. No evidence/history is deleted or rewritten; general revocation/corrections are deferred.

## Trigger and read APIs

GET `/receipts/{id}/matching-context` returns the current bounded snapshot and snapshot_sha256, without persistence. POST `/receipts/{id}/match` requires JSON plus the same actor/key headers:

```json
{
  "expected_receipt_version": 1,
  "expected_invoice_versions": {"<selected-invoice-uuid>": 1},
  "expected_snapshot_sha256": "<optional-current-lowercase-sha256>"
}
```

Omit expected_snapshot_sha256 if no prior context is available. The invoice-version map can be empty for unresolved/ambiguous attempts, but EXACT_MATCH requires the selected invoice's expected version. Maximum 100 map entries. All supplied invoice IDs are scoped. Missing selected-invoice preconditions, stale versions/snapshot or stale same-key proposal retries return 409 and commit no proposal. Changed operation/body/receipt under an existing key returns 409 IDEMPOTENCY_CONFLICT. A new key may evaluate the new state, preserving history.

Response includes proposal UUID/company/version/created_at, receipt/source/customer/invoice IDs, amount_paise (zero for abstention), outcome, immutable result/snapshot and snapshot_sha256, plus computed is_stale/current_snapshot_sha256. Result includes identity (RESOLVED/AMBIGUOUS/UNRESOLVED), customer candidates, exact-amount candidate invoice IDs, reason, selected invoice/version if eligible, and integer proposed amount. Snapshot basis points to verified alias/evidence records and source provenance/hashes.

Read evidence history with GET `/receipts/{id}/matching-evidence`, proposal history with GET `/receipts/{id}/matches`, and a proposal with GET `/matching-proposals/{proposal_id}`. Histories accept limit 1–100 and offset ≥0, ordered by created_at/id. Every query is company-scoped; foreign IDs return 404. GETs never append audit events or mutate stored/financial records. Staleness is a point-in-time observation, not permission to apply a proposal.

## Persistence and concurrency

All new tables share generated UUID id, company FK, version INTEGER >0, UTC created_at, unique(company,id) and company index. Fields below are NOT NULL unless nullable is stated; UUIDs are internal IDs, not new CSV inputs.

| Table | Additional fields | Constraints |
|---|---|---|
| matching_evidence | receipt_id/customer_id UUID; invoice_id UUID nullable; receipt_version/customer_version INTEGER; invoice_version INTEGER nullable; kind VARCHAR(32); source_import_id UUID; source_row INTEGER; source_field VARCHAR(20); start_offset/end_offset INTEGER; exact_quote VARCHAR(2000); verified_by VARCHAR(100); payload_sha256 VARCHAR(64) | Scoped receipt/customer/source FKs; composite invoice FK includes owner; unique(company,receipt,payload hash); kind/span/version checks; references require nonnull positive invoice version |
| matching_proposals | receipt_id/source_import_id UUID; customer_id/invoice_id UUID nullable; amount_paise BIGINT; outcome VARCHAR(32); snapshot_sha256 VARCHAR(64); snapshot/result JSONB | Scoped receipt/customer/source/owned-invoice FKs; unique(company,receipt,snapshot hash); exact requires positive amount/customer/invoice; abstention requires zero amount and null invoice |
| matching_requests | receipt_id UUID; idempotency_key UUID; request_sha256 VARCHAR(64); evidence_id/proposal_id UUID nullable | Scoped FKs, exactly one target, unique(company,key) across evidence and match operations |

`invoices` gains unique(company,id,customer_id) for ownership FKs. UPDATE/DELETE/TRUNCATE on all matching tables is blocked by DB triggers. Metadata creation appends audit events linked to the receipt's original source and operator; there is no financial posting.

Writes use the same company advisory-lock key as imports, shared row locks stabilize existing inputs, and expected versions enforce optimistic preconditions. Database uniqueness independently prevents duplicates. Identical key/body/current inputs reuse the proposal without another request/audit row; different keys against identical inputs also reuse the proposal while retaining key mappings. Snapshots cover algorithm version, receipt original/unapplied paise/status/currency/version, bank source validity/hash, customer versions/keys, invoice versions/actual balances/dates/currency/source identity and evidence validity/basis. Balance changes without version bumps and newly added evidence therefore stale old proposals without changing them. Future application/posting must independently revalidate state and authorization.

## Verification

`uv run --frozen python scripts/verify.py` runs offline lock consistency, dependency compatibility, Ruff lint/format, strict mypy for money and the pure matcher, and all PostgreSQL tests including migration up/down/up/drift/integrity checks. TEST_DATABASE_URL comes from the environment or ignored .env and requires CREATEDB. Only unique disposable databases are downgraded/dropped; development data is retained. Redacted detailed logs stay in ignored `local-data/verification/`.

GitHub Actions runs that same command with ephemeral PostgreSQL 16.15 and locked Python 3.12 dependencies and uploads logs. Workflow configuration does not imply remote execution. Strict typing is deliberately focused on pure financial functions; existing ORM/API checks are not weakened. No datasets, agents, workers, journal posting or later milestones are introduced.
