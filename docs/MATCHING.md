# Matching contract — exact-v1 (milestone 02)

The exact-v1 contract below remains supported unchanged. Milestone 03 adds the explicitly opted-in advanced contract at the end of this document; it does not reinterpret existing exact proposals.

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

## Advanced matching — milestone 03 / advanced-mitm-v1

`GET /receipts/{id}/advanced-matching-context` returns a stable input snapshot/hash, without searching or writing. `POST /receipts/{id}/match-advanced` accepts the existing MatchInput fields plus optional **strict boolean** `use_structured_allocations` (default false). Use the same actor/idempotency headers. This additive endpoint deliberately preserves exact-v1 abstention, body fingerprints and stored history. Existing proposal/history GETs serve both algorithms and compute staleness using the corresponding algorithm, source mode and current server limits.

```json
{
  "expected_receipt_version": 1,
  "expected_invoice_versions": {"<invoice-A-uuid>": 1, "<invoice-B-uuid>": 1},
  "expected_snapshot_sha256": "<optional-advanced-context-hash>",
  "use_structured_allocations": false
}
```

All supplied invoice IDs/versions are scoped/checked; expected versions are required for every invoice in returned candidate combinations. Errors preserve existing 404/409/422 semantics. Context accepts `?use_structured_allocations=true` for that source mode. Body changes across operations conflict under an existing key. No new tenant selector exists.

### Evidence, eligible search space and partials

Reuses exact-v1 source rehashing, alias/customer/reference verification, evidence supersession, company advisory lock, shared row locks, optimistic versions and current balances. Exactly one verified customer is required. Conflicting customers abstain as AMBIGUOUS; stale/invalid provenance abstains as UNRESOLVED. Eligible invoices must belong to that customer/company, be OPEN, INR, positive current outstanding, and issued on/before the receipt's India-local date. Receipt must have positive available cash and UNAPPLIED/PARTIALLY_APPLIED status. Due date is not a payment restriction. No financial field is mutated.

Verified invoice references constrain intent to **all referenced invoices**. Multiple references in this mode are a group, whereas exact-v1 intentionally still treats them as conflicting single-invoice intent. An ineligible/stale reference invalidates the group; it is never silently removed to manufacture a unique match. Exact full-balance totals produce one group candidate. One verified reference can support allocating available cash partially to that invoice, retaining unpaid AR. A multi-invoice short payment without amounts remains `EXPLICIT_ALLOCATION_INSTRUCTIONS_REQUIRED`; no proportional/order-based split is invented. A larger receipt without explicit allocation instructions remains unresolved rather than guessing how to use the remainder.

For explicitly supplied per-invoice partials, the **original bank memo** must be a JSON object containing exactly:

```json
{"allocations_paise":{"<exact-invoice-number-A>":40,"<exact-invoice-number-B>":60}}
```

Opt in with `use_structured_allocations=true`. Each key must correspond to a separately registered, valid INVOICE_REFERENCE attestation on this receipt; invoice-number keys must exactly equal the complete verified reference set. The operator attests those associations; JSON text alone never supplies identity/intent. Amounts are strict positive integer paise ≤ BIGINT maximum, never floats/bools/strings. Duplicate JSON keys, extra properties, missing/extra targets and malformed/nested unsupported structures abstain. Each amount must be ≤ current invoice open paise and aggregate ≤ receipt unapplied paise. Explicit smaller totals retain residual unapplied cash. Each allocation reports remaining AR; nothing becomes an authorized discount, deduction, write-off, posting or settlement. This is a narrow structured-record extension, not milestone 04 document ingestion/extraction.

Referenced JSON-looking memos in non-structured mode abstain with `STRUCTURED_ALLOCATION_MODE_REQUIRED`; the engine cannot ignore supplied amounts and label a different full-balance allocation as verified intent. Structured allocation candidates retain source import/row/field/hash and an escaped JSON Pointer for each amount. Advanced snapshot basis additionally embeds immutable reference spans/quotes/input versions, and candidate allocations list supporting reference-evidence IDs.

Without references, exact subset search considers full current balances only. When no exact subset exists, larger individual invoices can appear in `partial_analysis` as review possibilities (at most top-K, with `partial_analysis_truncated`), never in selected candidates or as evidence-qualified matches. Arbitrary partial splits without instructions are not enumerated. A mathematical UNIQUE always has `intent_verified=false`, `requires_review=true`, reason `MATHEMATICAL_UNIQUENESS_ONLY`. Every advanced result requires review, including locally attested intent. G1 authentication remains deferred: asserted operator labels are not authenticated authority.

### Completeness, determinism and bounds

The pure, strictly typed `advanced_domain.subsets` uses bounded **meet-in-the-middle** enumeration and a complementary-sum index. Python integer sums are exact (including BIGINT boundary combinations), with strict rejection of bool/float money. Distinct invoice IDs distinguish combinations, even with duplicate amounts. UUID sorting determines traversal and returned ordering; there is no arbitrary selection. Complexity before bounds is O(2^(n/2) + complementary joins), space O(2^(n/2)); positive amounts permit safe sum pruning. This avoids a target-paise-sized DP table and adds no dependency.

Configure server `MATCHING_LIMITS` as JSON, shown in `.env.example`:

| Limit | Default | Hard ceiling |
|---|---:|---:|
| max_candidates | 32 | 40 |
| max_combination_size | 8 | 40 |
| max_work | 100000 | 1000000 |
| max_time_ms | 100 | 2000 |
| top_k | 20 | 100 |

All limits must be positive integers. Candidate fetch uses limit+1; eligibility filtering precedes this cap when references are absent. Evidence retains the existing 100-record cap. Work counts half-state extensions, index insertions, complement lookups and joining pairs. A monotonic nanosecond clock checks every such operation. The time budget bounds combinatorial search, not database/provenance validation or whole HTTP latency; scheduling/cleanup may add overhead. Candidate count and hard ceilings also bound non-search preparation. No per-request budget escalation exists.

Combination-size pruning is intentionally conservative: any omitted positive prefix that could still fit cash marks the search incomplete, even if it might not ultimately complete. An exact complement exceeding the size limit also marks incompleteness. Thus reducing the limit never manufactures uniqueness. Raising it within hard ceilings may allow proof, subject to work/time limits.

| Outcome | Meaning |
|---|---|
| UNIQUE | Exactly one feasible combination after complete relevant search, or one fully specified verified reference group/instruction. Mathematical uniqueness is not evidence of intent. |
| AMBIGUOUS | Multiple combinations after completed enumeration; or conflicting customer evidence, explicitly reasoned. No selected invoice. |
| UNRESOLVED | Completed search has no exact subset, or invalid/missing identity, availability, eligibility or allocation evidence prevents a supported proposal. |
| SEARCH_INCOMPLETE | Candidate/evidence, size, work, time or result cap prevents complete proof/enumeration; always `search_exhaustive=false`, even if a candidate exists. |

All combinations are retained up to top-K. Discovery of a (K+1)th stops enumeration, rather than materializing all collisions. `ambiguity_proven` separately records proof of ≥2 subsets (including when top-K=1), while the primary outcome remains SEARCH_INCOMPLETE for truncated enumeration. The original UNIQUE_WITH_EVIDENCE maps only to UNIQUE with verified intent; MULTIPLE_CANDIDATES→AMBIGUOUS, NO_MATCH→UNRESOLVED, BUDGET_EXCEEDED→SEARCH_INCOMPLETE. An incomplete result is never accepted as uniqueness.

### Persistence, staleness and financial non-mutation

Migration `0004_advanced_matching` extends only the proposal outcome constraint; no import schema changes. Advanced proposals retain `amount_paise=0` and `invoice_id=null`: allocations in immutable `result.candidates[].allocations` are analysis records, never cash applications. Each includes invoice ID/version, outstanding paise, proposed cash paise and remaining AR; each candidate includes aggregate and remaining cash. Snapshot contains algorithm, effective limits, source mode, receipt/bank provenance, customer/invoice versions and actual balances, eligibility dates and evidence IDs/digests/validity. Original evidence endpoints resolve source spans. Runtime elapsed/work measurements live in result, **outside the input fingerprint**, avoiding nondeterministic idempotency/stale hashes.

One immutable proposal per `(company,receipt,snapshot_hash)` and one request mapping per company/key remain DB-enforced. Different concurrent keys serialize through the existing company lock and reuse the same stored result/audit event. Even an incomplete/time-limited result is immutable and reused under fresh keys for identical inputs; an intentional server-limit change creates a new snapshot and permits another analysis. Algorithm/source modes are part of snapshot identity; old exact-v1 and advanced analyses can coexist as immutable history, never conflicting executable allocations. No proposal is executed/accepted by these APIs.

GET staleness recomputes input identity without rerunning the search; changes to current observed balances (even without version bump), versions, candidate pool, evidence, source validity or limits stale old results. Bounded input overflow is always incomplete and cannot establish the state/uniqueness of unobserved rows. Future application must revalidate the full financial state and authenticated authority transactionally; there is no application endpoint here. UPDATE/DELETE/TRUNCATE triggers, original history and financial balances remain intact. Downgrading to 0003 with newer outcomes fails atomically instead of deleting/rewriting history; up/down/up verification uses only disposable DBs.

Verification adds an independent exhaustive-combinations Hypothesis oracle, deterministic boundary/clock tests, real PostgreSQL proposal/import/isolation/integrity/history/non-mutation tests and observed overlapping different-key sessions. `scripts/benchmark_matching.py` measures only small numeric algorithm vectors, writes local JSON timing logs and never creates an evaluation dataset. Argon's accuracy/realistic-data benchmarks and remote Actions remain unverified. See STATUS for actual commands/counts/measurements.

The complete `scripts/verify.py` gate now also invokes that bounded numeric benchmark. Each PostgreSQL test owns a fresh disposable database: migration roundtrips cannot accidentally downgrade another test's immutable advanced history. A dedicated upgrade/0003-downgrade/upgrade test proves existing exact-v1 financial/evidence/request/proposal/audit records survive and both algorithms remain readable; the separate newer-outcome downgrade test verifies safe refusal without history loss. No existing test assertions were relaxed.
