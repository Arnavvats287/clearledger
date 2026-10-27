# Live Gemini extraction evaluation

## Optional Investigator campaign — 2026-10-27 IST

Real extraction success below remains unchanged. The subsequent optional AR
Investigator has NOT passed live acceptance: four conservative transport attempts
fell back; latest model violated three plan criterion literals. Provider-only v2
string-enum encoding is fixed offline, not live reverified. No accepted live AI
planning/synthesis or signed-support/conflict usefulness claimed. New reservations120
paise; cumulative443,57 remain. No output repair, financial mutation or benchmark
changes. Actual attempts, controls, future frontend trace and remaining gap:
[AI_INVESTIGATOR.md](AI_INVESTIGATOR.md).


## Subsequent v5 real AI + automation verification — 2026-10-27 IST

The separately authorized synthetic vertical slice now completed with real Gemini
3.5 extraction and reason_code=null. Same claim flowed automatically through
source-backed correlation review, controller confirmation and refreshed original
LangGraph, ending REQUEST_EVIDENCE/MISSING_SIGNED_POD with no financial mutation.
Two actual generations, first correct extraction stopped by runner's occurrence-count
assumption; separately authorized second completed. New reservations52 paise;
cumulative323,177 remain. This does not replace historical failures/benchmarks or
establish general accuracy. Full actual results, API payloads, costs and controls:
[LIVE_AI_AUTOMATION_SLICE.md](LIVE_AI_AUTOMATION_SLICE.md).


Offline follow-up (2026-10-27): provider contract v5 rejects unlabeled status/category
words as reason codes; explicitly sourced codes survive validation/privacy filtering.
Optional initial deterministic case investigations reuse persisted extraction facts
and the existing outbox/LangGraph. Tests/limits: STATUS.md and INVESTIGATIONS.md.
**No further live calls;229 paise remain.** Historical v4 metrics and its incorrect
reason-code result below are preserved; corrected live-model accuracy is unverified.

## Gemini3.5 alternative — live validated facts, one semantic quality error (2026-10-27)

**Real Gemini3.5 generation works.** The final actual-API run persisted invoice I-1
and a damage claim101 paise with independently verified source spans, human review
required and financial state unchanged. It also misclassified the source word
“disputed” as a reason code: the whole-fixture expectation FAILED. This is a real
partial success, not perfect extraction, general accuracy or production readiness.
No further live calls after the measured result; the earlier3.1 outage remains distinct.

### Preflight and controls

Operator confirmed same existing Free-tier key/project, model-specific15 RPM,
250000 input TPM,500 RPD with displayed usage0 for each. These are dashboard evidence,
not an API-enforced real-time remaining counter. Exact model lookup confirmed
models/gemini-3.5-flash-lite, generateContent,1048576/65536 token limits, served version
3.5-flash-lite-07-2026. No key, project, billing or account upgrade/change.

Official [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
and [standard pricing](https://ai.google.dev/gemini-api/docs/pricing) checked:
USD0.30 input/2.50 output per million including thinking; Free tier listed free.
ECB2026-10-26 INR/USD95.18546657132642116553450125 passed freshness and INR110 buffer.
20% contingency gives3960/33000 paise/million. Reserve13 paise for2048 input/128 output
plain probe;26 for2048/512 remittance. The old17-paise3.1 estimate was not reused.

Real SDK2.33 client resolved canonical Google Developer API endpoint, v1beta,
trust_env=false,30-second timeout, HttpRetryOptions(attempts=1). Single caller;
metadata/count/generation operations paced below15 RPM/250000 TPM; no real transient
retry was needed. All7 generations explicitly reserved/counted. Application attempts
also used the unchanged PostgreSQL three-operation admission and gateway attempts1.
Remaining-RPD CLI bounds490/480/470/460/450 were deliberately conservative deductions
from operator evidence/known calls, not new dashboard readings. Shared outside usage
cannot be enforced by the local runner. No model escalation/fallback or hidden retry.

Plain probe sent only the approved fixed OK request. Subsequent requests used only
original approved PROSE through the unchanged privacy projection. For v3/v4, at most
512 exact Unicode token-boundary hints were computed from **projected text only**;
no private mask map, customer data, database URL, policy or financial tool was sent.
Hints are source positions, not extracted answers/attestations. Original document
bytes and strict host schema/source/amount/containment/tenant checks were unchanged.

### Every new generation attempt

Provider returned a generation response on7/7 attempts; no503/429/400 in this model
campaign. Successful HTTP generation is distinct from application acceptance.

|Attempt|Request|Measured result|Latency seconds|Input/output tokens|Reservation paise|
|---|---|---|---|---|---|
|1|Plain text,128 output cap|Exact OK|1.391038800|13/1|13|
|2|Projected PROSE, no JSON constraint|I-1 and101 paise; fenced JSON, no spans|1.054750000|178/35|26|
|3|Actual API, original v1 prompt|FAILED / SCHEMA_VALIDATION|6.220169300 API|215/149|26|
|4|Actual API, safe schema diagnostics|FAILED; page values below1|3.530060400 API|215/149|26|
|5|Actual API, v2 explicit page numbering|FAILED / SOURCE_VALIDATION / INVALID_SPAN|3.593125800 API|240/294|26|
|6|Actual API, v3 exact position hints|FAILED / SOURCE_VALIDATION / AMOUNT_OUTSIDE_CLAIM|3.731650700 API|699/296|26|
|7|Actual API, v4 complete containment instructions|NEEDS_REVIEW; persisted core facts; reason-code false positive|3.732660400 API|761/316|26|

First two latencies measure provider generation; actual-API latencies include
worker lookup/count/generation/validation overhead. Final internal latency3704ms.
All reported totals reconcile; campaign totals2321 input/1240 output/3561 total tokens.
No separate reasoning count reported. No raw provider error body/message/key/URL was
logged. Actual API outer HTTP200 is an envelope, not automatic acceptance of facts.

The original prompt conflated zero-based offsets with unspecified page numbering;
safe diagnostics established below-minimum page values (not an inferredHTTP400).
Explicit one-based pages fixed that schema failure. Position hints then passed exact
spans; the complete-claim clause requirement fixed the measured containment failure.
Provider contract is now gemini-remittance-shape-v4; versioned cache identity prevents
silent reuse under changed inputs. No model output was repaired or validation relaxed.
The independent actual API rejected all four invalid attempts before accepting facts.

### Final actual application evidence and limitations

The real flow: fresh disposable PostgreSQL/head migration check -> actual customer/
invoice/bank/receipt import setup -> approved immutable PROSE upload -> canonical-text
API -> deterministic extraction abstention -> Gemini isolated worker -> unchanged
strict schema/restore/semantic verification -> extraction-history API/verify-span API.

- Invoice reference I-1, page1/start8/end11, exact quote I-1: correct.
- Damage101 paise, amount quote INR1.01, page1/start38/end46: correct.
- Description page1/start31/end55, exact quote “damage INR 1.01 disputed”;
  exact quote and all actual offsets were verified
  by the application, not invented for this report.
- No invented payer, UTR or extra deduction. The9.00 payment was not a deduction;
  payment-total extraction remains outside the schema.
- **Incorrect optional classification:** reason_code=disputed. The word is in the
  source and its citation is valid, but no explicit code was supplied. No invented
  wording, yet one unsupported semantic classification. No silent dropping/correction.
- Requires human review=true, financial_authority=false, source authenticity UNVERIFIED.
  Source spans verified and facts persisted through the extraction-history API.
  Financial fingerprint unchanged. Every disposable application database cleaned;
  no finance/posting/approval/customer-message endpoint was invoked.

Among the one accepted final result: invoice1/1, amount1/1; all emitted source pointers
validated. Optional reason-code error1. Across five actual API attempts, one accepted
and four safely rejected. Whole-fixture correctness0/5: the accepted result still
fails the no-reason-code expectation. Those selected, adaptively debugged development
calls are **not a benchmark/general accuracy estimate**. No additional fixtures or
sealed evaluation were run. More semantic accuracy work/reproducibility across prose
is needed; the successful core path is now demonstrated with a real model.

New conservative reservations169 paise; previous102 -> **271 cumulative,229 remain**
of500. Usage-based conservative per-call ceilings sum53 paise (not reservations or
an observed bill). Official paid-price equivalent USD0.0037963 for known usage;
Free-tier billing was not enabled and no account invoice was independently inspected.
No zero-bill claim or refund of reservations. Live-call objective stopped with
validated core facts plus the recorded quality error; no further call implied.

### Reproduction and verification

Existing scripts reused, no framework/dependency/frontend/financial-schema change.
Diagnostic commands: scripts/diagnose_gemini.py --authorized-live --stage 1 then --stage 2,
each with --model gemini-3.5-flash-lite --confirmed-rpm 15 --confirmed-tpm 250000
--confirmed-rpd 500. Each actual API command:
scripts/live_gemini_smoke.py --authorized-live --model gemini-3.5-flash-lite
--remaining-budget-paise <reviewed remaining> --confirmed-rpm 15 --confirmed-tpm 250000
--remaining-rpd <conservative reviewed bound>. Executed using .venv/Scripts/python.exe
-X utf8, once per recorded attempt, not automatic retries. Date/auth/quota/budget gates
remain; the local campaign ledger now refuses further calls. Future execution requires
new review, not blind replay of these historical commands or rates.

Ignored records: local-data/gemini35-preflight.json; local-data/gemini35-stage1.log,
gemini35-stage2.log; local-data/gemini-campaign-20261027/alternative-35/ledger.json.
Actual API observations by attempt3–7:
1abcf7d0b17c4c5685123b6f570ca572,1f382c1f8eb5494bbd5ea3337c59def0,
d8dab9a9985d4e1ca713af3949f70b9a,0740d71f33b04550a055f3fc345aa42a,
b0da49f5d8e44a42914d2f9dce3a071c, each under local-data/live-gemini/<id>/observations.json.
Only sanitized validation codes/allowlisted paths captured; untrusted keys/values and
raw Pydantic/provider messages are excluded. Final runner intentionally exits1 because
the whole-fixture expectation failed; persisted NEEDS_REVIEW is not hidden as a pass.

Final targeted mock-HTTP/PostgreSQL verification: **36 passed in31.02s** across
test_gemini_campaign, test_live_gemini_runner, test_gemini_request_contract and
test_gemini_schema; Ruff lint/format passed on7 changed Python files. Log:
local-data/gemini35-verification-final.log. Full command in STATUS.md. These are
offline/code checks, distinct from the7 live requests and failed whole-fixture gate.
Persistent EXTERNAL_AI_ENABLED=false,
EXTRACTION_PROVIDER=disabled and external investigations false; .env/key unchanged.
Frozen benchmark/pilots/hidden ground truth untouched. No full suite or Docker rebuild.

## Expanded campaign — sustained minimal-generation failure, 2026-10-27 (IST)

This supersedes the earlier quota-blocked campaign below. Operator reconfirmed the
same Free-tier project:15 RPM (observed peak1),250000 input TPM (peak163),500 RPD
(displayed peak3). This is explicitly a peak view, **not497 guaranteed remaining**.
Authorization increased to500 paise cumulative and20 NEW generations including
retries. Prior conservative reservations51; each new reservation17. Even all20 would
reserve391 cumulative, below500; billing/account/key/model changes remain prohibited.

Official [pricing](https://ai.google.dev/gemini-api/docs/pricing) rechecked before calls:
standard text USD0.25 input/1.50 output per million including thinking; free-tier
input/output listed free. ECB latest2026-10-26 INR/USD95.18546657132642116553450125
passed the freshness/INR110 buffer gate. Conservative rates3300/19800 paise per
million include20% contingency. Input cap2048/output512 reserves ceil16.896=17 paise.
Same-key lookup confirmed exact gemini-3.1-flash-lite with generateContent and
adequate limits. No model switch, key rotation, billing enablement or project change.

Only the literal `Reply with exactly OK.` and system instruction `Return only the
requested text.` left the machine for generation. No remittance/customer document,
database URL, finance policy, private mapping or tool was sent. The unchanged approved
PROSE projection was independently checked offline but was **not transmitted**, since
stage1 never passed. Client tools=[] and automatic_function_calling disabled. SDK
HttpRetryOptions(attempts=1); one sequential caller; each generation reserved before
network, including transient retries. All model/count/generation operations spaced
by at least5.1 seconds (under12 starts/minute), with extra bounded2/4-second backoff.
Even conservatively charging input for metadata/count operations stays below250000
TPM. Project-wide concurrent use remains outside the local script's control; errors
are authoritative backpressure, not permission to exhaust the Free-tier allowance.

Actual command (once): `.venv/Scripts/python.exe -X utf8 scripts/diagnose_gemini.py
--authorized-live --stage 1`. Lookup and complete-request token count passed (13
tokens). No raw provider error message/body/URL is stored. Results:

| New attempt | Stage | Outcome | Safe phase/category | Provider latency | Reserved |
|---|---|---|---|---|---|
|1|Minimal plain text|HTTP503 / UNAVAILABLE|CONTENT_GENERATION / HTTP_API|7.965648400s|17 paise|
|2|Same, bounded transient retry|HTTP503 / UNAVAILABLE|CONTENT_GENERATION / HTTP_API|1.480382300s|17 paise|
|3|Same, bounded transient retry|HTTP504 / DEADLINE_EXCEEDED|CONTENT_GENERATION / HTTP_API|14.535045100s|17 paise|

**Stopped on sustained provider-path failure; no more live calls.** Generation success
0/3 new attempts. This is reproducible with a13-token prompt without JSON MIME/schema
constraints; it establishes unavailability/timeouts on this key/model path, **not a
proven global Google outage or a specific cause of the old HTTP400**. Exact provider
service/account reason UNKNOWN; error bodies are intentionally excluded. No unchanged
HTTP400 was retried. All three operations returned explicit safe provider errors;
there is no inferred successful output.

Stages2–6 (free-form, JSON MIME, minimal schema, full provider schema, actual-API
persistence) **NOT EXECUTED**, since stage1 does not support advancing. Invoice/claim
accuracy, citations, unsupported fields and human-review persistence NOT EVALUABLE
for this campaign. No extraction fact was created or finance endpoint invoked; no
database was created or modified. Financial controls were untouched, rather than
claiming a fingerprint test for an API path never reached. Live extraction accuracy
remains unestablished. Additional prose fixtures were not attempted.

Provider-reported generation usage and actual estimated spend **UNKNOWN**, not zero;
preflight count13 is not billable usage. New conservative reservations51, cumulative
102 paise, unreserved398 of500. Three of20 new attempts consumed; no authorization
to continue around the sustained-failure stop is implied. Six real generation
attempts have now failed across all historical tasks. Frozen benchmark untouched.

Minimal date-bound diagnostic script reuses installed SDK/privacy/schema/diagnostic
helpers; stages are operator-stepped and prior-stage-gated, not autonomous agents.
Its local single-caller ledger reserves uncertain attempts without refund; rerunning
an established three-failure outage, successful stage or unchanged400 is refused
before key access. The existing actual-API smoke runner remains unchanged and was
not invoked; its old one-attempt budget must not be mistaken for this campaign ledger.
No new application capability, production transport or generalized framework added.

Ignored local records: `local-data/gemini-campaign-20261027/ledger.json`,
`local-data/gemini-campaign-stage1.log`; successful synthetic model text would remain
local, never provider error bodies. Before live:13 offline checks passed in2.36s.
Final focused run:13 passed in2.52s, including repeat-outage/400/success refusal,
SDK retry count1, canary non-leakage, MIME-only then schema-only variation, exact
approved projection and budget arithmetic. First implementation test run caught a
Windows open-lock unlink error (4 failures/9 passes); close-before-unlink fixed it,
then all tests passed **before live calls**. No assertion relaxed. Final log:
`local-data/gemini-campaign-offline-final.log`. Ruff lint/format passed; no full suite,
Docker rebuild or benchmark. Persistent extraction/external-investigation switches
verified disabled; no .env edits. No live-call retry after the three failures.

## Controlled diagnostic campaign — preflight blocked, 2026-10-27 (IST)

New explicit authorization raises the cumulative conservative ceiling to300 paise,
with51 previously reserved. At most10 additional generation attempts, including all
retries, may reserve at most17 each: maximum new170, cumulative221, leaving at least79
if all10 run. **No additional attempt or Gemini metadata/token request was executed.**
The existing51-paise reservation remains unchanged;249 paise are unreserved under
the new ceiling. Authorization alone is not a measurement of current account quota.

Public [official pricing](https://ai.google.dev/gemini-api/docs/pricing) was reviewed:
gemini-3.1-flash-lite standard text USD0.25 input/1.50 output per million, free-tier
input/output shown free. Existing conservative INR110/USD plus20% contingency gives
3300/19800 paise per million and ceil17 for2048 input/512 output tokens, including
thinking in the output cap. A fresh FX check and actual key/model lookup remain
pending; neither pricing availability nor a prior successful lookup proves account
tier or remaining quota. No billing/key/project/model setting was changed.

**Blocking gate:** current project-specific remaining requests are not established.
The earlier operator confirmation15 RPM/250000 input TPM/500 RPD with usage0 predates
subsequent calls and does not establish current shared usage. Google's
[rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits) directs
active-limit checks to AI Studio; limits apply per project and RPD resets at Pacific
midnight. No account-usage dashboard or quota credential is available to this runner.
Requested fresh safe fields only: same-project Free tier, RPM, input TPM, RPD and
remaining daily requests/today's usage. Never requested key or project identifiers.
Until confirmed, the campaign is stopped before provider calls, not a provider failure.

Offline review verified installed SDK2.33's explicit HttpRetryOptions(attempts=1)
and the existing application's LLM_ATTEMPTS=1 prevent hidden transport/gateway retries.
Any resumed matrix needs a single sequential caller, an explicit shared attempt ledger,
pre-call reservation/counting, bounded503/429 backoff and no unchanged400 retry.
No campaign driver or new testing framework was introduced while its prerequisite
is blocked. Matrix stages1–6, model access, live token usage/cost and correctness are
**NOT EXECUTED / NOT EVALUATED**; the previous503 result remains historical.

Approved PROSE privacy projection and unchanged token reservation passed targeted
offline tests together with six runner refusal/sanitized metadata-error cases:
**8 passed in2.21s**. The initial sandbox default-temp run had6 passes/2 temporary-
directory errors; rerunning with a fresh workspace-local basetemp fixed infrastructure
only, without changing assertions. Log: `local-data/gemini-campaign-preflight-checks.log`.
Ruff lint/format on the existing runner, transport worker and diagnostics passed.
Persistent settings verified: extraction_provider=disabled, external_ai_enabled=false,
investigation_external_enabled=false. No financial/benchmark/customer-data operation,
full suite, Docker build or external AI call occurred in this preflight-only task.

## Final authorized compatibility attempt — 2026-10-27 (IST)

**FAILED: CONTENT_GENERATION / HTTP_API / HTTP503 / provider status UNAVAILABLE.**
Exactly one authorized PROSE attempt used gemini-remittance-shape-v1, the simplified
provider-only schema. No automatic retry, second fixture, billing/key/project/model
change, financial action or subsequent debugging call occurred. This is the third
real provider-path attempt overall; no valid live extraction has yet returned.

First inspected installed google-genai2.33.0 errors.APIError: `.code` is numeric HTTP
status, `.status` is a separate structured field, whereas `.message`, `.details`,
`.response` and exception stringification may contain private data. The worker reads
only code/status. Diagnostic sanitization allowlists canonical Google RPC error
statuses (INVALID_ARGUMENT, FAILED_PRECONDITION, etc.) at worker and parent boundaries.
Missing/non-string/unrecognized status becomes UNKNOWN, without guessing from HTTP.
Host metadata-preflight API errors use the same filter. No raw response/body/message,
prompt/key/URL or arbitrary exception name is introduced into diagnostics.
Reference:[Google error conventions](https://google.aip.dev/193).

Offline checks passed before execution:58 targeted diagnostic/strict-validation/
SDK-contract/refusal/privacy/budget tests in35.35s, then6 runner checks in2.06s,
including two new metadata-preflight status cases. **60 distinct checks passed**,
with four repeated runner checks, not64 distinct tests. INVALID_ARGUMENT versus
FAILED_PRECONDITION at HTTP400, other statuses, unknowns and leak canaries verified.
Ruff passed. Existing application source/span/money/authority rules unchanged.

Fresh preflight passed: same key accessible for exact model, current official paid
text prices USD0.25 input/1.50 output per million (free tier retained), latest available
ECB2026-10-26 INR/USD95.18546657132642116553450125 within freshness window. Used
conservative110/USD plus20% contingency;2048/512 token maximum reserves17 paise.
The date-bound pricing review advanced to27 October after checking official pricing;
the gate was not disabled. Exact original PROSE and approved privacy projection
unchanged. Operator-confirmed quotas15 RPM/250000 TPM/500 RPD; conservative remaining
492 accounts for at most eight earlier HTTP operations since the supplied usage
snapshot. No fresh account-dashboard observation is claimed. One metadata GET plus
at most three transport operations remain below those limits; no quota/billing API
or unrelated account action was invoked.

Actual one-time command:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/live_gemini_smoke.py --authorized-live --confirmed-rpm 15 --confirmed-tpm 250000 --remaining-rpd 492
```

| Measurement | Actual result |
|---|---|
| Extraction status / attempts | FAILED /1 |
| Phase / exception category | CONTENT_GENERATION / HTTP_API |
| Provider HTTP / structured status | 503 / UNAVAILABLE |
| Application HTTP | 200 failure-result envelope, not extraction success |
| Invoice I-1 / damage101 paise | No fields returned; acceptance criteria unmet |
| Citation validity / unsupported claims | NOT EVALUABLE; no facts/citations returned |
| Latency | 3.626688700s API wall time;3595ms internal |
| Input/output/total usage; actual estimated spend | UNKNOWN/null; usage_complete=false |
| New conservative reservation consumed | 17 paise, no refund assumed |
| Total reserved / remaining original100-paise budget | 51 /49 paise |
| Facts / human review / authority | Empty result /required /false |
| Financial state / cleanup | Unchanged fingerprint /disposable DB removed |

Model lookup and token-count validation preceded generation successfully on this
run; the exact counted tokens were not retained on failure. The service reported
UNAVAILABLE. Exact underlying service reason is unknown; no provider message/body
was retained. **503 does not prove the earlier400 is fixed or that the simplified
schema was accepted/compiled**. Real model extraction accuracy remains unestablished.
No retry, field adjustment or additional investigation was initiated after failure.

Private logs:`local-data/gemini-final-{offline-checks,runner-checks,live-attempt}.log`.
Actual synthetic observations:
`local-data/live-gemini/b3817f2e2d434381950439d71cd0bc43/observations.json`.
Runner exited1 on failed extraction. Process settings/key/gateway cleared; persistent
external extraction/investigation defaults reverified disabled. Existing API key
preserved, no .env edit/rotation. No full suite, Docker rebuild, sealed evaluation or
255-stage benchmark run. This authorization is consumed; no further call implied.

## Offline wire-compatibility mitigation — no third live attempt

2026-10-26: real SDK serialization/public-spec review found no proven malformed
generation field. Exact HTTP400 root remains unestablished. Provider-only schema
export removes documented decoder-complexity bounds while the strict internal
Pydantic/source/financial checks remain unchanged; live service acceptance is unknown.
See [precise findings and one-call acceptance gate](GEMINI_REQUEST_COMPATIBILITY.md).
All SDK HTTP in new tests is intercepted locally. No model/key lookup, token count,
generation or quota/billing API call occurred. Two real failed attempts remain the
only live results; real LLM accuracy is still not established. Remaining budget66
paise, future attempt cap17; separate authorization required. External AI stays off.

## Exactly one authorized diagnostic retry — 2026-10-26 (IST)

**FAILED at CONTENT_GENERATION; HTTP_API; provider HTTP400. No further attempt.**
This is an actual isolated Gemini SDK-path result, not a mocked diagnostic. The
generation request was rejected; no valid extraction was returned. The exact
rejected field/reason is unknown because response bodies/messages are not retained.
This establishes this retry's failure boundary, not the cause of the original
23.62-second failure, whose historical evidence remains insufficient.

Preflight passed again: exact model metadata accessible to the configured key;
official standard text prices unchanged (USD0.25 input/1.50 output per million,
including thinking); ECB2026-10-26 INR/USD95.18546657132642116553450125. Same
conservative110 conversion plus20% contingency,2048/512 token caps and17-paise
maximum new reservation. Used the user's confirmed15 RPM/250000 input TPM/500 RPD
Free-tier limits, subtracting at most four prior-attempt HTTP operations from the
previously reported0/500 usage:remaining-rpd496. This is a conservative bound from
operator-supplied quotas/known application activity, not a new dashboard observation
or a guarantee against unrelated project traffic. At most four HTTP operations in
this invocation (standalone metadata plus worker get/count/generate) fit the limits.
No billing change. Same existing approved PROSE/privacy projection only; no real data.

Actual command, executed once:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/live_gemini_smoke.py --authorized-live --confirmed-rpm 15 --confirmed-tpm 250000 --remaining-rpd 496
```

| Requested measurement | Actual result |
|---|---|
| Extraction status | FAILED; PROVIDER_FAILED; one attempt |
| Invoice reference / deduction amount | None returned |
| Citation validity / unsupported claims | NOT EVALUABLE; no output, not a zero-hallucination claim |
| Diagnostic phase | CONTENT_GENERATION |
| Exception category / provider HTTP status | HTTP_API /400 |
| Outer application HTTP status | 200 failure-result envelope; not model success |
| End-to-end extraction latency | 3.407971500 seconds |
| Recorded internal latency | 3381 ms |
| Input/output/total usage and actual estimated cost | UNKNOWN/null; usage_complete=false |
| New conservative reservation consumed | 17 paise; no refund assumed |
| Cumulative conservative reservation / remaining budget | 34 /66 paise of original100 |
| Human review / financial authority | Required /false |
| Financial state / database cleanup | Fingerprint unchanged /disposable DB cleaned |

Code order plus the phase diagnostic establishes that worker model lookup and
token-count validation completed before generation was attempted. The precise
token count was not retained on failure; no exact token usage is invented. No
extra call was made to retrieve a provider body, investigate a rejected field,
retry or send another document. No assertion that the schema, quota, authentication
or a particular generation parameter caused HTTP400 is supported by retained data.
Payment totals remain unsupported by the extraction schema. Across the two live
attempts there are0 valid returned extractions; this measures pipeline availability,
not model extraction accuracy.

Private sanitized observation:
`local-data/live-gemini/69d7bf1eb98b489c957b31b4ce34dafc/observations.json`;
log:`local-data/live-gemini-diagnostic-retry.log`. Runner exited1 as expected on
failed extraction. In-memory enablement/key/gateway cleared; persistent extraction
and external-investigation settings rechecked disabled. No financial operations,
billing enablement, external investigations, customer communication, benchmark or
sealed-evaluation changes. This authorization is consumed; no further call implied.

Targeted preflight: six offline launcher/budget/privacy checks passed in1.74s;
Ruff lint/format on runner and diagnostic transport modules passed. No source code
change, full regression, Docker rebuild or additional provider call. Reports/status
only committed; checkpoint in STATUS.md. Earlier history below is preserved.

## Offline failure-diagnostic hardening — 2026-10-26 (IST)

No external calls were made in this follow-up: no metadata, token counting,
generation, pricing/FX HTTP fetch or diagnostic retry. The original failure's
**cause remains UNKNOWN**. Its generic PROVIDER_FAILED and elapsed time cannot
establish which worker phase failed or whether generation was reached. The new
diagnostics cannot retroactively recover missing evidence. No quota, schema,
network, provider or authentication cause is asserted without evidence.

New failure-only `metrics.diagnostic` survives worker → transport → gateway →
persisted extraction API/history. Only allowlisted phase/exception-category codes
and optional safe HTTP integer100–599 can cross the boundary. Model lookup,
token count, generation, response decoding, Pydantic schema validation and source
validation are distinct. Parent worker timeout/process/resource failures also get
distinct codes; a killed worker's last HTTP phase remains unknown. Existing public
error codes/retry behavior remain compatible; the live runner still permits only
one attempt. Unknown SDK messages, arbitrary exception class names, key/prompt/body/
URL canaries, malformed diagnostic payloads and unsafe status types are excluded.

Examples of mocked diagnostic outputs (not live failure evidence):

```json
{"phase":"TOKEN_COUNT","exception_category":"HTTP_API","http_status":400}
{"phase":"CONTENT_GENERATION","exception_category":"TIMEOUT"}
{"phase":"SCHEMA_VALIDATION","exception_category":"VALIDATION"}
{"phase":"WORKER_TIMEOUT","exception_category":"TIMEOUT"}
```

Actual-API fake-provider tests verify immutable failure-history persistence,
idempotent replay, unchanged financial state, human review and no authority. Source
hash/span/semantic verification, privacy projection, worker isolation and monetary
rules remain enforced. No full regression gate or Docker rebuild was run. Native
source is updated; an existing Docker image is not claimed to contain this change.

**Prepared, NOT authorized/executed:** one separately authorized retry of the same
existing PROSE fixture. `live_gemini_smoke.py` now selects only that fixture, reserves
one attempt/three HTTP operations, caps daily input/output at2048/512 and maximum
estimated attempt cost17 paise against the remaining83 paise. It cannot auto-continue
to additional fixtures. The remaining-RPD admission gate requires four operations,
including standalone metadata lookup. No pricing/token limit/budget increase.
Before a future authorization is executed, recheck current official pricing/FX,
model availability, account quota and exact synthetic projection; the runner retains
its same-day pricing-review lock and explicit opt-in requirement. No billing or
financial authority will be enabled. A failed/uncertain retry consumes its full17-
paise reservation; no refund assumption. This follow-up leaves83 paise available.

Targeted tests/Ruff results and local checkpoint are in STATUS.md. External extraction
and investigations were checked disabled; the key was never emitted or committed.

## Actual provider extraction attempt — 2026-10-26 (IST)

**One real-provider extraction attempt failed safely; no additional documents or
retries were sent. No successful live extraction or model-accuracy result is claimed.**
The previous quota blocker was cleared by the user's direct AI Studio confirmation:
Free tier,15 RPM,250000 input TPM,500 RPD, displayed model usage0/500. Billing was
not enabled or modified. This is operator-confirmed quota evidence, not an API quota
query or an independently inspected account dashboard.

Preflight repeated: official standard text pricing remains USD0.25/million input,
USD1.50/million output including thinking; free tier listed as free. ECB daily XML
again returned2026-10-26, INR95.18546657132642116553450125/USD. Conservative110 with
20% contingency gives3300/19800 paise-per-million rates,17 paise per2048/512-token
attempt,85 paise maximum for five. Budget not increased; no assumption of free-tier
billing was needed for admission. Fresh key-authenticated model metadata lookup
succeeded for the exact configured model. Runtime limits:one attempt,one sequential
caller,three internal HTTP operations/minute,15/day; token maxima2048/512 and daily
10240/2560. Including the standalone model lookup, the first attempt's at-most-four
HTTP operations remain below confirmed15 RPM/500 RPD. No further operation was made
after the failed attempt.

`scripts/live_gemini_smoke.py` executed actual document ingestion, canonical-text,
baseline extraction and allow_external extraction APIs via FastAPI TestClient in a
fresh disposable PostgreSQL database upgraded to head. It used the real configured
Gateway/GeminiTransport and isolated google-genai worker, not FakeTransport or
scripted output. Only the existing approved PROSE document was uploaded; its exact
reviewed original/projection are shown below. The transport receives only projected
pages plus the static system/schema, not originals or DB/financial capabilities.
The API's finance identity verifier remained absent; no financial action was invoked.

| Measurement | Observed result |
|---|---|
| Deterministic baseline | NEEDS_REVIEW, SEMANTIC_EXTRACTION_REQUIRED, no fields |
| Real provider path | LLM route, FAILED, fixed code PROVIDER_FAILED |
| HTTP response | 200 extraction-result envelope; not a successful extraction |
| Provider attempts | 1; no retry |
| End-to-end live extraction API latency | 23.620253200 seconds |
| Internal recorded extraction latency | 23592 ms |
| Valid returned extractions | 0/1 attempted |
| Invoice reference / deduction amount | No returned fields; NOT EVALUABLE as model accuracy |
| Citation validity / hallucinations | No returned citations/facts; NOT EVALUABLE, not a zero-error claim |
| Input/output/total token usage | Unknown; usage_complete=false |
| Estimated actual token spend | Unknown/null, not reported as zero |
| Conservative consumed reservation | 17 paise; not refunded on uncertainty |
| Remaining authorized budget | 83 paise, unused because first attempt failed |
| Review / financial authority | requires_human_review=true; financial_authority=false |
| Financial state | Exact before/after fingerprint unchanged |
| Database cleanup / external settings | Disposable database removed; process settings disabled |

**Underlying provider failure remains unknown.** The existing worker collapses API
and other transport exceptions to a fixed safe failure code; it does not retain the
failed get/count/generate phase or HTTP status. A started transport attempt is proven;
whether generateContent was reached/completed cannot be established. No claim of a
successful generation, quota rejection, schema rejection or zero billing is made.
No remote diagnostic retry, provider/security weakening, prompt rewrite or additional
generation was undertaken. Payment-total extraction remains unsupported by the schema.

Actual sanitized observations: ignored
`local-data/live-gemini/fb1116f0ead443c0af4d88729b0d3364/observations.json`;
execution log:`local-data/live-gemini-execution.log`. No key or raw provider reply
was logged; the private artifact deliberately records the approved synthetic projection.
The original runner invocation completed normally after recording the failed extraction;
its final version now returns nonzero on failed/incorrect extraction, preventing a
shell completion code from being mistaken for model success. It was not rerun.

Invocation (requires a fresh explicit authorization and current price review):

```powershell
uv run --frozen python scripts/live_gemini_smoke.py --authorized-live --confirmed-rpm 15 --confirmed-tpm 250000 --remaining-rpd 500
```

Do not rerun automatically. No arguments contain a key or database URL. The runner
requires same-day pricing review, fresh operator quota figures, reads credentials
locally and only creates/drops a generated disposable DB. Its process-local settings
are disabled/cleared in finally; .env remains disabled and its key unchanged. Ordinary
pytest/CI never enables this path. Targeted offline gate/refusal/privacy/cost tests:
12 passed in11.16s; no full regression or independent benchmark. Final formatting/
lint/checkpoint results are recorded in STATUS.md. The frozen255-stage baseline,
trusted operator, sealed evaluation and independent data were not accessed/modified.

## Reduced-budget retry — 2026-10-26 (IST): account-quota gate pending

**One actual Google models.get call succeeded for the configured key. Zero token-
count or generation calls; zero document transmissions; API generation spend0.**
No scripted output is presented as live extraction. Live field accuracy, citations,
hallucination rate, abstention, generation latency and token usage remain NOT EVALUATED.
The original stopped preflight is preserved below as history.

### Pricing, conversion and reduced reservation verified

Rechecked Google's official standard text rates:USD0.25/million input and
USD1.50/million output, including thinking. The certificate-verified
[ECB daily XML](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml) returned
**2026-10-26**, with INR/USD cross-rate **95.18546657132642116553450125** (INR/EUR
divided by USD/EUR, using Decimal). For conservative estimation use INR110/USD and
an additional20% contingency, not a claim about final invoice conversion/tax.

Actual ClearLedger settings for the proposed isolated process:

```dotenv
EXTRACTION_PROVIDER=gemini
EXTERNAL_AI_ENABLED=true
GEMINI_MODEL=gemini-3.1-flash-lite
INVESTIGATION_PROVIDER=deterministic
INVESTIGATION_EXTERNAL_ENABLED=false
PRIVACY_REVIEW_REFERENCE=authorized-synthetic-prose-review-2026-10-26
LLM_ATTEMPTS=1
LLM_REQUESTS_PER_MINUTE=1
LLM_SHARED_REQUESTS_PER_MINUTE=3
LLM_DAILY_REQUESTS=15
LLM_MAX_INPUT_TOKENS=2048
LLM_MAX_OUTPUT_TOKENS=512
LLM_DAILY_INPUT_TOKENS=10240
LLM_DAILY_OUTPUT_TOKENS=2560
LLM_INPUT_PAISE_PER_MILLION_TOKENS=3300
LLM_OUTPUT_PAISE_PER_MILLION_TOKENS=19800
LLM_MAX_COST_PAISE_PER_ATTEMPT=17
```

No GEMINI_ENABLED flag is used. At2048/512 tokens, the USD maximum per attempt is
0.001280. Converted rates, with both buffers, are3300/19800 paise per million.
Ceiling((2048×3300+512×19800)/1,000,000)=**17 paise/attempt**; five attempts reserve
**85 paise**, below100. An uncertain/failed attempt still consumes its full reservation;
no retry or automatic escalation. The input cap includes system/schema payload, as
counted by the existing worker before generation; insufficient room must abstain.
The profile was exercised offline against disposable PostgreSQL, not activated for
live extraction or installed as global development defaults.

This fixes the local reservation mismatch without changing reservation semantics:
three HTTP operations fit the shared cap3;15/day covers at most five complete
attempts. Only one caller, at least61 seconds between attempts, including after
the standalone metadata lookup. The already-completed standalone lookup is an
additional HTTP operation outside those15 reservations and must be included in
account usage checks. Application quotas are company-scoped, not account-wide.

### Exact synthetic-only privacy review completed

The first document is exactly the existing `PROSE` fixture, not regenerated data:

```text
Invoice I-1: payment INR 9.00; damage INR 1.01 disputed, review required.
```

The model-visible projected page is exactly:

```text
Invoice I-1: payment INR 9.00; damage INR 1.01 disputed, ██████ ████████.
```

Reviewed: no real customer/person names, PAN/GSTIN, bank/account details, contacts,
real UTR or confidential data. Only approved fixture reference I-1, explicit INR
amounts, financial vocabulary and masked text survive. Offsets/length are preserved;
the mapping/originals stay local. The existing worker would send JSON
`{"untrusted_pages":[<the projected page above>]}`, the static remittance system
instruction and strict Extraction JSON schema. Tools=[], function calling disabled;
no originals, DB/session, credentials in model content, finance rules or approval
authority. The API key travels only as transport authentication. A model response
would still require independent schema, source/span and semantic validation; no
amount would be interpreted as approval. Payment total remains unsupported by the
schema, and the mask's loss of "review required" is a measured projection limitation.
The system instruction still requires explicit uncertainty and no financial authority.

Google's pricing page discloses different free/paid data-use terms; no account tier
or confidentiality assurance is assumed. The user explicitly approved sending only
these synthetic fixtures. This narrow review does not authorize any real documents.

### Actual provider model availability verified, quotas not verified

Official google-genai SDK, explicit key, vertexai=false, trust_env=false,10s timeout,
one HTTP attempt, logging disabled: `models.get("gemini-3.1-flash-lite")` returned
`models/gemini-3.1-flash-lite`, generateContent support, input limit1048576 and output
limit65536. No generation was performed as an availability probe. Key never printed,
logged or committed. Private sanitized metadata/FX log:
`local-data/live-unblock-preflight.log`.

[Google's quota documentation](https://ai.google.dev/gemini-api/docs/rate-limits)
states quotas vary by project/model/tier and active limits are shown in AI Studio;
RPD resets at midnight Pacific, unlike ClearLedger's UTC-day reservation. Model
metadata does not expose those active limits or remaining allowance. The available
AI Studio browser session redirected to sign-in; no account login, credential entry
or quota change was attempted. A request for safe RPM/TPM/RPD and remaining allowance
was issued to the user. **No generation until those figures are provided/verified**;
a successful metadata GET does not establish generation quota or billing entitlement.

Eight targeted offline tests passed in12.57s (new reservation/privacy assertions plus
existing fail-closed tests); Ruff lint/format passed. Normal TLS verification remained
enabled: an initial urllib public-FX lookup failed its certificate chain, while the
existing transport-style httpx trust_env=false path succeeded with normal verification.
An initial ad-hoc command quoting error was corrected locally, without any API call.
No persistent application code, financial state, independent benchmark or sealed
result changed. Generated offline test DBs were disposable; no live-extraction DB
was provisioned because the account quota gate is still pending. Local external-AI
and extraction enablement remained disabled throughout and were reverified disabled.
Only the metadata-only helper used the private key. No full suite/benchmark run.

## Original authorized preflight — historical result

Date:2026-10-26 (IST). **No Gemini API calls were made**, including model lookup,
token counting or generation. API spend:0 paise. No live extraction, token usage,
latency, citation accuracy or model-quality result is available. Previous scripted
controls remain offline results, not live Gemini measurements.

## Verified configuration and model documentation

A nonempty local GEMINI_API_KEY is present; its validity was not tested and its
value was never emitted. Existing ClearLedger configuration accepts:

```dotenv
EXTRACTION_PROVIDER=gemini
EXTERNAL_AI_ENABLED=true
GEMINI_MODEL=gemini-3.1-flash-lite
INVESTIGATION_EXTERNAL_ENABLED=false
```

`EXTRACTION_PROVIDER` accepts only disabled/gemini/fake. `GEMINI_ENABLED` is not a
ClearLedger setting: extra .env entries are ignored and it cannot enable Gemini.
Explicit synthetic upload approval, request allow_external, a nonempty
PRIVACY_REVIEW_REFERENCE and all provider/privacy/budget gates are also required.
The inspected local configuration lacked that review reference and still used
two attempts,10 process requests/minute and4096 maximum output tokens. These are
not the requested single-attempt/two-per-minute/512-output smoke limits. No process
using that configuration was started for the experiment.

Google's [official model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite.md)
documents the exact stable ID, structured output and text support. **Availability
for this key/account via Google's API is NOT VERIFIED**: preflight configuration
and budget gates failed, so the API was not contacted. No model substitution occurred.

## Budget gate — not passed

Google's [current official standard pricing](https://ai.google.dev/gemini-api/docs/pricing)
lists text input at USD0.25/million tokens and output, including thinking, at
USD1.50/million. No free-tier entitlement, caching discount, batch/flex pricing,
currency conversion or zero billing was assumed.

Exact Decimal reservation arithmetic at8192 input/512 output tokens:

| Maximum generation attempts | Input/output reservation | USD cost bound |
|---|---|---|
| 1 | 8192 /512 | 0.002816 |
| 5 semantic documents | 40960 /2560 | 0.014080 |
| 8 permitted attempts | 65536 /4096 | 0.022528 |

Five maximum reservations fit INR1 only at USD/INR no greater than
71.022727… before fees/taxes. A current billing conversion was not established;
therefore the100-paise gate cannot be certified. For context only, the historical
2026-10-01 INR96.2856/USD rate visible on [FBIL](https://www.fbil.org.in/) produces
136 paise for five and217 paise for eight, rounded upward. This historical figure
is **not** a current billing quote or an authorized conversion rate. No request was
made on the assumption that actual short prompts or free-tier access would cost less.

## Proven rate/quota incompatibility

The existing `provider_budget.reserve` reserves **three HTTP operations per attempt**:
model get, count_tokens and generate_content. The requested shared minute cap2
therefore raises PROVIDER_SHARED_RATE_LIMIT before transport. A daily cap8 admits
only two complete attempts (six operations); the third would exceed it. Gateway's
process requests/minute counts generation attempts, a different unit from the
PostgreSQL shared HTTP-operation reservation. These limits were not raised, bypassed
or redefined. Existing cost/unknown-price gates also remained fail closed.

Required before retry: reconcile these distinct quota units with the authorized
limits; a bounded per-HTTP-call pacing design or explicit revised limits would need
separate work/authorization. Tighten the input reservation/number of live calls as
necessary, obtain a verified billing conversion and prove the entire estimate fits
100 paise. Do not silently raise the budget or assume low actual token counts.
Supply the explicit synthetic privacy-review reference and the requested single-
attempt/output settings in an isolated test process, not a globally enabled server.
Only after these gates pass should the exact model be checked through models.get.

## Safety, verification and state

The approved eight fixtures remain unchanged in `tests/test_ai_usefulness.py`.
The existing real transport receives only privacy-projected canonical text, no
original bytes, token mapping, database handles or tools. A fresh live database was
not provisioned because admission failed before execution; offline proof tests used
generated disposable PostgreSQL databases only. No synthetic prompts were sent.
Financial actions and Gemini investigations were never enabled or invoked. Frozen
255-stage results, trusted operator, sealed split and all independent data untouched.

Ignored local .env was returned to EXTERNAL_AI_ENABLED=false,
EXTRACTION_PROVIDER=disabled, INVESTIGATION_EXTERNAL_ENABLED=false, and its unused
GEMINI_ENABLED flag=false. Key/model preserved; no credentials committed. No
generation settings were enabled by this task. Other local settings were preserved.

Targeted verification and checkpoint results are recorded in STATUS.md. No full
suite, benchmark, application-domain change or paid request was undertaken. Actual
successful live examples/failures remain NOT EVALUATED because the fail-closed
preflight stopped as requested.
