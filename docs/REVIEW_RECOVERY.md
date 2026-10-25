# Review and recovery — review-1.0

Milestone 09 implements the original `prompts/09-approvals-recovery.md` checklist. This is an operational
review workflow, not a mail service, production identity provider or new settlement
mechanism. The M08 accounting simulator and all CSV 1.0 schemas remain unchanged.
Gemini and external investigations remain disabled. No dataset is constructed or used.

## Two explicit identity boundaries

`REVIEW_DEMO_ENABLED=false` and `REVIEW_ACCESS_ENABLED=false` are the defaults. An administrator on the local host can
explicitly provision single-company **demo** users, using the configured organization:

```text
uv run --frozen python -m clearledger.review_users analyst --role AR_ANALYST
uv run --frozen python -m clearledger.review_users controller --role CONTROLLER
uv run --frozen python -m clearledger.review_users auditor --role AUDITOR
```

Enable REVIEW_DEMO_ENABLED in the ignored local environment first. The CLI prompts
for a 16–128 character password, never takes passwords in shell arguments, and never
prints one. There are no default users/passwords or unauthenticated HTTP admin routes.
Changes require `--expected-version N`; `--disable` revokes access. Changes increment
the user's grant version and append a provisioning audit event in the same transaction.
Every outstanding session from a previous version immediately fails.

POST `/review/demo/login` takes `username` and `password`, returning a random 48-byte
opaque access token, an absolute expiry, `authority=LOCAL_DEMO_ONLY` and
`financial_authority=false`. Use `Authorization: ReviewDemo <token>`; it is not a finance
bearer credential. The response is no-store/no-cache. Only its SHA-256 is persisted;
passwords have independent random salts and PBKDF2-SHA256 with 600,000 iterations.
Sessions last 30 minutes. Company-wide admission permits 20 login attempts per rolling
minute, shared through PostgreSQL, including failures. Login is serialized, unknown
users receive equivalent bounded password work, and diagnostic responses contain no
passwords, session tokens or submitted values. Logout appends revocation; no history
is deleted. There is no session refresh or password-recovery email.

Demo requests require a direct loopback peer (the ASGI fixture peer is test-only).
Forwarded-address headers are ignored. **Do not expose the demo through a public
listener or reverse proxy**: this is local synthetic-data support, not hardened SSO,
MFA, remote access or production credential lifecycle management. Host administrators
remain trusted. The aggregate login throttle can temporarily block other local users.

For verified review authority, the existing trusted `IdentityVerifier` port must
authenticate and revalidate real canonical issuer/subject/company/current grants.
REVIEW_READ gives AUDITOR, REVIEW_WORK adds AR_ANALYST, REVIEW_CONTROL gives CONTROLLER.
Human identity, validity and current grants are checked under the company lock again
before use. Service principals cannot act as human reviewers. Role strings, X-Actor-ID,
customer statements and AI findings cannot choose or promote a role.

Enabling REVIEW_DEMO_ENABLED automatically protects the **whole existing business API**,
including CSV imports, documents, matching, case commands and reads. With demo disabled,
REVIEW_ACCESS_ENABLED=true enables the same boundary for a real trusted identity port.
Omitting credentials or using old document/case service tokens cannot bypass role mode.
AR_ANALYST/CONTROLLER can perform existing source intake and nonfinancial operations;
AUDITOR is read-only. The existing POST evidence search/verify endpoints remain true
PostgreSQL READ ONLY operations and are available to auditors. Every legacy mutation
rechecks current grants under the company lock; reads recheck under its shared lock.
An admitted source write records full role provenance atomically and replaces caller
X-Actor-ID with a stable canonical actor digest. No authorization token is rewritten.
Original source/state/evidence validation remains mandatory. No local role can lift the
old capability gates for accepting/settling claims or marking a case financially ready.

The original local M00–08 compatibility profile remains when both switches are false;
it is **not a protected shared/production deployment**. Real deployment must enable
REVIEW_ACCESS_ENABLED and supply a reviewed identity adapter; absent authority fails
closed. Broad deployment/identity/RLS review is still G1, not waived by compatibility.

Demo roles authorize source intake and bounded operational metadata work. They **never** install a
finance adapter, approve/reject journals, publish financial policies, post, or close a
financial case. M08's finance endpoints still default to 503 without a trusted adapter.
Closure additionally requires current verified APPROVE and REVIEW_CONTROL grants,
independently revalidated; local CONTROLLER is insufficient. Positive financial/closure
tests use an explicit test-only adapter, not production SSO. G1 production identity,
deployment-wide authorization/RLS and real-data/shared deployment remain unresolved.

## API and permissions

Company scope always comes from server configuration. Reads are paginated (1–100,
offset) and never write. All role-based routes authenticate the current session/grants.

| Route | Authority / behavior |
|---|---|
| GET `/review/me`, `/review/demo/users` | All roles; safe identity/user metadata, no credential hashes |
| GET `/review/cases`, `/review/cases/{id}`, `/review/cases/{id}/claims` | All roles; existing typed case/claim views, scoped to company |
| GET `/cases/{id}/review-actions`, `/review/audit` | All roles; immutable drafts/responses/reasons and allowed/denied action provenance |
| POST `/cases/{id}/review-comments` | Analyst/controller; bounded untrusted comment, fixed reason code |
| POST `/cases/{id}/draft-evidence-request` | Analyst/controller; immutable source-linked draft, never sends |
| POST `/cases/{id}/request-evidence` | Controller; affected claims plus optional exact journal proposal/version/hash; invalidates unposted work |
| POST `/cases/{id}/record-response` | Analyst/controller; validated document/span/claim-version inputs, optional reply thread |
| POST `/cases/{id}/reopen` | Analyst/controller; NEW_INFORMATION, legal state edge, reinvestigation/invalidation only |
| POST `/cases/{id}/close` | Verified human controller + APPROVE, different from posted proposal maker; independent closure predicates |
| POST `/review/demo/logout` | Current demo session; immutable revocation |

Financial submission and approve/reject remain the existing M08 endpoints:
`/journal-proposals/{id}/request-approval` and `/journal-proposals/{id}/review` with
decision APPROVE or REJECT, expected proposal version/hash and a fixed decision reason.
No duplicate approval implementation or relaxed identity path is added. Self approval,
expired/revoked grants, stale sources/policies and repeated posting remain prohibited.
Finance approval/rejection reasons and immutable histories remain in finance audit.

Review commands require UUID `Idempotency-Key`, strict `expected_case_version`,
`expected_context_sha256`, a reason enum, and optional `comment` (at most 2,000 chars).
Pydantic/OpenAPI in `review_contract.py` is exact; unknown fields, bool/fractional
versions, duplicate IDs, oversize/duplicate-key JSON and invented authority are rejected.
401/403/503 denote missing/insufficient/unavailable authority; 404 hides foreign objects;
409 denotes stale input, conflict or unsatisfied lifecycle predicates. Errors omit inputs.
Meaningful allowed actions and safe denial codes are audited; denied actions roll back
all case/evidence effects before their separate security audit is committed.

## Drafts and evidence

DraftInput adds 1–20 invoice IDs, 0–20 claim IDs and 0–20 optional delivery record IDs.
The reason is CUSTOMER_FOLLOW_UP, MISSING_EVIDENCE or CONTRADICTORY_EVIDENCE. A fresh
PostgreSQL READ ONLY evidence preflight verifies the case/customer/current context.
Invoice facts must have intact immutable CSV provenance. They remain native records,
not signed external evidence or authorization. Delivery facts require current scoped
WMS/POD manifests, configured source authentication, valid originals/canonical spans,
signed/approved source metadata, same customer/invoice and valid invoice-date period.
Other date bases abstain. These source signatures are not user or legal authority.

The persisted draft contains a fixed neutral template, no recipient, immutable source
pointers (versions/hashes/row or canonical span), projected financial/delivery facts,
claimed amounts explicitly labeled unverified, and its source digest. Reviewer comments
are stored as untrusted annotations, never inserted into executable templates or models.
Missing evidence is requested, never fabricated. Drafts have `transmitted=false` and no
send endpoint, SMTP client, customer messaging tool or outbox transmission event.

ResponseInput adds an existing AttachInput (document version/raw and canonical digests,
exact span, claim IDs and source-backed invoice relationship), exact expected claim
versions, and optional `in_reply_to` draft/request ID. The reason is CUSTOMER_RESPONSE.
Empty claim targets permit new case-level evidence; they do not fabricate new claims.
An evidence-request reply must cover exactly its requested claims. Incomplete responses
can be recorded without claiming they satisfy that request. A thread cannot cross cases
or tenants. The original bytes remain immutable; a recorded response has
`sender_authenticated=false`. An operator recording it has not authenticated the sender
or accepted the deduction.

Existing attachment validation enforces invoice/customer ownership and complete source
reference spans. The transaction appends response provenance, reopens affected claims
and a settled/closed case to INVESTIGATING through existing legal edges, appends
invalidations for stale unposted proposals/hypotheses/findings and schedules the existing
leased outbox reevaluation. Previously investigated claims reuse M07's selective rerun.
Posted journals/settlements and earlier approvals/reviews are retained, never reversed.
New extracted claim assertions enter through the normal document/event workflow.

## Closure and financial invariants

PARTIALLY_SETTLED continues to come from M08's actual ledger proof. A case may close with a fresh context and SETTLED_AND_COMPLETE from READY_TO_APPLY or
PARTIALLY_SETTLED. A reopened INVESTIGATING/AWAITING_REVIEW/AWAITING_EVIDENCE case can
advance through the existing legal readiness edges **only after the same complete
closure proof passes**. Those intermediate versions/events are persisted, without any
new posting. NEW/MATCHING/CLOSED are not new-close entry states. This permits reclosure
after a harmless late reply and completed reevaluation, while unresolved claims/actions
still block it. Every close requires:

- Verified customer and no outstanding attention codes.
- Linked company/customer invoices exist and all open paise are exactly zero.
- Linked receipts exist, all are FULLY_APPLIED and unapplied paise are exactly zero.
- Every operational claim is RESOLVED with current immutable source provenance.
- At least one committed simulated-posted proposal; no active unposted proposal.
- Closure reviewer differs from every posted proposal's initiating subject.
- No pending/retry/dead case work; all mandatory evidence requests have recorded replies.

No mutation here makes a balance zero or resolves a claim. Zero AR alone, a customer
email, a balanced proposal, an AI finding or a controller label cannot satisfy closure.
Unsupported damage/tax claims keep the case open. Negative/reversal and zero-cash-only
noncash follow-up remain unsupported M08 limitations; this milestone does not work
around them. Reopening changes operational state only, not ledger or financial history.

## Transactions, bounds and persistence

Additive migration 0011 adds seven scoped tables: demo users/sessions/revocations/auth
events, review actions/commands/audit. Composite company FKs, unique command/token keys,
append-only UPDATE/DELETE/TRUNCATE guards, versioned user writes and deferred audit/
case-version checks protect provenance. No old tables or journal rules are altered.

Commands serialize on the existing company lock and recheck versions/context/current
authority after preflight. Same-key identical requests replay one immutable action;
changed requests conflict. Replay after a subsequent case revision/source change is
explicitly stale. The fingerprint binds stable canonical actor identity, not a transient
login timestamp. Two different keys with one expected mutable snapshot yield one commit
and one conflict. Draft/comment-only actions do not change case versions or financial
state. Their histories remain distinct intentional actions under new keys.

Database lock/statement waits are bounded to 3/10 seconds; document originals use the
existing 100-document/16MiB evidence budget. Closure scans at most 2,000 proposals and
2,000 review actions, failing closed beyond those bounds. Older case/group limits apply.
Security-denial audit contains identity/operation/fixed code/target ID, never source text,
passwords or tokens. Transaction crashes roll back evidence/state/history together.

```text
uv run --frozen pytest tests/test_review.py tests/test_review_access.py tests/test_review_security.py tests/test_review_closure.py tests/test_review_domain.py tests/test_review_restart.py --require-postgres
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

The full gate includes every previous regression. The isolated runner additionally
checks review sessions/draft/audit persistence, fresh API processes/connections and
idempotent replay through its own labelled disposable PostgreSQL container restart.
Development migrations only upgrade; disposable migration tests alone may downgrade.
Actual commands/counts/logs/checkpoints and remaining limitations are in STATUS.md.
