# Synthetic AI usefulness evaluation — 2026-10-26

The operator's completed 255-stage deterministic baseline is frozen and untouched.
No operator, scorer, sealed split, independent dataset, schedule or answer was read
or changed. This small application-owned evaluation measures existing interfaces;
it is not another benchmark run, representative accuracy study or product milestone.

## Actual end-to-end investigation

Four isolated PostgreSQL cases exercised actual import/document/correlation/evidence
and investigation APIs, existing outbox delivery, the real LangGraph executor and
persisted findings/trace APIs. API calls use FastAPI TestClient; the real worker graph
is executed in-process, not replaced by a stub. Local fixture source signatures are
explicit test trust roots, never production authentication. No finance endpoints
were invoked. Every case retained its exact financial state and required human review.

| Synthetic rebate claim | Retrieved/verified result | Recommendation |
|---|---|---|
| 101 paise, signed promotion says101 | SUPPORTED; NUMERIC_PREDICATE_MET; exact cited pointer | HUMAN_REVIEW |
| Same amount, unsigned promotion | INSUFFICIENT_EVIDENCE; INCOMPLETE_OR_UNVERIFIED_EVIDENCE | HUMAN_REVIEW |
| Promotion absent | INSUFFICIENT_EVIDENCE; MISSING_EVIDENCE | HUMAN_REVIEW |
| Signed promotions disagree:100 versus101 | INSUFFICIENT_EVIDENCE; CONFLICTING_EVIDENCE | HUMAN_REVIEW |

All four runs completed, with three scoped evidence tool calls each; findings were
current and every run recommended AWAITING_REVIEW. The supported example preserved
document/version, raw/canonical hashes and source span. The conflict result retained
both opposing sources. These are useful evidence triage and discrepancy explanations,
expressed as typed reasons, not rich natural-language analyst narratives. Four of
four expected outcomes passed; three of three unsafe/unsupported situations abstained.
This demonstrates the LangGraph workflow with the deterministic Investigator, not
an LLM reasoning improvement. No live or fake Investigator model was used in these
four measurements; separate forged-citation controls use the existing fake provider.

## Eight-document extraction smoke pack and comparison

Definitions/bytes are in `tests/test_ai_usefulness.py::SMOKE` (PDF bytes use the existing
minimal compressed-PDF test helper). All uploads explicitly mark approved synthetic
content and use the actual ingestion, extraction and canonical-text APIs.

| Fixture | Deterministic baseline | Scripted fake-provider control |
|---|---|---|
| Structured JSON; invoice i, damage101 paise | SUCCEEDED, exact reference/amount | Not needed |
| Strict lines; invoice i, damage101 paise | SUCCEEDED, exact reference/amount | Not needed |
| Compressed PDF; invoice i only | SUCCEEDED, reference, no invented claim | Not needed |
| Plain email with Subject and strict body | NEEDS_REVIEW; no extracted fields | Not exercised |
| Prose; Invoice I-1, payment INR9.00, disputed damage INR1.01 | NEEDS_REVIEW | Exact I-1/damage101, still NEEDS_REVIEW |
| Prose; Invoice I-1, damage amount unknown | NEEDS_REVIEW | I-1, damage amount null; NEEDS_REVIEW |
| Conditional rebate INR1.01, explicitly not approved | NEEDS_REVIEW | I-1/rebate101, NEEDS_REVIEW; no authority |
| Fake SYSTEM approval/tool instruction | NEEDS_REVIEW | Malicious approval/tool output rejected, FAILED |

Deterministic reference coverage:3/8 documents, with3/3 emitted references correct.
Known numeric deduction coverage:2/5 documents (email/prose/conditional omitted);
both emitted amounts correct. Including the unknown-amount claim, claim coverage is
2/6. The PDF and injection example have no deduction claim to infer. All five
non-grammar documents abstained; abstention does not count as field extraction.

The scripted positive controls add exact references on3/3 selected prose documents,
two correct101-paise amounts and one correctly preserved null. Across deterministic
and these fake controls, references cover6/8 documents and claims5/6; the email remains
unextracted and injection does not gain authority. These figures measure plumbing
with hand-authored replies, **not AI accuracy or an improvement attributable to Gemini**.
Source/schema/semantic validation passed on all emitted facts; fake prose pointers
also passed the real verify-span API. No invalid emitted citations were observed.
Four separate forged-pointer controls (quote/hash/offset/tenant) were rejected.

**Payment-total extraction is NOT SUPPORTED** by remittance-extraction-1.0. It models
invoice/UTR references and deduction claims, not a payment-total field. INR9.00 in
the prose is not scored as a deduction or a successful payment extraction. Missing
invoice identity, claim legitimacy, source authenticity and authorization cannot be
filled in by the model. Schema success always retains human review/no financial authority.

## Measurements and limitations

- Actual API ingestion + deterministic extraction:495–531 ms/document (eight cases).
- Investigation start + worker graph + findings/run/trace retrieval:2,195–2,525 ms.
- Injected fake extraction:48–54 ms; no network/model latency, not comparable to Gemini.
- External calls:0; paid API spend:0. Provider/model accuracy, real usage, billable cost
  and live latency:NOT EVALUATED. Fake usage counters are scripted, cost estimate null.
- Financial non-mutation:12/12 evaluation cases. No posting, approvals, settlements,
  benchmark attestations or real source authentication were manufactured.
- Targeted evaluation:12 passed in50.02s. Focused existing security regressions:
  11 passed in47.38s (four citation forgeries, five injection/authority attempts,
  privacy/default-off behavior and controlled provider/privacy failures).
- The first evaluation harness attempt had8 failures from using the document detail
  endpoint for canonical pages; corrected to the existing `/documents/{id}/text`
  endpoint. Four investigation cases already passed. No application defect/change
  or relaxed assertion was needed. Final measurements above use the successful run.

Fixture tests are tiny, selected controls, not statistical evidence of generalization.
The privacy vocabulary may remove useful difficult-prose context; live accuracy is
unknown. Current recommendations are typed evidence triage, not adjudication. The
email Subject triggers review by design. Existing parser/security limits were preserved.

## Reproduce and separately authorized live smoke plan

Run `uv run --frozen python scripts/evaluate_ai_usefulness.py` with a local ignored
TEST_DATABASE_URL role capable of creating disposable test databases. The runner
forces paid providers off/clears the child Gemini key, redacts configuration secrets
from captured output and never touches the development schema. Per-case real API
observations are ignored under `local-data/ai-usefulness/`; targeted logs are
`local-data/ai-usefulness-run-final.log` and `local-data/ai-usefulness-security.log`.
No full benchmark, full regression suite, Docker rebuild or restart gate is needed
for these evaluation-only files. The existing application/image is unchanged.

**Live test prepared, NOT authorized or executed.** After separate explicit approval,
use only these eight original synthetic documents in a fresh disposable database;
retain deterministic-first routing and compare against the fixture expectations.
Do not use the scripted replies as live results. Configure key only in ignored local
environment; verify actual configured model availability using the existing provider
preflight, without assuming a model ID exists. Keep investigation external calls off.
Use one sequential caller, LLM_ATTEMPTS=1, both minute request limits=2,
LLM_DAILY_REQUESTS=8, LLM_MAX_INPUT_TOKENS=8192, LLM_MAX_OUTPUT_TOKENS=512,
LLM_DAILY_INPUT_TOKENS=65536, LLM_DAILY_OUTPUT_TOKENS=4096. Existing shared reservations
fail closed. Structured inputs should cause no generation; at most five documents
need semantic extraction. No automatic escalation or retries beyond the single attempt.

Before enabling extraction, obtain current verified model prices and explicit operator
approval of a maximum100-paise estimated spend: conservatively ceiling the full token
reservation at the configured input/output paise-per-million rates, and decline if
it exceeds that cap or rates/model limits are unavailable. This is a proposed test
budget, not an existing global extraction spend-cap feature or a billing guarantee.
No rates, valid model, privacy review or live key were inspected/assumed in this run.
The operator must approve the model/budget and synthetic privacy projection before
enabling external extraction for that isolated session. Restore defaults afterward.
Actual live outputs must undergo existing independent source-span/semantic checks,
record complete usage/estimated cost or explicit unknown, and preserve human review.

Subsequent authorization/preflight: see [LIVE_GEMINI_EVALUATION.md](LIVE_GEMINI_EVALUATION.md).
Live calls were authorized but did not execute: the proposed shared minute/day limits
use HTTP-operation units (three reserved per attempt), not generation-attempt units,
and the full token reservation did not pass the100-paise budget gate. The earlier
proposed configuration is therefore not an executable approved run profile.
