# Authorized Gemini extraction smoke — preflight stopped

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
