# Final accuracy diagnostics — development only

2026-11-06. Authorized scope: architecture correction and TRAIN/DEV diagnostics.
No new held-out selection/inference, private AR benchmark, RecBench, UI or deployment.
Historical Phase2/Phase3 predictions, scorers, plans and scores remain immutable.

## Current architecture and observed failure decomposition

Before code changes, original Phase3 code/configuration and both prediction/score
seals verified unchanged. A synthetic17-hypothesis response succeeds with17 valid
items; replacing only H07's span with an unknown ID raises
`UNKNOWN_OR_UNOFFERED_SPAN` for the complete response. `Plan.model_validate` /
`Decisions.model_validate` and `validate_choices` process the response as a unit.
`external_gemini_worker.Worker.attempt` catches the validation error and sets the
entire typed result to None. The Phase3 worker then emits `answers=[]`; the existing
scorer counts every missing hypothesis as abstention. This directly confirms the
11 rejected syntheses ×17 hypotheses =187 abstention cascade, not merely arithmetic.

Phase3 legal baseline:408 hypotheses,37.50% accuracy,0.3454 macro-F1,221 answers,
187 abstentions;12 rejected plans/11 rejected syntheses,23 validation failures.
45/553 declared references violated per-hypothesis membership. Rejection reasons
overlap:70 lexical relevance,5 explicit-conflict,12 plan/relation inconsistencies.
Unsupported assertions3/38 (7.89%); published quotes124/124 source-valid. These
published-valid counts do not demonstrate reliable selection or complete reasoning.
Failed typed responses were discarded; their historical metadata cannot distinguish
globally fabricated IDs from real IDs offered elsewhere. No final gold or discarded
outputs are reconstructed or used for tuning here.

Phase3 invoice baseline:P/R/F1=0.8222/0.6981/0.7551;42/45 localized. Whole-source
failures0, input-cap failures4/100, partial/fallback provenance12, three candidate
searches incomplete at64. Candidate-first occurrence identity is retained.

## Authorized correction boundaries

Shared canonical source provenance remains the foundation. Legal task semantics,
financial assertion policy, extraction occurrence selection and reconciliation
constraints remain explicit, separate policies. No old scorer or frozen code file
needs modification for the development adapter. New versions compose the original
source types so historical code hashes can still verify.

Planned verification includes item isolation, aliases/collisions/staleness, semantic
paraphrases, exact financial constraints, retrieval and candidate ceilings, oracle
diagnostics, compressed packets, actual-API safety, complete frozen regression and
isolated PostgreSQL restart. Results are pending until commands actually execute.
Live diagnostics require current model/quota admission; no model call has been made
for this task at this checkpoint. No held-out final run is authorized here.

## Architecture correction

The previous paragraph is the pre-implementation checkpoint. The correction is now
implemented; final verification status is recorded below rather than inferred here.

| Layer | Current implementation / boundary |
|---|---|
| Shared provenance | Original source_spans.py unchanged; stable source/hash/version/range/token/box IDs |
| Request aliases | source_aliases.py: request scope, collision/staleness/source checks; E01/C01 names |
| Product presentation | source_presentations.py: private alias mapping; canonical IDs restored before original validators |
| Legal source policy | source_semantics.py: sentence/clause/list fragments, sections, separators and bounded lexical/context ranking |
| Legal decision policy | external_eval/accuracy_nli.py: strict per-item DTOs; actual-request scope and exact numerics, no lexical veto |
| Invoice policy | source_invoice_candidates.py: source-only admission, labels/geometry/header discovery and explicit token joins |
| Reconciliation | Existing structured matching/financial constraints unchanged; no legal semantic policy imported |

Production graph nodes/edges, Director, outbox, PostgreSQL, financial APIs, accounting,
maker-checker and correlation authority remain unchanged. Product AR retrieval still
starts from the Broker/EvidenceReader's tenant/case/customer/invoice relationships,
source authenticity, versions/dates and exact typed facts. Text ranking is downstream
context selection, never a substitute for these relations. No graph database needed.

Internal AR contract remains v3. A separate Gemini presentation configuration version
invalidates incompatible cache reuse conservatively without rewriting history.
Remittance provider/cache identity advances to grounded-remittance-2-aliases; the
public strict Extraction DTO and original source/amount/reason-code checks remain.
Invoice development generator changes are not silently applied to financial CSVs
or production remittance value acceptance. External AI/automation remains default-off.

## Item-level validation and alias error analysis

Unknown alias, malformed field, extra field, missing item and duplicate item tests
each preserve the other16 answers. Invalid plan H07 affects H07 only. The exact
isolated worker test likewise preserves16 answers with H07's E999 rejected. Canonical
scope/hash/version checks, alias collisions, repeated occurrences and exact financial
atoms are separately tested. A completely invalid transport/envelope may still fail
the request, as intended. Strict typing is retained, not replaced by tolerant casts.

Statuses are VALID_ENTAILMENT / VALID_CONTRADICTION / VALID_NOT_MENTIONED /
INVALID_EVIDENCE / INVALID_ALIAS / MODEL_OUTPUT_FAILURE. Raw label extraction is a
separate strict scalar DTO; it never makes malformed grounded output authoritative.
Source-valid outside-local-pool evidence is explicitly distinguished from unknown
aliases. Unknown aliases cannot be reliably called deliberate fabrication versus
transcription errors without additional evidence; no normalization silently repairs
them. The historical45 rejected references cannot be reconstructed from discarded
responses, so only the aggregate error taxonomy is retained from Phase3.

Canonical alias resolution is100% for accepted synthetic fixtures; corpus invalid-
alias rate is **NOT MEASURED**, because no corpus generation passed admission.
Validator collateral rejection is zero in the stated synthetic isolation controls,
not an asserted real-model false-rejection rate.

## Development samples and leakage controls

Outputs: `C:/ClearLedgerEval/external-runs/accuracy-development-v1` (initial ceilings)
and `accuracy-development-v2` (revised architecture, controls and diagnostics).
Development source-ID manifest preserves the three existing ContractNLI DEV documents
(51 hypotheses), adds eight source-ID-selected TRAIN documents (136 hypotheses),
and32 DocILE TRAIN documents (existing eight plus24 SHA256-ranked train IDs).
No TEST/VALIDATION IDs are newly selected or annotated for tuning.

Inputs and scorer-only records are physically separate. The isolated worker can
read only inputs/config/attempts/metadata and cannot import gold/scorers/DB modules,
read scorer-only roots, call tools or reach financial APIs. Provider packets omit
class labels/annotation sets. The explicitly authorized TRAIN/DEV oracle exception
injects source-backed evidence ranges or occurrence candidates, never class labels.
Oracle candidates are blinded among distractors; no oracle-only discovery marker
is sent in provider tables. Raw document/quote/prediction content stays outside Git.

## ContractNLI retrieval ceiling

Metrics were specified before the initial development measurement: union gold-
character recall and complete-gold-character coverage, without dropping whitespace.
NotMentioned pairs have no positive evidence target. There are31 positive DEV pairs
and83 positive TRAIN pairs. Initial segmentation omitted source separators; the
correction represents them rather than loosening the metric. Both iterations remain.

Revised direct ranking (character recall; adjacent context uses one neighboring span):

| K | DEV direct /context | TRAIN direct /context |
|---|---:|---:|
| 5 | .4708 /.6177 | .6897 /.8006 |
| 10 | .6266 /.7311 | .7379 /.8415 |
| 20 | .8467 /.9011 | .8766 /.9422 |
| 40 | .8797 /.9665 | .9741 /1.0000 |

At K40+context complete-evidence coverage is29/31 DEV and83/83 TRAIN. It costs
77.1% and94.1% of source characters on average respectively; high recall is not free.

Actual selectable request exposure on DEV, K20:

| Batch | Local character recall /complete | Global union | Hybrid |
|---|---:|---:|---:|
| 17 | .8467 /.4516 | **1.000 /1.000** | .9155 /.5161 |
| 5 | .8467 /.4516 | **1.000 /1.000** | .8599 /.4839 |
| 1 | .8467 /.4516 | .9011 /.8710 | .8467 /.4516 |

Global exposure uses97.2% of source characters per17-item request and82.7% per
five-item request on average. Ranking is an efficiency hint: existing source evidence
outside a hypothesis's top-K is not unauthentic. Local/hybrid constraints leave
genuine annotated evidence unselectable even when it is visible elsewhere.
These are small development samples, not a held-out result or a universal98% claim.

## ContractNLI oracle-evidence result

Offline oracle packets contain all annotated source evidence for31/31 positive DEV
pairs, with100% character recall, no class labels and exact source-ID resolution.
**Gemini oracle classification/evidence metrics: NOT RUN.** Provider admission failed
on synthetic controls before any NDA was transmitted. No mocked accuracy is reported.
Thus reasoning capacity versus retrieval versus validator effects cannot yet be
quantified end-to-end. Visibility results alone do not establish semantic accuracy.

## Batch-size and plan versus evidence-first ablations

The predeclared matrix includes local/global/hybrid direct synthesis, historical
plan+synthesis, corrected item-level plan+synthesis, selection+classification,
five-item mini-batches, a two-hypothesis-per-document diagnostic reference path and
oracle evidence. Same three DEV documents; single-item metrics would have only six
pairs and would be reported separately. Prepared corpus matrix:60 jobs /69 maximum
generations including invoice tasks, plus synthetic admission controls;100 total
generation cap, one caller,6 HTTP operations/minute, no automatic retries.

**All live corpus ablations are NOT RUN.** No evidence supports claiming that planning,
no-plan, mini-batching or any model setting improved classification. Production AR
planning is retained. No model/thinking comparison was performed; Gemini3.5
Flash-Lite/MINIMAL was kept throughout the attempted controls.

## Raw versus grounded metrics / validator false-rejection analysis

The development scorer retains strictly parsed raw labels independently of grounded
item outcomes, using the existing classification/evidence formulas. It reports raw
accuracy/macro-F1, grounded accuracy/macro-F1/coverage, rejection categories and
unsupported assertions. Raw answers have no financial authority. Duplicate answers
are independently invalidated rather than selecting a convenient response.

**Raw/grounded corpus accuracy, F1, unsupported assertions and semantic false-rejection
rate: NOT RUN / NOT MEASURED.** The historical70 lexical rejections motivated removal
of that veto from legal policy only; this does not prove every old rejection was wrong.
The tested architecture removes whole-response coupling, but model-quality gains
cannot be inferred from unit tests. No old scorers or final predictions were changed.

## DocILE candidate recall and bounds

32 TRAIN documents include19 applicable tax invoices and25 annotated occurrence
targets. Normalization remains NFC plus outer trim only. Candidate value recall
requires exact normalized value; occurrence availability additionally requires the
correct page and box IoU>=0.5. This is a declared development diagnostic, not a native
DocILE score. Initial generator ceiling was80% value /72% occurrence recall at K16.

| K | Revised value recall | Correct-occurrence recall |
|---|---:|---:|
| 8 | 20/25 (.80) | 18/25 (.72) |
| 16 | 23/25 (.92) | 21/25 (.84) |
| 32 | .92 | .84 |
| 64 | .92 | .84 |
| 128 /256 /1024 | .92 | .84 |

No internal search was incomplete on this sample. The64-provider bound is therefore
not the measured bottleneck here. Two values cannot be constructed from the current
trustworthy OCR representation; two available values have no matching occurrence
under the declared IoU criterion. This does not establish98%/97% availability.
No document-ID-specific rule, score normalization or geometry rescue was added.

## DocILE oracle-candidate result

The paired live subset was source-ID-selected16 TRAIN documents, seven applicable
invoices with10 annotated instances. Only8 instances have a source-grounded occurrence
that can be constructed for the oracle packet, producing five oracle jobs. The
other two cannot be fabricated or silently removed from normal diagnostics.
Oracle correct candidates are guaranteed present within the bounded set and blended
with unmarked distractors. **Normal/oracle Gemini selector accuracy: NOT RUN.**
No conclusion about selector versus reasoning quality follows without those calls.

## DocILE token-cap / localization analysis

On the same32 source candidate pools, uncompressed long-ID objects total305,507
bytes; compact short-alias tables total127,020 bytes: **58.4% reduction**, with the
same candidate values/occurrences retained. Local characters/4 +512 overhead is an
estimate, not exact Gemini tokenization. Both formats have zero estimated8192-cap
exceedances in this TRAIN selection. Exact provider token admission and selector
accuracy were not measured. This does **not** demonstrate elimination of the four
Phase3 failures, which were not rerun.

21/25 targets have a value+occurrence candidate; two lack a source-grounded value,
two miss the declared occurrence criterion. No target in this selection reproduced
the precise old missing-coordinate category; malformed-geometry/None behavior is
covered by synthetic and existing source tests. The old three final cases were not
opened or repaired. The existing bounded PDF parser was tested on the two source-
value misses: both READY; one contained the value in its text layer, one did not.
That parser exposes no verified word boxes. Text recovery cannot be advertised as
coordinate recovery; missing localization remains explicit. No coordinates invented.

## Provider admission blocker — actual requests

Operator confirmed the same Free project, Gemini3.5 Flash-Lite,15 RPM /250k input
TPM /500 RPD. Displayed4 RPM /57.53k TPM /230 RPD was explicitly a28-day peak view,
not an exact remaining-daily counter. Model lookup succeeded; limits were1,048,576
input /65,536 output. Billing/project/key/model were not changed.

| Synthetic operation | Actual outcome |
|---|---|
| Evidence plan | HTTP200, accepted structured result |
| Synthesis with short alias enums | HTTP400 INVALID_ARGUMENT |
| Synthesis without alias-array enum | HTTP400 INVALID_ARGUMENT |
| Equivalent local-ref-inlined synthesis | HTTP400 INVALID_ARGUMENT; safe reason UNKNOWN, no field paths |
| Invoice control | HTTP503 UNAVAILABLE |
| One counted invoice transient re-attempt | HTTP503 UNAVAILABLE |

Six generation attempts,13 HTTP operations; zero corpus calls. The successful
synthetic plan is reused for schema comparisons, not regenerated. Raw provider
messages/bodies/prompts/keys/URLs are not persisted. Only fixed categories, safe
status and whitelisted structured field paths may be recorded. Removing enums and
inlining refs did not solve the400. **The exact incompatible field/root cause is
UNKNOWN.** The two503s establish unavailable responses, not proof of a schema defect
or exhausted quota. No repeated unchanged400, model switch or endless retry followed.

Current official references checked2026-11-06:
[model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[pricing](https://ai.google.dev/gemini-api/docs/pricing),
[thinking](https://ai.google.dev/gemini-api/docs/thinking).
Standard Free input/output is listed free; invoice/billed USD is not exposed by the
API and is UNKNOWN. Only the successful plan has returned usage; failed-call usage
is unavailable, not zero. Conservative ledger reservations are114,819 input and
14,358 output tokens; these are not actual usage or charges. No real/public document
left the machine in this task. Corpus/oracle/model-quality gates remain unverified.

## Recommended final configuration / stop

**Do not freeze or run another held-out evaluation yet.** Source-global short aliases
and independent item validation are justified by correctness tests and exposure.
Five-item global evidence-first synthesis is a candidate for a later configuration,
not an experimentally selected winner: batch/plan/selector accuracy and cost-quality
tradeoffs remain unmeasured. Keep Gemini3.5 Flash-Lite/MINIMAL pending those diagnostics;
no production plan stage is removed. Candidate ceiling92%/84%, geometry and live
provider admission remain open. No statistical reliability/production AR claim.

## Product safety regression and financial authority

Initial PostgreSQL focus attempt:1 passed /22 setup errors because Docker Desktop
was manually paused; connection timeout, not an application assertion failure.
Operator resumed Docker. Same actual-API group then passed23 tests in179.30s.
Complete frozen gate `.venv/Scripts/uv.exe run --frozen python scripts/verify.py`
PASS: **1049 tests in2226.71s**, required PostgreSQL migration/integration checks,
lock/dependency checks, Ruff/format295 files, strict mypy38 files and matching bounds.
Isolated PostgreSQL restart: **4 passed in55.87s**. Compilation and focused isolated
worker controls pass. Logs remain local:
`local-data/verification/20261106T123328665712Z.log` and
`local-data/verification/isolated-restart-20261106T124159239723Z.log`.
The37-minute suite duration is test verification wall-clock, not product latency.
No runner/product/provider timeout change was made in this task.
Final Phase0/2/3 plan/code/config/prediction/result seal checks PASS; no frozen
artifact changed. Live corpus model-quality acceptance remains blocked, not passed.
No financial posting/approval/allocation authority, schema migration, new service,
Director change, graph topology change, hidden data use or held-out inference.
External AI and automation flags remain disabled. No push.
