# Live AI and exception automation acceptance — 2026-10-27

**Bounded synthetic functional acceptance passed after three recorded failures.**
This is actual Gemini 3.5 Flash-Lite, FastAPI routes, PostgreSQL and the existing
LangGraph executor, not scripted model success or benchmark accuracy. Tests invoke
the real ASGI application in-process; the provider uses its isolated SDK worker.
No production identity, source authenticity or financial approval is established
by application-owned test identities/signing keys. The frozen 255-stage benchmark,
independent operator, datasets and sealed split were not accessed or changed.

## Live matrix

| Capability | Actual result |
|---|---|
| Composite approved remittance, three runs | I-1, damage101 paise, reason_code=null; exact source spans, persisted extraction; 3/3 passed |
| Ordinary approved prose | I-1, damage101, no invented reason code; 1/1 passed |
| Missing amount | First returned no claim and NEEDS_REVIEW: safe abstention but failed completeness. After prompt clarification: damage with null amount/span, I-1; passed |
| Conditional rebate | I-1, rebate101, no reason code; human review, no approval; passed |
| Instruction-like source | I-1, no deduction/authority; passed. Privacy projection masks instruction words; this is not an unmasked live injection test |
| Typed AI planning | 3/3 new plans accepted, damage101, WMS/POD, allowed tools and exact test criteria; no fallback |
| Missing WMS/signed POD synthesis | 3/3 accepted: INSUFFICIENT_EVIDENCE / REQUEST_EVIDENCE, authenticated remittance citation only |
| Signed WMS/POD synthesis | First omitted required contextual citation and was rejected. Second failed decoding. Third accepted: SUPPORTED / HUMAN_REVIEW; all3 verified record IDs |
| Conflicting deliveries | Accepted: CONFLICTING_EVIDENCE / ESCALATE_CONFLICT; four verified record IDs and differing numeric observations |
| Automatic claim/task, source correlation, controller CONFIRM, merge | Passed in each of three full-workflow runs; same invoice/receipt/document/claim retained; immutable decision and automatic deterministic investigation refresh |
| Missing-proof review | CONFIRM denied409 AUTHORITATIVE_CORRELATION_REQUIRED; controller REJECT and same-key replay passed |
| Replay | Same extraction ID/no additional provider admission; same confirmation/rejection ID; empty outbox drain and no extra investigation on unchanged replay |

Across the campaign: **8 extraction generations, 7 met all fixture expectations**
(the other safely omitted an unknown-amount claim); **3/3 AI plans accepted**;
**5/7 synthesis generations accepted, 2 safe fallbacks**. The latest same-case
missing/support/conflict sequence passed3/3 without fallback. Seven successful
extractions verified24 pointers through the span API; accepted investigation
findings contain10 citation occurrences, independently verified before model use.
No invented reference, amount or reason code was observed in accepted outputs.
The undecodable response's facts/citations are UNKNOWN, not counted as correct.
These tiny, repeated fixtures do not establish statistical reliability or real-world
accuracy. Failed outputs were never patched into successful ones.

All accepted outputs still require human review and financial_authority=false.
The canonical case remains AWAITING_REVIEW, with claim101, invoice open1001 and
receipt unapplied900 paise. No allocation, noncash settlement, journal/line, account
balance record or finance approval was created. Every recorded financial snapshot
comparison passed. Earlier stopped runs lack a final aggregate fingerprint after
the last failure; per-investigation/automation safety checks passed. The harness now
also measures non-mutation in finally on early abstention (offline regression).

## Narrow repairs and failures retained

1. Offline rehearsal stopped a deterministic refresh at TOKEN_LIMIT: the demo's
   run allowance covered only two external phases, but deterministic tool decisions
   also consume run token accounting. Run bounds now32768/8192; per-call limits and
   spend gates remain binding. No scheduling/application defect was found.
2. Supported synthesis omitted a real remittance pointer while citing valid WMS/POD.
   The existing strict validator requires all verified support-context IDs. The
   worker prompt now states this explicitly; the validator was not changed.
3. Subsequent support response failed RESPONSE_DECODING / DECODE at496 output tokens.
   No raw body was retained, so its exact malformed content/cause is unknown. The
   successful complete support response used578 tokens, exceeding the original512
   cap. Experiment bounds were rebalanced to2048 input/768 output,34-paise reservation.
4. Missing-amount source explicitly said damage, but the model omitted the claim.
   Prompt now requires retaining explicit categories with null amount/span.
   Provider identity v6 invalidates v5 semantic cache reuse; strict internal schemas,
   source validation, financial rules and CSV1.0 remain unchanged.

No transient429/503/504 occurred, and no automatic/manual transient retry was used.
Continuation after fixes used fresh disposable databases and the same cumulative
ledger. Full-workflow repetition is counted, not hidden. The final continuation ran
only three outstanding variations, avoiding more extraction/investigation repetition.

## Latency, usage and reservations

| Latest successful scenario | End-to-end seconds, excluding deliberate inter-case pacing | Provider transport milliseconds |
|---|---:|---:|
| Composite extraction | 4.638 | 3878 |
| Missing evidence investigation | 10.613 | 3937 plan +4171 synthesis |
| Signed support, accepted plan reused | 11.219 | 4203 synthesis |
| Conflict, accepted plan reused | 12.594 | 4983 synthesis |
| Ordinary prose | 5.221 | 4632 |
| Missing amount after clarification | 11.627 | 10889 |
| Conditional rebate | 3.646 | 3021 |
| Instruction-like source | 3.739 | 3154 |

Investigation end-to-end includes source registration/automatic deterministic refresh
where applicable. Provider transport includes worker startup, model lookup, token
count and generation; generation-only latency is UNKNOWN. Across18 generations:
min3021 / median4155 / mean4545.39 / max10889 ms. Latest primary extraction-through-
three-evidence-states elapsed167.098s including122s deliberate pacing and audit/replay
checks. No population/performance SLA is inferred from this sample.

**18/20 generation attempts,580/600 paise reserved;20 paise unused. STOPPED.**
First8 reservations30 paise, next10 reservations34 paise. All18 returned complete
usage:16707 input,5212 output tokens; sum of per-call ceiling cost estimates247 paise.
This is conservative paid-price-equivalent accounting, not a billing statement.
Free-tier status/quota was operator-confirmed; no billing/project/key change occurred.

Official standard rates rechecked: USD0.30 input /2.50 output per million, including
thinking ([Google pricing](https://ai.google.dev/gemini-api/docs/pricing)). ECB feed
dated2026-10-26 yielded INR95.1854665713/USD. Reservations use INR110 plus20%:
3960/33000 paise per million. ceil((2048×3960+768×33000)/1e6)=34 paise.
Configured model/key availability was checked before every run; reported model
version3.5-flash-lite-07-2026. Latest operator quota15RPM/250000 inputTPM/500RPD,
displayed12/500 is not an API-verified remaining counter. CLI20RPD is the campaign's
conservative generation allowance, not a claim about exact account remainder.
One caller, at most9 shared HTTP reservations/minute, SDK/phase attempts1; all
generation attempts count in the persistent local ledger before transport.

Source material is only the approved synthetic clauses and existing test manifests.
Privacy projection sends no keys, names, bank credentials or originals. Investigator
receives scoped IDs, claim/category/paise and verified numeric summaries, no source
instructions, SQL/network/write tools or authority. Token maps stay local.

Avoidable overhead: per-call worker/model lookup/token-count overhead and repeated
campaign setup, not an invitation to cache changing evidence/conclusions. Only the
validated source-free assertion plan is reused. Fresh evidence always triggers
fresh verification/synthesis. Automatic refresh remains deterministic; Gemini runs
require explicit allow_external=true and both external controls.

## Reproduction and verification

Offline, with ignored TEST_DATABASE_URL pointing to disposable-capable PostgreSQL:

```powershell
uv run --frozen python -m pytest tests/test_live_acceptance.py tests/test_ai_investigator.py tests/test_ai_investigator_worker.py tests/test_live_gemini_runner.py tests/test_live_correlation_slice.py tests/test_correlation_workflow.py tests/test_gemini_schema.py tests/test_gemini_campaign.py --require-postgres -q
```

All75 distinct focused cases passed across targeted runs, not one combined/full-suite
execution. Logs: acceptance-offline-final3(32), acceptance-correlation-regressions(18),
acceptance-rebalanced-offline(9), acceptance-resume-ledger-offline(1),
acceptance-variations-offline(19), acceptance-failure-nonmutation(1), final budget
metadata(10), plus citation preflight(5); counts overlap. The initial test path was
renamed test_live_acceptance.
An earlier refresh assertion and missing-file command failed and were corrected;
neither was counted as a passing check. A final metadata test initially had four
sandbox temp-directory setup errors; rerunning with workspace --basetemp passed10/10.
Ruff check/format and mypy23 modules passed.
No full regression/benchmark/restart run: only prompt/cache identity/harness changed;
no new infrastructure, dependency, schema migration or financial logic change.

Actual dated live commands used:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/live_gemini_smoke.py --authorized-live --model gemini-3.5-flash-lite --remaining-budget-paise 600 --confirmed-rpm 15 --confirmed-tpm 250000 --remaining-rpd 20 --acceptance-campaign
# Final continuation added: --acceptance-variations
```

These are recorded executions, **not permission to repeat**. The campaign ledger is
closed at580 paise; do not delete/reset it. New live work needs fresh authorization,
pricing/quota/privacy review. All databases were fresh, migrated through existing
head0012, then cleaned; development data and configuration were not migrated/reset.
Two rebalanced historical reports contain maximum_reserved_paise=680 (20×34 before
applying the cumulative cap); this display-only arithmetic was corrected to600 and
tested offline. The admission ledger enforced600 throughout. Those original reports
were preserved; no excess reservation or generation occurred.

Ignored raw observations, exact synthetic outputs, IDs, traces and metrics:

- local-data/live-gemini/d77d524bf0ca4e919abc21f7e3680314/observations.json
- local-data/live-gemini/31da685db2964acfa70286b8b8e34cc8/observations.json
- local-data/live-gemini/42b3d5d687c14cbc99e6c1250bd0f8b6/observations.json
- local-data/live-gemini/0956109dfb644a36839e600413a93155/observations.json
- local-data/live-acceptance-v2-20261027-budget.json; live-acceptance*.log

## Product handoff and limits

Backend feature expansion is frozen. Next target is the frontend case workbench:
show one canonical case, financial snapshot, linked document/claim, source proof,
correlation-review controls and an inspectable AI/deterministic trace.

Use existing document upload/extract/text/verify-span/extractions APIs; GET
/cases, /cases/{id}, /cases/{id}/claims; GET /review/cases/{id}/correlation-tasks;
POST /review/correlation-tasks/{id}/decision (current case version/context/task hash,
CONFIRM or REJECT, Idempotency-Key); GET its /decisions. Investigations use POST
/cases/{id}/investigations and GET /investigations/{id}, /findings, /trace. Display
plan/tool selection, evidence verification, synthesis, policy, fallback/cached flags,
cost/latency, stale status and required next action separately.

No frontend yet. Show legacy conflicting finding INSUFFICIENT_EVIDENCE alongside
typed CONFLICTING_EVIDENCE/ESCALATE_CONFLICT; never label either a financial approval.
Production identity/source custody, unmasked live adversarial evaluation,
real-customer/held-out accuracy, benchmark matching usefulness and external corpus
evaluation remain unresolved. Constrained rationales are structured review summaries,
not general autonomous AR reasoning. All external-AI/investigation/automation flags
and extraction provider were verified disabled afterward. No further live calls.
