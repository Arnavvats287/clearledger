# Accounting simulator — finance-1.0

Milestone 08 implements `prompts/08-policy-ledger.md`. This is a local INR simulation,
not an ERP integration, legal opinion, tax filing, GST credit note or automatic writeoff.
All persisted amounts and journal lines use integer paise. Financial CSV 1.0 and
both pilot ZIPs are unchanged. Only isolated code fixtures exercise accounting.

## Authority boundary and default denial

Production identity integration is **not configured**. Every new finance endpoint
returns `VERIFIED_FINANCE_IDENTITY_UNAVAILABLE` (503) until a trusted host supplies
`app.state.finance_identity_verifier`, implementing `finance_identity.IdentityVerifier`.
These finance APIs have no environment flag, finance API token, demo-login adapter or
body field that manufactures verified identity. DOCUMENT_API_TOKEN, CASE_READ_TOKEN, X-Actor-ID, source text and
model outputs cannot authorize finance. Existing imports/document/case access remains
unchanged; this does not resolve the application's broader production-authentication G1.

The adapter must authenticate a real, canonical issuer/subject, company, current
authorization version, permissions, service/human kind and explicit-timezone validity.
It must securely verify credentials/issuer/audience and provide bounded, current
authorization revalidation, not trust arbitrary proxy headers or cached actor labels.
Its implementation/key custody/SSO/RBAC/RLS require separate deployment review. Default
denial is intentional when that authority is unavailable. Tests install a clearly
test-only `FixtureIdentities` adapter; fixture authentication is not production SSO.

`Principal.require` independently enforces company, lifetime, permissions and identity
kind. A canonical subject must stay stable across issuer aliases for maker-checker.
Permissions are FINANCE_READ, PROPOSE, REVIEW_SOURCES, REVIEW_POLICY,
REVIEW_TAX_POLICY, APPROVE and SIMULATE_POST. Human principals review/publish/propose/
approve. Only a separately entitled **service** principal may simulate-post. Every
proposal requires controller approval; no automatic cash-application bypass is enabled.
The approver's subject must differ from the maker's, regardless of actor labels or
issuer aliases. Maker, source reviewer, policy reviewer and approver grants are
revalidated before financial use. Missing/revoked/expired authority fails closed.

Audit provenance contains issuer, subject, authorization version, permission snapshot,
identity kind and authentication/expiry dates, never raw credentials. Case event actor
IDs are stable identity digests; full provenance remains in finance audit/history.

## Versioned policies and tax abstention

`FinancePolicy` is immutable, company-scoped and versioned by reference plus contiguous
version/predecessor. A different successor cannot fork the same predecessor. Only
REVIEW_POLICY may publish; tax rules additionally require REVIEW_TAX_POLICY. Reviewer
identity and verification time come from the authenticated action, not input labels.
The read contract exposes `reviewed_rules` with inherited `verified_by`,
`verification_date` and `policy_version_id`. Old versions remain visible; publishing a
successor/disabled policy invalidates active proposals using the predecessor.

The chart config maps BANK 1010, AR 1200, INCOME_TAX 1310, GST_TAX 1320, UNAPPLIED
2300, ALLOWANCE 4100 and OUTPUT_GST 2110 by default. Codes are configurable and distinct.
OUTPUT_GST is present as configuration but is **not** an allowed journal role here.
Existing posted account codes cannot silently change roles. A recognized receipt's bank
and clearing accounts cannot change between applications. Fictional cash/noncash caps
and approval TTL (1–3600 seconds, default 900) are policy controls, not legal thresholds.

The tax interface supports only an exact, reviewer-stipulated **synthetic fixture**.
Rules record ID/version, IN-SIMULATION jurisdiction, SYNTHETIC_STIPULATION provision,
SYNTHETIC_ONLY transaction category, effective dates, STIPULATED_AMOUNT basis,
explicit deduction date, exact company-owned case/customer/receipt/invoice/claim IDs,
integer-paise amount, eligibility preconditions, required evidence IDs and recognition
policy. Rate/threshold/source_url are explicitly null for this fixture mechanism;
reviewer and verification date are inherited from the immutable policy record.
No universal TDS percentage, threshold, supply classification or legal provision is
inferred. A real/nonfixture or unestablished case is NEEDS_TAX_REVIEW.

`approved_fixture=true` is necessary but insufficient. The controller-reviewed rule
must match every scope/amount/date, the remittance extraction must be current and
unambiguous, and immutable signed/current source evidence must independently verify.
All relevant tax sources are boundedly checked for contradictory/unknown tags or
amounts. Income-tax TDS and GST-TDS have distinct tags and receivable accounts.
Claim/evidence originals must be explicitly synthetic for this fixture path. Source
HMAC authentication is not legal eligibility, user approval or PDF PKI. M06 tax
retrieval still returns tax review; M08 adds the independent reviewed fixture policy.
An optional AI finding must be current, same-claim and factual SUPPORTED, but it never
substitutes for evidence/rules/approval; tax findings are not legal authority.

Commercial allowances need their own exact reviewed fixture rule and fully supported
M06 deterministic predicate, including complete contradiction/POD/conditions checks.
Unexplained damage/short-payment/promotion differences are not discounts or writeoffs.
An unsupported treatment has allowed_paise=0 and stays in AR. Excess/unknown tax goes
to tax review, not an automatic customer chargeback or allowance.

## Source review and financial proposal

A separately authenticated REVIEW_SOURCES action attests current imported bank/invoice
provenance and exact intended cash allocations. It binds source hashes, the current
case/context, receipt/customer/invoice versions and an existing current matching proposal.
This T0 human review is separate from M02's locally asserted matching labels. It is
not an external live-bank validation service. The source review expires at the earlier
of the authenticated proof's expiry and one hour. Refresh it to regenerate proposals.

The matching proposal must be EXACT_MATCH or exhaustive UNIQUE with verified intent;
mathematical uniqueness alone, ambiguous subsets, incomplete search, stale references,
wrong customers, closed invoices and unavailable cash fail. Partial cash allocations
may consume no more than the uniquely supported amounts; other cash stays unapplied.
Source rows/import digests are independently checked against the immutable CSV data.
Unexplained baseline balance changes without allocations/settlements fail conservation.

Proposal snapshots preserve the algorithm (`accounting-simulator-v1`), exact case and
financial versions/hashes, matching/source-review/policy IDs, configuration/trust digest,
rule/treatment/evidence IDs, allowed/unsupported amounts and planned journal lines.
Callers cannot supply arbitrary journal lines. Same-key changed requests conflict;
identical concurrent requests share their intended proposal snapshot. A new source
review produces a new proposal; original proposals and decisions are never rewritten.

States: DRAFT -> VALIDATED -> PENDING_APPROVAL -> APPROVED / REJECTED ->
SIMULATED_POSTED (only from APPROVED). Active proposals can become INVALIDATED.
Every transition has immutable version history. Approval binds the exact proposal
version/snapshot and expires at the earlier of proof expiry and policy TTL. Source/case
events and policy supersession persist invalidations. Unannounced balance/file changes
also compute stale immediately and invalidate on attempted use. GET never writes.

## Journals and atomic simulated posting

At the first authorized cash recognition/application for a receipt, journal A records
the **whole immutable receipt** once: Dr Bank / Cr Unapplied Receipts. Raw unauthenticated
CSV ingestion alone does not book a bank journal. Subsequent applications reference
the existing recognition and produce only journal B. Bank recognition is unique per
company/receipt; application is unique per company/proposal.

Journal B debits clearing for actual cash consumed, plus separately approved supported
tax receivable/allowance amounts, and credits AR per invoice for their exact sum.
Every line has one positive side, a permitted account and a scoped invoice where
required. Each journal balances independently with no fractional paise or overflow.

CASE-204, reading the unchanged `fixtures/demo-case.json` as a test oracle:

| Journal | Debit paise | Credit paise |
|---|---|---|
| A | Bank 11,650,000 | Clearing 11,650,000 |
| B | Clearing 11,650,000; approved fixture income-tax receivable 100,000 | AR 11,750,000 |

AR starts at 12,000,000 and remains 250,000. Unsupported damage creates no debit and
remains AWAITING_CUSTOMER_EVIDENCE. Approved fixture tax resolves only with the actual
ledger settlement proof. Cash becomes fully applied. Case state is PARTIALLY_SETTLED;
operational closure/recovery/reviewer correspondence remains M09, even with zero AR.

The service performs read-only evidence preflight, then serializes the company, locks
the proposal/receipt/invoices and rechecks the complete input snapshot. Role/approval/
policy versions, original hashes, available cash, invoice bounds, source currentness,
numeric rule conditions and exact regenerated journals must all agree. Balance alone
is insufficient. Ledger rows, allocations/noncash settlements, account movements,
receipt/invoice balances, case/claim versions, audit and idempotency results commit in
one transaction. Failure at any point rolls everything back. No graph receives these
credentials or functions; the seven M06 read-only capabilities remain unchanged.

Deferred PostgreSQL guards independently enforce double entry, provenance, bank-once,
cash clearing, per-invoice AR and separate noncash accounts, immutable records,
proposal version/history, approval binding, conservation and account movements.
Conservation guards protect ledger-participating rows; source-only legacy data is
unchanged and its baseline is checked before first posting. Repeated/concurrent posting
returns one immutable ledger result or a conflict; replay after posting never reapplies
cash, recreates tax or rebooks bank. Account balances are **net simulated movements**,
not a fabricated complete opening general ledger. Imported outstanding AR remains
the invoice balance source of truth. Reversals/negative journals are not implemented.
Creation requires a supported positive cash application. A later zero-cash/noncash-only
follow-up is unsupported and remains in review; the service never invents another receipt.

## API and reproduction

New endpoints require a trusted identity adapter, JSON, and UUID Idempotency-Key on
commands. X-Actor-ID grants no authority and is unnecessary here. Tenant is the server
company. Read APIs require FINANCE_READ; lists use limit (1–100) and offset.

| Method/path | Required permission / payload |
|---|---|
| POST `/finance/policies` | REVIEW_POLICY (+ REVIEW_TAX_POLICY for tax), PolicyInput |
| GET `/finance/policies` | FINANCE_READ; immutable versions and reviewed rule metadata |
| POST `/cases/{id}/finance-source-reviews` | REVIEW_SOURCES; current case version/context, matching_proposal_id, cash[{invoice_id,amount_paise}] |
| POST `/cases/{id}/journal-proposals` | PROPOSE; source-review fields plus policy_id, source_review_id, claims[{claim_id,invoice_id,rule_id?,finding_id?}] |
| GET `/journal-proposals/{id}` | FINANCE_READ; source hash, journals/treatments and computed staleness |
| POST `/journal-proposals/{id}/request-approval` | Maker PROPOSE; expected_version and expected_snapshot_sha256 |
| POST `/journal-proposals/{id}/review` | Different-subject human APPROVE; version/hash, APPROVE or REJECT and fixed reason code |
| POST `/journal-proposals/{id}/simulate-post` | Service SIMULATE_POST; expected version/hash |
| GET `/finance/journals`, `/finance/account-balances`, `/finance/audit` | FINANCE_READ; simulation ledger and immutable provenance |

Use actual returned IDs/versions/hashes, not invented approval labels. OpenAPI/Pydantic
schemas in `finance_contract.py` are exact. Mutations have bounded duplicate-key rejecting
JSON and omit submitted sensitive values in errors. No source text is executed.

Reproduce with disposable databases only:

```text
uv run --frozen pytest tests/test_finance.py tests/test_finance_domain.py tests/test_finance_restart.py --require-postgres
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

The restart runner owns its labelled temporary PostgreSQL container/volume, never the
shared development database. It now verifies finance journal/approval/history/counter
persistence, fresh API processes/connections and no duplicate posting after restart.
The complete gate retains every earlier test/check; its bounded test timeout is 30
minutes and CI ceiling 35 minutes to accommodate the larger disposable-schema suite.
These are harness ceilings, not weakened product search/approval/security limits.

Remaining limitations: real trusted identity/provider integration and broad G1, upstream
source PKI/key custody/live-bank authentication, real tax/legal rules, live Gemini,
remote CI and Argon benchmark/ablation remain unverified. External AI stays disabled.
No production-ready identity/tax/accounting claim follows from fixture tests. All
observed commands, counts, logs, migration fingerprints and checkpoints are in STATUS.

## Milestone 09 reviewer integration

M09 adds local demo identity only for operational metadata; it never installs a finance adapter or grants financial permissions. Submission and approve/reject continue to use the M08 verified identity/current-source/version/hash/maker-checker gates above. Evidence requests and late source-backed replies invalidate stale unposted proposals; posted journals and approvals remain immutable history. Operational closure now uses independent financial/claim/work checks and current verified controller authority. Production identity remains unavailable by default. See [REVIEW_RECOVERY.md](REVIEW_RECOVERY.md).
