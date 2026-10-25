# Evidence retrieval and verification — evidence-1.0

Milestone 06 implements `prompts/06-evidence-search.md`. Retrieval/verification is
read-only and deterministic. `SUPPORTED` means **the requested source-fact predicate**
passed, never deduction legitimacy, authenticated user approval, tax eligibility or
permission to settle. All results have `financial_authority=false`; verification
requires human review. Claim/case approval and settlement transitions remain gated.
No investigator, model, MCP, vector database, Redis or financial mutation is added.

## Separate source contract and trust boundary

Financial CSV DATA_CONTRACT v1.0 is unchanged. This separate JSON interface indexes
documents and structured source assertions supplied by Argon/upstream publishers.
Neither pilot dataset is modified or assumed to supply these new manifests. No
automatic indexing, source signing, dataset construction or hidden-answer access occurs.
Unindexed/free-form/scanned material stays in the document system, with missing
structured evidence explicit. OCR/semantic interpretation is not fabricated.

Use existing `/documents` ingestion first. A record references a READY document's
immutable original and canonical text, never an arbitrary file path or URL. Source
types: CONTRACT, PROMOTION, WMS, POD, TAX, INVOICE, REMITTANCE. The latter two supplement
native invoice CSV and remittance claim retrieval; they do not replace those records.

POST `/evidence/records` with application/json, document write bearer credential,
X-Actor-ID and UUID Idempotency-Key. Exact schema: `RecordInput` in
`src/clearledger/evidence_contract.py`; extra fields are forbidden at every level.

| Field | Required representation / meaning |
|---|---|
| contract_version | `evidence-1.0` (default) |
| source_system, source_record_id | 1–100 ASCII letters/digits/`_.:/-`; stable source identity, not paths |
| revision, previous_id | Positive integer; revision 1 has null predecessor; later revisions must extend the current predecessor by exactly one |
| customer_id, invoice_id | Scoped UUIDs; customer required; invoice required for WMS/POD/TAX/INVOICE/REMITTANCE, optional for customer-wide clauses/promotions |
| document_id, document_version | Scoped UUID and exact positive integer version |
| raw_sha256, canonical_sha256 | Lowercase 64-character SHA-256; original bytes and existing canonical pages digest respectively |
| excerpt | Exact `{page,start,end,quote}` Span, 1-based page, 0-based Unicode offsets, exclusive end, at most 2000 characters |
| customer_reference | `{value,span}` with actual customer external reference and exact labeled source span |
| invoice_reference | Same form with actual invoice number; required together with invoice_id |
| categories | Nonempty unique list of up to 7 existing claim categories; source metadata, not an adjudication |
| effective_from, effective_to | Exact YYYY-MM-DD; inclusive valid interval, end >= start |
| occurred_at, recorded_at | Explicit-timezone ISO timestamps including seconds; normalized UTC; occurrence <= recording, no future recording at ingestion |
| signed_at, approved_at | Explicit-timezone timestamps or null (unknown); cannot postdate source recording |
| date_basis | INVOICE_ISSUED or RECEIPT_OCCURRED; server resolves the date from current case-owned transactional records |
| fact | Strict discriminated object below; financial values are integer paise, never floats, rupees or tolerances |
| key_id, signature | Both null for unverified sources, or a configured source key ID plus HMAC-SHA256 lowercase hex signature |

Each numeric value is `{value,span}`. Money: strict int 0..9223372036854775807.
Quantities: strict int 0..2147483647. Each reference is `{value,span}`. All field spans
must occur inside the excerpt on its page, have the matching label immediately
before them, exact text and complete delimiters. Money text explicitly states INR/Rs
or integer paise. Labels below are case-insensitive and end with a colon.

| fact.type | Exact additional fields / source labels |
|---|---|
| CONTRACT | limit (Money / LIMIT), conditions |
| PROMOTION | amount (Money / AMOUNT), conditions |
| WMS, POD | shipment (Ref / SHIPMENT), shipped/delivered/damaged (Units / SHIPPED/DELIVERED/DAMAGED), unit_value (Money / UNIT_VALUE), unit exactly EACH |
| TAX | amount (Money / AMOUNT), tax_tag INCOME_TAX_TDS/GST_TDS/UNKNOWN |
| INVOICE, REMITTANCE | amount (Money / AMOUNT) |

All records also require CUSTOMER and, when invoice-scoped, INVOICE label/value
spans. Delivered <= shipped and damaged <= delivered. Contract/promotion `conditions`
defaults to UNASSESSED, which abstains. Only a source-authenticated explicit
NO_ADDITIONAL_CONDITIONS attestation permits the bounded predicate to pass. Free-form
or additional commercial conditions require review/future policy, not an inferred
absence of preconditions. These factual predicates do not implement commercial rules.

### Authentication is separate from asserted status

Text saying "signed", a boolean, actor label, uploaded filename or model confidence
cannot authenticate a source. By default no source keys are configured; unsigned
records can be indexed/reviewed but verification cannot promote them to support.

`EVIDENCE_TRUSTED_SOURCES_JSON` is an ignored local SecretStr configuration containing
at most 32 strict objects: organization_id, source_system, key_id, secret (32–256
characters), allowed_kinds (source-type list). Use independent random publisher keys
under separate custody; reusing a document/read bearer token is rejected. Empty
configuration means no trusted origins. Duplicate/malformed config fails closed.
No signing or trust-provisioning endpoint exists, and no key is returned to a UI,
extractor, tool result, subprocess, model or log.

The publisher signs canonical UTF-8 JSON:

```text
{"organization_id": "<server company UUID>", "manifest": <normalized RecordInput excluding signature>}
```

Use sorted keys, compact comma/colon separators and JSON's default ASCII escaping.
Normalization includes all defaults/nulls and UTC timestamp serialization from the
versioned Pydantic contract, including key_id and fact conditions. Compute HMAC-SHA256
with the configured publisher secret. A 64-zero signature placeholder may be used
only while normalizing the schema; replace it with the computed digest. Signature
admission binds company, owner, invoice, complete source pointers, revisions, dates,
statuses and numeric assertions. Altered/unknown/revoked/wrong-kind signatures fail.

This authenticates the **configured upstream attestation**, not a PDF digital
signature, real-world sender, legal contract or tax right. signed_at/approved_at are
upstream-attested statuses; production assurance depends on independently reviewed
publisher/key custody and upstream controls. A local operator cannot elevate an
unsigned record by setting those fields. Native financial imports and extraction
claims explicitly remain `source_authenticated=false`.

## Fixed read-only capabilities and API scope

Read endpoints accept the existing strong document bearer token or distinct GET-only
case credential. This credential may POST a read-only query/verification, but cannot
register records. Production authenticated users/RBAC/isolation remain G1, not solved
by these local credentials. Actor headers never grant financial authority.

Every read starts a fresh PostgreSQL READ ONLY transaction, shared company lock,
3-second statement timeout and 2-second lock timeout. The reader checks read-only
mode, current canonical case version/context hash, verified customer, claim membership
and case-related invoice ownership. Row-lock helpers retain original matching/write
behavior and omit FOR SHARE only in this enforced read-only scope. Tests prove DML
is rejected by PostgreSQL. No tool accepts SQL, arbitrary URLs, file paths or tool names.

POST `/cases/{id}/evidence/search` takes ScopeInput plus `tool`, optional query,
after_id and limit (1–50). ScopeInput requires expected_case_version,
expected_context_sha256, customer_id; optional claim_id and invoice_id narrow scope.
The seven typed allowlisted Python capabilities are:

- find_contract_clauses
- find_promotions
- get_wms_deliveries
- get_proof_of_delivery
- get_tagged_tax_evidence
- get_invoice_evidence
- get_remittance_evidence

The server applies company/customer/case/invoice filters, current immutable source
revision selection, parameterized PostgreSQL simple-config FTS and stable UUID paging.
No arbitrary SQL or semantic/vector search exists. Native invoices retain CSV import
ID/row/hash and current version; remittances retain claim/extraction IDs and exact
document version/offsets. Search hits return source-integrity/authentication/current
flags, stable pointers, masked excerpts and safe typed numeric facts. They are untrusted
data and never executable instructions. More pages mean search_complete=false.

GET `/cases/{id}/evidence/records/{record_id}` with scope query parameters returns
the immutable manifest and full citation for a reviewer; superseded history is retained.
GET `/cases/{id}/evidence/native/{INVOICE|REMITTANCE}/{id}` additionally requires
expected_record_version and expected_source_sha256; it returns the original validated
CSV row or remittance assertion/span. These privileged reviewer views may contain
original confidential data and are **not** model-allowlisted tools. Responses use
no-store/nosniff. Foreign/missing IDs are 404; stale scope/pointers are 409.

## Verification semantics

POST `/cases/{id}/evidence/verify`: ScopeInput with claim_id and invoice_id required,
question, optional receipt_id, and zero to 20 exact Citation objects. A Citation is
record_id + document_id/version + raw/canonical hashes + exact excerpt Span.
Unsupported, fabricated, stale or ambiguous inputs abstain; wrong ownership is hidden.

Questions: CLAUSE_LIMIT, PROMOTION_AMOUNT, DELIVERY_SHORTAGE, DELIVERY_DAMAGE,
TAX_DOCUMENT, INVOICE_AMOUNT, REMITTANCE_AMOUNT. The verifier independently checks
invoice CSV provenance, current claim extraction and unique claim-to-invoice source
reference. A multi-invoice remittance with no individual claim mapping abstains.
Uncertain claim extraction also abstains, even with an otherwise valid clause.
It then checks source/manifest hashes, spans/labels/numbers, key scope/signature,
current revision, owner/category, effective dates, status and chronology.

Early-payment checks require the actual case-owned receipt date, never the earlier
invoice date. A receipt-date basis with multiple receipts requires an explicit receipt
ID. Contract/promotion source statuses postdating the transaction route to review;
retroactive terms are not guessed. Invoice dates are calendar dates; receipt/status
dates use Asia/Kolkata. Late evidence can be recorded later without inventing prior
knowledge. Original document parsing/layout limitations remain in DOCUMENTS.md.

Numeric predicates: claim <= source clause limit; claim == fixed promotion/remittance
amount; original invoice gross == source invoice amount; shortage/damage units times
exact unit paise == claim amount. Overflow or inconsistency with invoice gross abstains.
Signed, approved, authenticated POD is required for delivery support; missing/unsigned
POD is insufficient. Conflicting WMS/POD quantities or values and multiple shipment
groups abstain; there is no invented multi-shipment aggregation or fractional unit math.
Tax tags are retrievable source material and **always require tax review**, not tax
classification, rate/eligibility adjudication or financial recognition.

Verification inspects all current applicable records within its 200-record budget,
not merely the caller's favorite citation or FTS hit. Multiple opposing facts return
INSUFFICIENT/CONFLICTING_EVIDENCE with individual findings; uniformly contrary facts
return CONTRADICTED. Expired/irrelevant facts return NOT_APPLICABLE. Missing/unverified
facts or any incomplete search return INSUFFICIENT. A completed supported predicate
returns SUPPORTED with SOURCE_FACTS_ONLY purpose, reasons, source IDs, algorithm
evidence-verifier-v1 and input fingerprint. None of these outcomes writes a claim,
hypothesis, approval, balance or journal. Persisted provenance permits reproduction;
reads do not append mutable "approved" findings or audit records.

## Privacy, limits, lifecycle and operations

Tool excerpts reuse the existing fail-closed offset-preserving privacy projection.
PAN/GSTIN/accounts/contact information and unknown unnecessary text are masked; no
raw quote, arbitrary source-system identifier or token mapping is copied into a tool
payload. Essential-identifier conflicts return PRIVACY_REVIEW_REQUIRED and suppress
typed fact disclosure. Reviewer pointers remain local privileged originals. No model
or network call occurs. Production anonymization/terms and model accuracy remain
unverified; schema success does not defeat prompt injection or authenticate source text.

JSON is UTF-8 application/json, <=262144 bytes, depth <=12 and <=2048 nodes; duplicated
keys/nonfinite values/malformed nesting are rejected before model validation. Queries
are <=256 characters/32 words. Errors never echo source values, arbitrary extra field
names, keys or SQL exceptions. Source config is <=32768 characters. FTS excerpts are
<=2000 characters. Per request, at most eight hash-verified financial imports are
parsed/reused (existing CSV bounds remain); overflow fails closed. A request-local
cache retains at most 16 MiB of hash-verified originals across
100 documents; it never survives the operation. Related invoice scope is capped at
1000. Exceeding either budget abstains rather than dropping evidence. Case context holds
at most 200 current external records and 100 distinct external documents. Source
registration may notify at most 200 relevant customer cases, atomically or not at all.
Existing case/document limits remain. No benchmark-scale throughput claim is made.

Additive migration 0008_evidence creates immutable evidence_records/requests/events,
compound tenant/owner FKs, contiguous predecessor protection, audit-projection guards,
scoped indexes and a stored GIN text vector. Same key/body replays one operation;
different keys reuse the same immutable source revision. Conflicting concurrent
successors yield one commit and one conflict. Corrected evidence is a new revision;
no destructive correction, reclassification or original overwrite is permitted.

Registration publishes source-linked events through the existing transactional
outbox. The separate case worker updates relevant case versions, invalidates affected
claim hypotheses/unposted bindings and schedules reevaluation. Relevant external
records/hashes/integrity are part of fresh case and per-claim contexts, including
source-file corruption before delivery. Unknown owners abstain and require the
existing reconciliation/refresh flow. Keys are revalidated on every read; no cached
success survives revocation. Publisher management/PKI, general legal-condition
interpretation, OCR and full Argon compatibility/evaluation remain unverified/future.

Minimal isolated application demonstration (no dataset seeding or paid provider):

```text
uv run --frozen pytest tests/test_evidence.py::test_correct_clause_search_pointer_readonly_and_no_financial_mutation --require-postgres -q
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```
