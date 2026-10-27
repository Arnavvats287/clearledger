# External evaluation authorization amendment

Date:2026-10-27. Applies only to the frozen DocILE and ContractNLI experiment.

The dataset holder/user explicitly confirmed that they reviewed the permissions
and access conditions of their downloaded copies and authorized their evaluation
use, including external API processing **where provider terms permit it**.
Dataset-use/API-processing rights status is therefore **USER-RESOLVED / AUTHORIZED
FOR THIS EVALUATION**. This records user attestation, not a newly obtained publisher
grant, legal opinion, production-data consent or general dataset-processing license.

Raw source documents remain private/local except for the exact authorized provider
requests. No raw source text, evidence quotes, API keys or sensitive model payloads
may be committed to Git or published. This permission does not extend to unrelated
datasets, production records, public document redistribution or the private/sealed
ClearLedger benchmark.

All frozen sample IDs, scorer formulas, normalization/failure rules, source
chronology and leakage controls remain unchanged. Predictions must be sealed before
a separate scorer accesses gold. No prompt tuning or rerunning failed examples to
improve final scores. Original Phase0 JSON/checksum and historical Phase1/1.5 reports
are preserved; the appended transition supersedes only the current rights blocker.

Provider treatment remains independent. Real/public documents must not be sent
through unpaid services when their content is prohibited there. Paid-project
billing, model, price, quota, schema admission and retry/cost controls must be
verified before any real-document call. Billing must not be enabled automatically.
Any synthetic admission calls also count against the authorized token-charge budget.

The five known DocILE input failures remain in the50-document denominator. Per the
new explicit instruction, they receive zero model calls and honest input-failure
dispositions unless an already approved source projection represents them without
changing semantics. This amendment does not repair or weaken the frozen adapter.

## Historical provider-gate disposition — 2026-10-27

An existing local `GEMINI_API_KEY` is configured, but its billing status/project
identity cannot be established from the key's presence. No evaluation-specific key,
project ID, application-default credential reference or `gcloud` command was found
in the scoped local configuration/PATH checks. No key value was printed or recorded.
**Paid billing is UNKNOWN, not asserted to be disabled.** No provider model or
document request was attempted to infer billing from generation success.

The task stops at SectionB as instructed. The minimal evaluation transport,
synthetic admission, smoke/scored runs and inference configuration freeze have
not begun. Dataset permission has been recorded and does not bypass this gate.

**Single setup action:** connect a paid Gemini evaluation project locally. Place
that project's evaluation key in Git-ignored `.env.external-evaluation` as
`CLEARLEDGER_EVAL_GEMINI_API_KEY`, and confirm that the same project's AI Studio
billing page shows Paid with usable credit if prepaid. Do not send the key in chat.
No local file, project, key or billing change has been made on the user's behalf.

Current official references:
[Paid Services terms](https://ai.google.dev/gemini-api/terms) and
[billing/status verification](https://ai.google.dev/gemini-api/docs/billing),
retrieved2026-10-27. These distinguish an active paid project from mere possession
of an API key; no historical Free-tier quota or current paid status was assumed.

## Free-tier operator amendment — 2026-10-28

The operator explicitly authorizes the frozen ContractNLI/DocILE samples to be
processed using the existing Gemini API Free tier and accepts its data-treatment
conditions for this experiment. **Dataset/API-processing rights remain USER-RESOLVED.
Paid tier is not an operator requirement.** Do not enable billing, create/modify
projects, establish AutoPay or rotate a working key. The previous paid-setup
instruction above is historical, not the current requested next action.

Scope remains only these frozen public samples. No production/private/customer/
sealed ClearLedger data, secrets, unrelated documents, raw source publication or
Git-committed evidence quotes are authorized. Original sample IDs, prompts,
schemas, metrics, failure rules, source/gold separation and no-retry policy remain.
This is an additive authorization change, not a claim Free/Paid terms are identical.

### Independent provider-payload restriction

The [current official Unpaid Services terms](https://ai.google.dev/gemini-api/terms),
rechecked2026-10-28, separately state: “Do not submit sensitive, confidential, or
personal information” under Unpaid Services. Acceptance of product-improvement
use/human review does not establish an exception to that content restriction.

Local Phase1.5 screening reports identifying/contact/signatory/payment-context
candidates in frozen inputs. Those are heuristic findings, not proof every match
is personal or confidential. They nevertheless do not establish that all unchanged
payloads meet the provider restriction. No publisher/license issue is reopened;
the remaining issue is **provider-permitted payloads**, not Free tier by itself.

Current status: **STOPPED_AT_PROVIDER_PAYLOAD_TERMS_GATE**, not the historical paid
billing gate. No source was sent, redacted or skipped. Synthetic preflight, model/
quota/tier verification, transport implementation, configuration freeze and scored
runs have not occurred. No metric or provider billing observation is fabricated.

To retain the exact unredacted v1/Free-tier experiment, obtain an applicable provider
clarification permitting these payloads, or establish locally that the complete
unchanged payloads contain no prohibited information. No billing change is requested.
If redaction is needed, it requires a separately approved protocol version; this
task does not silently create one or alter the frozen denominator.
