# Persistent deduction cases — contract v1.0

Source-backed correlation tasks and controller decisions now bridge document and
receipt cases using existing monotonic merges and reevaluation, without manual claim
recreation or fabricated matching proposals. Independent source verification is
required even for a controller. New default-off option, scoped immutable provenance,
frontend APIs and unsupported cases: [CORRELATION_REVIEW.md](CORRELATION_REVIEW.md).

Post-M09 extraction automation is an opt-in scheduling extension, not a case-state
or finance change. Existing committed extraction events already create source-linked
claims, including validated NEEDS_REVIEW facts. CASE_AUTO_INVESTIGATE_EXTRACTIONS
defaults false; when true, the existing bounded reevaluation schedules first
deterministic investigations for current extracted claims. No facts are recreated,
receipt/customer association inferred, or model status promoted to claim authority.
Limits, provenance and the remaining correlation gap: [INVESTIGATIONS.md](INVESTIGATIONS.md).

M08 extension: `verified_settled_paise` now derives from committed noncash settlements,
bounded to signed-bigint paise; without settlements it remains zero. Historical M05
snapshots below remain unchanged. Independently approved posting can advance private
proof-backed claim states and PARTIALLY_SETTLED; public actor-label gates remain closed.
Posted allocations supply T1 customer provenance when old matching versions become stale;
conflicts abstain. Case/source changes invalidate active finance proposals. Closure and
recovery remain M09. Contract: [ACCOUNTING_SIMULATOR.md](ACCOUNTING_SIMULATOR.md).

Milestone 05 adds durable **review metadata**, not deduction adjudication, approvals,
cash application or posting. Financial CSV DATA_CONTRACT v1.0 and existing matching
and document interfaces are unchanged. All money remains integer paise. A customer
claim may exceed the cash/shortfall; missing amounts stay null. The case reports
`claimed_total_paise`, `unknown_amount_count`, `verified_settled_paise: 0`,
`requires_human_review: true`, and `financial_authority: false`. Aggregate sums beyond
signed bigint report null instead of wrapping or using floats.

## Sources and identity

Committed receipt creation, matching evidence/proposals and document events publish
an immutable domain event plus an outbox row **in the source transaction**. Failed
imports publish nothing. Unresolved receipts acquire a durable case; source-validated
parsed remittance claims acquire a document case, even before a receipt arrives.
The conservative implementation also tracks receipts with matching proposals: a
matching suggestion has not settled their unapplied cash.

Names, invoice strings and operator labels do not establish customer/payment intent.
Document/receipt cases merge only through an existing **current LINKED document
association**, with the existing source-backed UTR attestation and receipt-version
requirements. Unattested/candidate/ambiguous associations remain separate. Customer
projection comes from existing deterministic receipt identity resolution; conflicting
known customers prevent merging and raise `CONFLICTING_CUSTOMER_SOURCES` for review.
Matching-derived invoice links retain the exact proposal ID. They are candidate
relationships, never allocations or approvals.

Every distinct validated claim assertion is immutable and separately tracked with
category, nullable amount, description/amount/reason source spans, document and
extraction provenance. Repeated identical assertions reuse their claim; each source
extraction/index is retained. Changed assertions create additional unresolved claims;
same-description disagreements raise `CONFLICTING_CLAIM_ASSERTIONS`. Superseded claims
remain visible with `source_current: false`; they are not silently removed or netted.

Merging preserves physical case/claim/source IDs and all original histories. A child
case has a single immutable canonical redirect. GET resolves the root and reports the
requested ID; commands to an old ID return 409. `/versions` addresses that physical
case's history; other case collections include its merged members.

## State machines and authority

Case vocabulary and graph follow API_AND_STATES:

`NEW → MATCHING → INVESTIGATING → AWAITING_EVIDENCE / AWAITING_REVIEW / READY_TO_APPLY`

Waiting cases reopen to INVESTIGATING. READY_TO_APPLY may lead to PARTIALLY_SETTLED
or CLOSED; settled/closed cases may reopen. Claim vocabulary is
`EXTRACTED → INVESTIGATING → SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE /
NEEDS_TAX_REVIEW → ACCEPTED / DISPUTED / AWAITING_CUSTOMER_EVIDENCE → RESOLVED`,
with re-investigation edges. Exact operational graphs are typed in `case_domain.py`
and enforced by PostgreSQL triggers.

Milestone 05 exposes investigation/evidence/review and claim insufficiency/dispute
metadata. **SUPPORTED, CONTRADICTED, ACCEPTED, RESOLVED, READY_TO_APPLY,
PARTIALLY_SETTLED and CLOSED require validated adjudication/settlement capabilities
from later milestones and currently return 403 on otherwise legal transitions.**
This preserves the original state vocabulary without letting a local operator label
assert financial authority. NEEDS_TAX_REVIEW is an uncertainty route, not a tax
conclusion; tax claims cannot be disputed through this generic command. No claim
transition authenticates a customer, settles money, or sends a customer message.

## Persistence and concurrency

Migration `0007_cases` adds cases, case_receipts/documents/invoices, claims,
claim_sources/versions, evidence_links, hypotheses, case_proposals/invalidations,
case_versions, domain_events, outbox_events/deliveries, event_consumptions,
case_reevaluations and case_commands. Every relationship is scoped by organization;
receipt/document anchors are unique per company. Composite FKs bind versions,
claims and evidence to their owners. Database triggers reject history edits/deletes,
truncation, mutable assertion changes, illegal transitions and revisionless writes.
Originals remain in the existing immutable document store.

Mutations take the existing company advisory lock and compare expected versions;
GETs take its shared form for internally consistent multi-query views. New command
keys are unique per company; the request fingerprint includes operation, case,
claim, actor and typed body. Identical concurrent keys reuse one result; different
keys with one expected version yield one success and one 409. A replay whose result
has since changed returns 409, never an obsolete success represented as current.

Every case change records an immutable version snapshot and source-linked domain
event. Case/claim revisions are database-required at commit. Actual receipt/invoice
versions, balances, validated source hashes, extraction revisions and associations
form a fresh context fingerprint. A changed context is reported as stale immediately,
even before outbox delivery; commands reject it except explicit versioned refresh.
Existing immutable matching proposals are not edited. Case-local proposal bindings
gain immutable invalidation records; current views also check source snapshot and
case staleness. They cannot authorize using a stale proposal.

New evidence increments case version, reopens affected reviewed claims, invalidates
only their hypotheses (all case proposal bindings conservatively), and schedules an
explicit claim-ID reevaluation. Unaffected claims keep their current hypothesis.
The current hypothesis is an immutable `UNASSESSED` placeholder, not an investigator.
Superseded work records its scheduled/evaluated versions and evaluates current inputs;
empty target lists remain empty. No duplicate case or financial application is made.

## APIs and credentials

All case endpoints require a strong local `DOCUMENT_API_TOKEN` bearer credential.
Optional distinct `CASE_READ_TOKEN` (at least 32 characters) allows GET only. Actor
headers record provenance; they grant no role or approval authority. This local
service boundary does **not** resolve deferred production authentication/RBAC G1.
Company scope is server-configured, never taken from a caller body.

- GET `/cases`: bounded limit 1–100/offset, optional state/customer_id/receipt_id.
- GET `/cases/{id}`, `/claims/{id}`; case `/claims` supports a state filter.
- GET case `/events`, `/versions`, `/evidence`, `/hypotheses`,
  `/matching-proposals`, `/reevaluations`, `/work`; claim `/versions`, `/evidence`.
  All collections are paginated. Work views omit lease secrets and raw errors.
- POST case `/transition` (`target`), `/investigate`, `/refresh`.
- POST case `/claims/{claim_id}/transition` with target and expected_claim_version.
- POST case `/attach-evidence` with document ID/version, raw/canonical hashes,
  exact canonical Span, relation and optional claim IDs. Case-owned documents are
  required; a new document additionally needs a case/customer-owned invoice link
  and independently validated complete source invoice-reference span. A document
  already owned by another case requires source-backed correlation/merge.
- POST case `/matching-proposals` with matching_proposal_id, verified current and
  owned by a receipt in the case.
- POST `/cases/reconcile` with source `receipts`, `document_events`,
  `matching_proposals` or `matching_evidence`, limit ≤100 and optional after_id.
  This bounded, naturally deduped cursor backfills pre-migration sources; repeat
  until has_more is false. No arbitrary event/payload ingestion API exists.

Every case command requires `expected_case_version`, `Idempotency-Key` UUID and
`X-Actor-ID`. Claim commands also require `expected_claim_version`. Extra fields
are rejected. 401/403 cover missing/read-only authority, 404 hides foreign IDs,
409 covers invalid/stale/replayed conflicts, and 422 covers malformed source/input.
Errors omit submitted values and source content. Evidence SUPPORTS/CONTRADICTS is
an **unverified analyst relationship annotation**, never the claim's adjudication.

Example (shell variables contain local credentials and current IDs/versions):

```powershell
$headers = @{ Authorization = "Bearer $env:DOCUMENT_API_TOKEN"; 'X-Actor-ID' = 'analyst'; 'Idempotency-Key' = [guid]::NewGuid().ToString() }
Invoke-RestMethod "$base/cases/$caseId/investigate" -Method Post -Headers $headers -ContentType application/json -Body (@{expected_case_version=$version} | ConvertTo-Json)
```

## Durable outbox operation

Run the API and a separate process using the same organization/database/originals:

```text
uv run --frozen python -m clearledger.case_worker
uv run --frozen python -m clearledger.case_worker --once --limit 100
```

PostgreSQL provides the queue; no Redis/framework dependency is necessary for this
bounded metadata work. `FOR UPDATE SKIP LOCKED` claims distinct leases. Transport
is at least once; consumption keyed by organization/event/consumer commits with all
case effects and acknowledgement. Failures roll back all effects. Attempt/phase
history is append-only. Expired leases are reclaimable; old tokens cannot acknowledge
new leases. Default lease 30 seconds (5–300), attempts 3 (1–10), exponential retry
1/2/4… seconds capped at 60. Persistent DEAD rows require operational investigation;
there is no automatic unlimited retry/redrive or financial side effect. Worker output
contains outcome counts only; stored failure diagnostics use fixed safe codes.

Analysis is bounded to 256 merged members, depth 64, 100 receipts/documents and
associations per document, and 2000 group rows/claim targets. Exceeding bounds fails
closed for review; it never truncates evidence into a successful determination.
Run another bounded drain for a larger pending queue. Processing is eventually
consistent: source acknowledgement means committed ingestion, not completed case work.

Gemini/extraction is never called by case processing. Future evidence validation,
investigation, tax policy, RBAC/approvals, recovery and accounting remain 06–09.

## Milestone 06 source integration

External evidence registration now publishes a scoped source event through the existing
outbox. Immutable source revisions and fresh integrity participate in case context and
relevant per-claim bases. Only matching categories/source invoice references are targeted;
unrelated claims retain their current basis. Reads reject stale contexts even before
worker delivery. Case registration/worker operations remain distinct from the database-
read-only evidence tools. Verifier SUPPORTED is a factual predicate, not the claim state
SUPPORTED or permission to accept/settle; existing state gates remain. Evidence contract,
limits and trusted-source assumptions: [EVIDENCE.md](EVIDENCE.md).

Milestone 07 adds separate persistent investigation runs/findings and native graph
checkpoints. Existing UNASSESSED placeholders remain immutable historical records;
SUPPORTED investigation findings do not bypass claim adjudication gates. Fresh workflow
completion can move a case only to AWAITING_REVIEW through existing legal metadata
transitions, never acceptance/settlement. New evidence appends finding invalidations
and reinvestigates only affected previously investigated claims. Per-claim currentness
is separate from whole-run snapshot staleness. APIs, durable retry/lease semantics and
oversized-case review behavior: [INVESTIGATIONS.md](INVESTIGATIONS.md).

## Milestone 09 operational extension

The M05 public actor-label state gates remain unchanged. New authenticated operational commands append review/draft/response histories, use existing evidence attachment/reevaluation/invalidation, and conservatively reject stale snapshots. M08 PARTIALLY_SETTLED is retained; trusted controller closure checks balances and mandatory operational completion. Late source-backed customer evidence can reopen CLOSED without reversing ledger history. Sender identity and deduction legitimacy are never inferred from an operator recording a reply. See [REVIEW_RECOVERY.md](REVIEW_RECOVERY.md).
