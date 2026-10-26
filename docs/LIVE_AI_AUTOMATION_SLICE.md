# Live synthetic extraction and automated investigation — 2026-10-27 IST

**Complete vertical slice passed on the separately authorized second attempt.**
Actual Gemini3.5 Flash-Lite extraction, actual FastAPI application routes, PostgreSQL,
transactional outbox, controller review and existing deterministic LangGraph ran
together. No provider output was repaired. This is a tiny synthetic development
demonstration, not benchmark accuracy, a production identity or payment authorization.
API requests use the real FastAPI ASGI application through TestClient, real PostgreSQL
and outbox drain, and the real isolated Gemini transport process. This does not
exercise a separately deployed HTTP server, browser or frontend.

## Input, trust and preflight

Original approved PROSE is unchanged, with existing minimal source-contract fields
appended before immutable upload:

```text
Invoice I-1: payment INR 9.00; damage INR 1.01 disputed, review required.
CUSTOMER: c
INVOICE: I-1
UTR: t
AMOUNT: 101 paise
```

The original prose alone cannot meet signed correlation's explicit CUSTOMER/INVOICE/
UTR/AMOUNT source-span requirements. These appended synthetic fields are an explicit
fixture composition, not model-discovered authority or a change to the original fixture.
Invoice open1001 paise and receipt available900 paise were imported via CSV1.0.
The101-paise claim remains unresolved; matching identity uses the existing synthetic
verified payer-alias/import contract, not the model. Remittance ownership/UTR proof
uses the existing independent **test-only** HMAC signing root. Controller's trusted
identity port is the existing isolated fixture, restricted to REVIEW_READ/WORK/CONTROL;
it has no finance permissions. This does not establish real source authentication.

Only privacy-projected synthetic text, schema/system extraction instructions and
projected token-boundary hints leave the machine. Customer c and review required
are masked; invoice, UTR and amounts retained. No originals, mask map, DB URL,
signing key, finance policy, tools or customer data enter the extraction worker.
No investigation model calls, customer messages or financial commands.

Current [official pricing](https://ai.google.dev/gemini-api/docs/pricing) checked:
standard input USD0.30/output2.50 per million including thinking, Free tier available.
[ECB](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml)2026-10-26
INR/USD95.18546657132642116553450125 passed freshness; conservative110
plus20% gives3960/33000 paise per million. Each2048-input/512-output reservation
rounds up to26 paise. Exact-key model lookup and generateContent support passed;
served version3.5-flash-lite-07-2026. Existing operator-confirmed15 RPM/250000 TPM/
500 RPD reused; remaining CLI440 then436 conservatively accounts for known use,
not a fresh dashboard counter. Outside account usage cannot be enforced locally.
One sequential caller, no SDK/application/manual provider retry. Four HTTP operations
per run including separate preflight lookup; application reserves its three operations.
No billing/project/key change. Both runs used fresh generated disposable databases;
initialize upgraded head0012_correlation and Alembic checked metadata. Shared DB untouched.

## Actual attempts, including the runner failure

|Attempt|Provider/application result|API latency|Input/output tokens|Estimated cost|Reservation|
|---|---|---|---|---|---|
|1|SUCCEEDED, correct fields and spans; runner stopped on two valid I-1 occurrences|3.5647484s|1045/462|20 paise|26 paise|
|2, separately authorized|SUCCEEDED; full source-backed review/investigation slice passed|3.4807519s|1045/317|15 paise|26 paise|

Attempt1's exact-list expectation incorrectly required one invoice occurrence even
though source contains two. Internal schema/source validation accepted both valid
citations. Runner stopped before draining automation and cleaned its disposable DB;
this attempt is not reported as end-to-end success. The narrowly fixed runner compares
the identifier set for this slice, retains both occurrences, independently validates
every span and never edits the response. Offline rehearsal covers both forms.
User explicitly authorized attempt2 rather than treating this as a transient retry.

Successful live extraction: I-1 page1[95,98), UTR t[104,105), damage101 paise with
INR1.01[38,46), reason_code=null; description[31,56) is `damage INR 1.01 disputed,`.
All exact spans verified by actual verify-span API and
persisted in extraction history. No unsupported extra claims, payer or code. Payment
total is not an extracted schema field and is not claimed as model accuracy here.
uncertainty=none does not override requires_human_review=true or UNVERIFIED source
authenticity. Internal latency3452ms, full extraction API3.4807519s. Total provider
tokens1362; reasoning/cached tokens UNKNOWN. No whole-workflow latency measured.

New reservations52 paise; prior271 -> **323 cumulative,177 paise remain** of500.
Usage-based conservative ceilings20+15=35 paise, not an observed bill/refund of
reservations. No more generation attempts. Historical benchmark results unchanged.

## Persisted API journey and frontend representation

All IDs/hashes below are actual synthetic-run observations. Database was cleaned
after assertions; retained detailed observations are ignored local files.

1. POST `/imports/customers`, `/imports/invoices`, `/imports/payer-aliases`,
   `/imports/bank-transactions` with existing CSV1.0 headers; creates one invoice and
   one bank-backed receipt. No manually created claim or matching proposal.
2. POST `/documents` immutable upload. POST `/documents/{id}/extract`:
   `{"expected_document_version":1}` abstains REVIEW/SEMANTIC_EXTRACTION_REQUIRED.
   Same endpoint with `{"expected_document_version":1,"allow_external":true}` returns
   LLM/SUCCEEDED, model gemini-3.5-flash-lite and strict validated facts.
3. Worker drains actual outbox with both automatic flags true **only in Settings**.
   It creates one101-paise damage claim, its extraction provenance, first investigation
   and a PENDING task with reason MISSING_AUTHENTICATED_CORRELATION_EVIDENCE and action
   REGISTER_AUTHENTICATED_REMITTANCE_WITH_UTR. No receipt/invoice linked yet.
4. POST `/evidence/records` with evidence-1.0 signed manifest: current document/raw/
   canonical hashes, exact CUSTOMER c/INVOICE I-1/AMOUNT101-paise source spans, UTR t
   in signed excerpt, fixed synthetic chronology/owner and test source signature.
   Signature is produced independently from known source facts, not model output.
   Worker automatically creates a fresh task READY_FOR_REVIEW with one candidate;
   frontend GET `/review/cases/{id}/correlation-tasks` shows receipt/invoice versions,
   source record IDs and CONFIRM_OR_REJECT_VERIFIED_ASSOCIATION.
5. POST `/review/correlation-tasks/{task_id}/decision`, real controller review API,
   Idempotency-Key and current server-provided basis:

```json
{
  "expected_case_version": 11,
  "expected_context_sha256": "61553e2dec791efcb5b6a2ff8f057b167661904fd28dc10ce823c9349163eeb0",
  "expected_task_sha256": "cf4f5b4d6310ea042681129fb9245ef6cafb484e37a8f0c956f168a4068a77be",
  "decision": "CONFIRM"
}
```

6. Decision history API returns one immutable CONFIRM with actor provenance and
   financial_authority=false. Existing DocumentAssociation becomes LINKED/current.
   Document case635b0717-ec78-404c-895a-8f2c53748d2b merges into receipt's canonical
   case868faef3-6408-4576-8ee4-919cb5c4b61b. This is the existing canonicalization
   contract, not a new duplicate case/claim. Requested old ID resolves to canonical.
7. Worker automatically reevaluates/refreshes; current investigation COMPLETED,
   deterministic provider,4 read-only tool calls,10 persisted trace steps. Its5
   provider_attempts are deterministic LangGraph decisions, **zero external calls**.
   GET `/investigations/{run_id}/findings` yields current damage
   INSUFFICIENT_EVIDENCE/MISSING_EVIDENCE, source-verifier MISSING_SIGNED_POD,
   NO_BACKED_CONCLUSION, next_action REQUEST_EVIDENCE. Recommendation AWAITING_REVIEW.
   Citation points to the authenticated remittance original/canonical hashes and
   page1[0,123). Remittance proves asserted source facts/correlation, not delivery damage.
   Frontend should request signed delivery/POD evidence, not offer automatic write-off.

|Entity|Same synthetic ID retained|
|---|---|
|Invoice I-1|3488550d-7583-43ac-83cc-c668dbed3f6f|
|Receipt|8ee50d6f-b427-4ba2-84fa-6ed922461a1d|
|Document|e7624922-84a8-4f51-bc03-4488f8a194e8|
|Live extraction|308332de-f134-4753-976c-e3eda7649c98|
|Claim|b2af8a43-e765-42ee-b577-36e5f1a062da|
|Canonical case after merge|868faef3-6408-4576-8ee4-919cb5c4b61b|
|Refreshed investigation|bbb0149c-2e82-4306-b483-a65a0bd11861|

GET existing case/claim/version/event/work, document extraction/association,
investigation findings/trace and new review task/decision endpoints for the workbench.
Final case AWAITING_REVIEW, requires_human_review=true, financial_authority=false,
verified_settled_paise=0. Fingerprint of all five imported financial tables unchanged;
invoice open1001/receipt unapplied900. Allocation, noncash settlement, journal/line,
account balance and financial approval counts all0. Re-draining emits no new work
or investigation. Existing immutable original claim/history retained.

## Reproduction and focused verification

Existing smoke runner extended with `--correlation-slice`; no production code,
architecture, schema or dependency change. Application-owned helper only composes
existing fixtures/API calls and checks expected results. A **new live authorization,
current quota/pricing/privacy and budget review** is required before rerunning:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/live_gemini_smoke.py --authorized-live `
  --model gemini-3.5-flash-lite --remaining-budget-paise <reviewed-budget> `
  --confirmed-rpm 15 --confirmed-tpm 250000 --remaining-rpd <reviewed-allowance> `
  --correlation-slice
```

Offline targeted31 tests passed57.08s across test_live_correlation_slice,
test_live_gemini_runner, test_reason_code_semantics and test_gemini_request_contract.
Initial rehearsal fixture used a callback instead of the existing fake transport's
list interface; fixed test setup, never provider output. Final after-live checks are
recorded in STATUS.md. Ruff lint/format PASS, mypy22 files PASS. No full regression,
Docker rebuild, independent benchmark or restart checks. Cleanup disabled external
AI, extraction provider, investigation external and both automation settings; key
removed from in-memory settings, persistent .env untouched/defaults disabled.

Ignored logs: local-data/live-correlation-slice.log and authorized-rerun.log;
observations under local-data/live-gemini/5e14569a0fe244dab167f187b1302740 and
bbbbb81b571541cd802ffd356108b6b5. Production identity/key custody and real-customer
validation remain unresolved; one synthetic success establishes no general accuracy.
