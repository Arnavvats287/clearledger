# Live Gemini extraction evaluation

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
