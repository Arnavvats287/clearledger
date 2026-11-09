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

## Completion pass — 2026-11-09

The previous blocked checkpoint above is historical. This pass reused only the
previously selected 3 ContractNLI DEV and 8 TRAIN documents and 32 DocILE TRAIN
documents. The development results are kept under `local-data/accuracy-completion`.

### Synthetic provider admission

Gemini `gemini-3.5-flash-lite`, `MINIMAL`, `generateContent`, with the same prompt,
synthetic payload, and output cap across schema probes. The minimal accepted form
was an object containing `items`, an array of objects with string `id`, string
`label` and array-of-string `evidence`. The simple synthesis uses that same nesting
with the existing `answers` fields. The schema logs contain schema hashes and
sizes, deltas, attempts, timestamps, safe status, latency and usage.

| Probe | Actual HTTP result |
| --- | --- |
| Minimal nested array shape | 200 |
| Label enum and alias enum, independently | 200 each |
| Outer and inner `minItems` / `maxItems`, independently on the minimal shape | 200 each |
| `required`, `additionalProperties`, nullable type union, description | 200 each |
| `$defs` alone, adding `$ref`, nullable `anyOf` | 200 each |
| Exact synthesis DTO, including both nested `maxItems` bounds | 400 `INVALID_ARGUMENT`, twice |
| Full synthesis DTO removing only outer `maxItems: 17` | 200 |
| Full synthesis DTO removing only inner `maxItems: 20` | 200 |
| Full synthesis DTO removing both bounds | 200 |
| Simple synthesis retaining all fields and nesting | 200 |

The observed trigger is the pair of array bounds in the full synthesis schema.
The one-variable removals retain depth and all other DTO fields and constraints.
The provider did not identify its internal threshold or rejected field. Google
documents both array bounds and rejection of some complex schemas.
[Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).

The development worker sends only the object, array and string transport shapes.
Local validation still checks enum values, required/extra fields, item counts,
missing/duplicate hypotheses, aliases, source identity and hashes, and factual
constraints. The historical validator remains in its own ablation. Provider
errors are recorded per attempt. Only eligible transient errors may receive two
additional attempts, with deterministic backoff and ten-second operation pacing.

### Offline ContractNLI exposure

Five-hypothesis requests are shown below. The checked-in preparation command
also measures 1- and 17-hypothesis requests. Recall and complete coverage are
over 31 DEV and 83 TRAIN positive pairs. Exposure is mean unique document
characters sent per request. Token estimates use UTF-8 payload bytes divided by
four and exclude the instruction and schema. They differ from provider usage.

| Strategy | DEV recall | DEV complete | DEV exposure | DEV tokens / aliases | TRAIN recall | TRAIN complete | TRAIN exposure | TRAIN tokens / aliases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local K20 | 84.67% | 14/31 | 67.38% | 4314 / 45.0 | 87.66% | 53/83 | 82.74% | 2700 / 30.8 |
| Local K40 | 87.97% | 17/31 | 86.34% | 5826 / 62.0 | 97.41% | 66/83 | 96.11% | 3514 / 43.7 |
| Local K20 + neighbors | 90.11% | 27/31 | 83.06% | 6142 / 80.5 | 94.22% | 78/83 | 92.03% | 3573 / 51.3 |
| Local K40 + neighbors | 96.65% | 29/31 | 94.38% | 7411 / 96.5 | 100% | 83/83 | 98.70% | 4121 / 59.8 |
| Global union K20 | 100% | 31/31 | 83.06% | 6232 / 80.5 | 99.92% | 82/83 | 92.03% | 3547 / 51.3 |
| Section-first K20 | 76.24% | 22/31 | 37.16% | 2918 / 37.9 | 60.18% | 49/83 | 52.42% | 1814 / 24.4 |
| Section + span K20 | 76.51% | 18/31 | 62.39% | 4174 / 50.8 | 90.31% | 65/83 | 80.43% | 2736 / 36.5 |

Section grouping uses source headings and contiguous clauses, with group scores
derived from lexical rank and scaled by group size. The hybrid retains lexical
anchors and nearby spans within sections. On TRAIN it improves K20 local recall
and complete coverage at lower document exposure, but uses slightly more packet
tokens. On DEV, section-first reduces exposure and improves complete coverage
relative to local K20 while losing character recall. The global pool provides
the strongest measured DEV ceiling. The earlier 77.1% and 94.1% K40 exposure
figures are per-hypothesis means. The table measures the combined batch request.

### DocILE source ceiling

All 32 PDFs produced bounded parser representations. OCR candidates take priority.
Up to eight novel PDF text candidates use the PDF byte digest, parser version and
canonical exact text range, with `localization_status=UNAVAILABLE` on selection.
OCR candidates preserve source token IDs and geometry. The label parser now joins
visible punctuation fragments across whitespace, including slash and backslash,
and tolerates small left overlap in right-of-label box alignment.

The live-sized packets expose **23/25 values (92%) and 21/25 localized occurrences
(84%)**. All recovered OCR values rank among the first 13 candidates. The source
pool offers 78 supplemental PDF
candidates across the 32 documents. Combined packet estimates total 141,365 bytes,
with a maximum of 11,604 bytes before the system prompt/schema.

| Remaining TRAIN misses | Count | Observation |
| --- | ---: | --- |
| PDF text only, no exact standalone value | 1 | The target occurs inside a longer punctuation-delimited identifier. Truncating it has no independent source boundary. |
| Source absent | 1 | Exact target absent from the admitted OCR and PDF text. |
| Correct value, occurrence geometry fails | 2 | Best observed IoU was 0 and 0.3085 respectively, below the frozen 0.5 criterion. |

The fallback increases representational coverage. It does not raise measured
recall on these 25 targets. Source limits, instead of the candidate rank cap,
account for the observed misses. Scoring normalization remains NFC plus outer trim.

### Live ContractNLI development ablations

Raw semantic metrics accept only exact label literals and count malformed or missing
items as abstentions. Grounded metrics additionally require strict typed rows and
verified evidence. The existing unsupported-assertion metric counts assertive
predictions whose class disagrees with gold, divided by all assertive predictions.
Evidence F1 is grounded gold-character overlap. Counts include all scheduled pairs.

| Path | Pairs | Raw accuracy / macro-F1 | Grounded accuracy / macro-F1 | Evidence F1 | Unsupported assertions | Generations | Input / output tokens observed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local direct, 17 | 51 | 80.39% / .5667 | 74.51% / .5413 | .6657 | 23.53% | 3 | 24090 / 3347 |
| Global direct, 17 | 51 | 80.39% / .5648 | 80.39% / .5648 | .7255 | 27.03% | 3 | 45582 / 3396 |
| Hybrid direct, 17 | 51 | 82.35% / .5729 | 82.35% / .5778 | .6692 | 18.18% | 3 | 33007 / 3299 |
| Historical plan then synthesis | 51 | 58.82% / .4745 | 0% / .0000 | .0000 | N/A | 6 | 82113 / 6816 |
| Item-level plan then synthesis | 51 | 0% / .0000 | 0% / .0000 | .0000 | N/A | 6 | 91880 / 5595 |
| Select evidence then classify | 51 | 84.31% / .5883 | 84.31% / .5883 | .6579 | 20.59% | 7 | 77107 / 5520 |
| Global direct, batches of up to 5 | 51 | 70.59% / .5287 | 70.59% / .5287 | .6031 | 23.33% | 12 | 79665 / 3574 |
| Global direct, single-item reference | 6 | 83.33% / .6000 | 83.33% / .6000 | .5681 | 0% | 6 | 18249 / 448 |
| Blinded oracle evidence | 51 | 50.98% / .4375 | 50.98% / .4375 | .4944 | 31.82% | 3 | 50482 / 3421 |
| DEV section-first | 51 | 78.43% / .5443 | 74.51% / .5291 | .5816 | 16.67% | 3 | 19576 / 3211 |
| DEV section + span | 51 | 56.86% / .4771 | 54.90% / .4677 | .4413 | 16.67% | 3 | 25304 / 3292 |
| TRAIN section + span | 136 | 70.59% / .6631 | 67.65% / .6351 | .7071 | 20.83% | 8 | 48409 / 8695 |

The six single-item pairs also scored 6/6 with the existing 17-item global outputs,
versus 5/6 for the single-item calls. Grounded macro-F1 on those pairs was .6667 vs
.6000. Contradiction had zero support in that six-pair sample. Neither reduced
batch size improved measured accuracy on these samples. The five-item path used
12 calls versus three for the 17-item global run.

The blinded oracle included source evidence for all 31 positive DEV pairs without
class labels. Grounded per-class F1 was .6250 Entailment, .0000 Contradiction and
.6875 NotMentioned. One oracle response used relation-style or underscored strings
in the label field for all 17 items. Across the other two responses, 26/34 labels
were correct.
The oracle did not outperform normal retrieval, even with source coverage verified
offline. Formatting and semantic classification both remain bottlenecks. The oracle
does not support attributing the main error to retrieval alone.

The historical validator rejected all three synthesis documents. The item-level
plans themselves validated, but all 51 resulting synthesis rows used unsupported
uppercase or underscored label literals. The direct global path had zero local
rejections. The select-then-classify path gained two correct DEV answers at the cost
of three additional planned calls, one transient retry and lower evidence F1.
Its Contradiction F1 remained zero. The corpus shows that removing provider enums
can leave significant format error even when strict local isolation works.

Across the alias-based synthesis jobs, 558 references were declared. All existed
in their request catalogs. Thirteen (2.33%) were known aliases outside the
hypothesis's selectable scope, including references in malformed rows. Strict
validation recorded 12 evidence rejections and 115 item-output failures among 601
scheduled pairs (127/601, 21.13%). The item failures are chiefly invalid literals.
No alias normalization or relabeling was applied. A single-hypothesis scorer
denominator mismatch was corrected offline by projecting the original packet to
the requested hypothesis IDs. Gold coverage enforcement remains strict. A separate
occurrence counter deduplicates multiple selected aliases hitting the same gold box.
Both corrections used the same saved predictions.

### Live DocILE normal vs blinded oracle

| Path | Documents | Correct / gold values | Correct / emitted values | Distinct gold occurrences recovered | Unknown aliases | Non-invoice emissions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Normal, full live TRAIN subset | 16 | 4/6 | 4/8 | 6/10 | 0/10 | 1 |
| Normal, paired oracle documents | 5 | 4/5 | 4/6 | 6/9 | 0/8 | 0 |
| Blinded oracle, same documents | 5 | 5/5 | 5/6 | 8/9 | 0/17 | 0 |

Oracle candidates were source-constructible occurrences blended among distractors.
The gain on the paired documents indicates that candidate availability matters.
The remaining incorrect emission shows that selection remains imperfect. Multiple
aliases can hit one occurrence. The table counts each gold occurrence at most once.
Exact document value sets matched on 12/16 normal documents and improved from 3/5
to 4/5 on the paired oracle documents.
Exact token admission passed for every DocILE generation in this run, including
fallback packets. This pass did not re-execute old capped requests.

### Transport, reproducibility and recommendation

The final worker recorded 88 generation attempts, comprising 85 corpus attempts
and three synthetic controls. There were 83 successful corpus responses and two
HTTP 503 `UNAVAILABLE` attempts, one during evidence selection and one during
invoice extraction. Each succeeded on its first permitted transient retry. There
were zero corpus HTTP 400s, 429s or input-cap failures. Across the final 85 corpus
attempts, provider generation latency was 6.863s median, 10.973s p95 and 12.076s
maximum, excluding pacing. The 83 reported responses used 672,077 input and 51,273
output tokens, 723,350 total. Failed usage and separate thinking counts were
unavailable. Schema probes added 21 synthetic generations, and the earlier exact
worker admission added three. Total for this pass: 112 generation attempts and
205 HTTP operations. Billing and model selection stayed as configured by the
operator. Provider billing amounts are unavailable.

Run artifacts: `local-data/accuracy-completion/run-v2`, with all 74 development
predictions, exact attempt metadata, variant-level performance, offline exposure,
invoice ceilings and `development-seal.json`.
Campaign SHA256 `6507ce6839d48d79cc0d574bf3ead74e5a3ece1b2f8bcf6ff32a938178f77483`.
Development seal SHA256 `e4c0fc12148bac917983ac2356ce9e5f5040028b8696403e26935ee865f82abc`.

For a future configuration review, the 17-item direct path offers the best
measured call efficiency. Global K20 is the evidence-recall reference, and the
direct hybrid is the lower-cost accuracy and assertion-rate candidate on DEV.
Evidence-first selection merits consideration only if its extra calls are worth
the observed two-answer gain. Keep local validation and consider retaining admitted
label enums with the nested array bounds removed. This schema passed synthetic
admission, but its semantic performance has not been measured on the corpus.
The weak contradiction results and format failures argue against freezing a final
configuration based on these DEV results alone. No alternate model or thinking
level was tested.

For an already authorized development run, `scripts/accuracy_completion.py prepare`
takes `--runs`, `--docile` and a new `--root`. Use the same root with `preflight`
before `run`. `scripts/accuracy_score.py --runs <runs> --development-root <root>`
scores existing attempts without a provider call. The scorer refuses to replace
an existing result file. The original blocked checkpoint and evaluation seals
remain available for independent integrity checks.

### Verification

- Focused grounding, schema, transport and scorer suite: 53 passed in 5.78s.
- Final `uv run --frozen python scripts/verify.py`: 1,058 passed in 2,008.96s.
  PostgreSQL migrations/integration, matching bounds, lock/dependencies, Ruff,
  format and strict mypy all passed. Strict mypy checked 40 source files.
- `uv run --frozen python scripts/verify_isolated_restart.py`: 4 passed in 87.27s.
  It removed only the disposable resources owned by that invocation.
- Compilation, imports, Phase 0/2/3 plan/code/config/prediction/result seal checks,
  and the local development seal all passed. External AI and automation flags
  were false.

The earlier regression run passed 1,056 tests. The final suite includes the
additional punctuation and scoped-scorer cases. Full logs are local under
`local-data/verification/20261109T104959802108Z.log` and
`local-data/verification/isolated-restart-20261109T101135869486Z.log`.
The evaluation worker had no database or financial action access. No new held-out
sample was selected, transmitted or scored.

## FINAL CONTRACTNLI CONFIGURATION SELECTION

The comparison reuses all 17 hypotheses for each of the three established DEV
documents and eight established TRAIN documents. The gold denominators are 51
and 136. Contradiction has two DEV positives and 18 TRAIN positives. Results are
reported separately because the DEV class estimate can move sharply with one item.

The predeclared zero-shot matrix includes direct hybrid, direct global and global
evidence selection followed by classification at `MINIMAL` on Gemini 3.5
Flash-Lite. The fourth candidate repeats hybrid direct with `LOW` and paired
evidence, aliases, prompt, schema, caps and scorer. Google documents `LOW` as the
next Flash-Lite setting. Gemini 3.5 Flash is the sole stronger-model candidate,
paired against direct hybrid `MINIMAL` on the same 11 documents, conditional on
synthetic admission using the same Free project after the thinking comparison.
[Gemini thinking levels](https://ai.google.dev/gemini-api/docs/thinking).
[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

The revised instruction distinguishes explicit support, material incompatibility
and missing information. It calls out negation, defined terms, narrower scope,
exceptions, prohibitions and party/temporal scope. The transport restores only
the final `predicted_label` enum (`Entailment`, `Contradiction`, `NotMentioned`).
Both nested array bounds stay out of the provider schema. The local validators
still check item counts, scope, source and alias membership, and explicit evidence
for assertive conclusions. Predictions are scored verbatim with no label repairs.

The comparison uses full denominators, including failed calls and abstentions.
Predeclared quality gates require zero malformed labels, document cascades and
unknown aliases, at least 95% grounded coverage and at most 25% unsupported
assertions on each split, DEV macro-F1 of at least .3954, and positive grounded
Contradiction F1 on both splits. These thresholds are decision aids for this small
development comparison. They do not estimate performance on a fresh test set.

### DEV results (51 hypotheses per candidate)

All candidates use the revised instruction and zero-shot inputs. `E/C/N` means
Entailment / Contradiction / NotMentioned F1. Format counts are malformed
literal / missing label field. Alias counts are unknown / known but outside the
hypothesis's selectable set. Provider failures count attempts, including recovered
transients. Token counts are provider-reported input/output. Latency is median/p95
generation seconds, excluding count-token calls, backoff and pacing.

| Model | Thinking | Evidence strategy | Grounded accuracy | Macro-F1 | E/C/N F1 | Coverage | Evidence F1 | Unsupported | Format | Alias | Failures / calls | Input/output tokens | Median/p95 s |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| 3.5 Flash-Lite | MINIMAL | Hybrid direct | 42/51 | .5654 | .8852/.0000/.8108 | 49/51 | .6600 | 5/32 | 0/0 | 0/3 | 1/4 | 33211/3273 | 4.973/9.594 |
| 3.5 Flash-Lite | MINIMAL | Global direct | 42/51 | .5727 | .9180/.0000/.8000 | 49/51 | .7021 | 6/34 | 0/0 | 0/0 | 1/4 | 45786/3158 | 3.168/3.450 |
| 3.5 Flash-Lite | MINIMAL | Global select then classify | 41/51 | .5602 | .8571/.0000/.8235 | 51/51 | .6968 | 10/37 | 0/0 | 0/0 | 2/8 | 77032/4901 | 2.697/3.373 |
| 3.5 Flash-Lite | LOW | Hybrid direct | 46/51 | .6188 | .9333/.0000/.9231 | 50/51 | .6736 | 3/31 | 0/0 | 0/2 | 0/3 | 33211/3071 | 3.212/3.529 |
| 3.5 Flash | MINIMAL | Hybrid direct | 42/51 | .5871 | .8966/.0000/.8649 | 48/51 | .6652 | 5/31 | 0/0 | 0/4 | 1/4 | 33211/3393 | 7.802/10.535 |

### TRAIN sanity check (136 hypotheses per candidate)

| Model | Thinking | Evidence strategy | Grounded accuracy | Macro-F1 | E/C/N F1 | Coverage | Evidence F1 | Unsupported | Format | Alias | Failures / calls | Input/output tokens | Median/p95 s |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| 3.5 Flash-Lite | MINIMAL | Hybrid direct | 108/136 | .6890 | .8652/.4167/.7850 | 136/136 | .7493 | 16/82 | 0/0 | 0/0 | 0/8 | 57316/8377 | 3.341/4.381 |
| 3.5 Flash-Lite | MINIMAL | Global direct | 106/136 | .7116 | .8392/.5385/.7573 | 136/136 | .7736 | 19/86 | 0/0 | 0/0 | 0/8 | 72651/8347 | 3.121/9.097 |
| 3.5 Flash-Lite | MINIMAL | Global select then classify | 109/136 | .6981 | .8671/.4348/.7925 | 136/136 | .7844 | 16/83 | 0/0 | 0/0 | 2/18 | 126602/13919 | 2.907/6.056 |
| 3.5 Flash-Lite | LOW | Hybrid direct | 105/136 | .6773 | .8552/.4167/.7600 | 133/136 | .7635 | 19/86 | 0/2 | 0/0 | 0/8 | 57316/8157 | 3.269/6.423 |
| 3.5 Flash | MINIMAL | Hybrid direct | 107/136 | .7186 | .8489/.5185/.7885 | 134/136 | .7658 | 17/83 | 0/0 | 0/2 | 0/8 | 57316/8661 | 8.887/20.636 |

All 55 corpus jobs returned a synthesis envelope and none experienced a
document-level validation cascade. The final label enum eliminated malformed
literals. The two omitted TRAIN label fields on LOW remain failures. There were
zero unknown aliases in 719 declared synthesis references and 11 known references
outside the permitted hypothesis scope. Seven transient HTTP 503s recovered
within the retry allowance. The 73 corpus generation attempts and five synthetic
generations used 158 HTTP operations, including two model metadata lookups.
The 66 successful corpus generations reported 593,652 input and 65,257 output
tokens. Failed-call usage and separate thinking-token counts were unavailable.

### What the comparisons resolve

- Direct hybrid LOW gained four correct DEV answers relative to MINIMAL, but
  lost three on TRAIN and left Contradiction F1 unchanged on both splits. The
  stored evidence-packet hashes match across all 11 MINIMAL/LOW pairs. This
  result does not justify choosing LOW on the basis of DEV accuracy alone.
- Gemini 3.5 Flash passed the Free-project synthetic gate and used the same 11
  hybrid packets, prompt, schema and MINIMAL setting as the Lite reference.
  It improved TRAIN Contradiction F1 from .4167 to .5185 and macro-F1 from .6890
  to .7186, with a higher median latency. DEV Contradiction remained zero and
  grounded accuracy stayed 42/51. Its DEV coverage fell to 48/51.
- Selection then classification used 26 attempts across the two splits versus
  12 for direct global, including retries. It gained three TRAIN answers and
  lost one DEV answer, with lower macro-F1 on both splits. The selection step
  retained complete contradiction evidence for 0/2 DEV and 9/18 TRAIN positives.
- Direct global offered all annotated contradiction characters for **2/2 DEV**
  and **18/18 TRAIN** positives. Every candidate missed both DEV contradictions
  in the raw predictions before validation. The hybrid packets exposed 895/898
  contradiction evidence characters in DEV and 7196/7202 in TRAIN. The remaining
  DEV weakness is in semantic classification despite evidence access. This
  experiment cannot isolate model capacity from prompt behavior, and the two
  supported DEV examples give limited precision for the class estimate.

### RECOMMENDED FINAL CONFIGURATION

**Reference for configuration review: Gemini 3.5 Flash-Lite `MINIMAL`, direct
global K20. Recommendation for Phase 3B: hold.** None of the five candidates
passed the predeclared DEV contradiction gate. The direct global reference
gives 96.08% DEV and 100% TRAIN grounded coverage, the highest TRAIN Contradiction
F1 (.5385), full contradiction evidence exposure, zero alias scope failures and
one planned generation per document. The stronger model gained .0070 TRAIN
macro-F1 over this reference with materially higher latency and no DEV
contradiction gain. Higher thinking and the extra selection pass gave no
consistent cross-split improvement.

| Setting | Exact value |
| --- | --- |
| Model / thinking | `gemini-3.5-flash-lite` / `MINIMAL` |
| Prompt | `SELECTION_INSTRUCTION` in `scripts/external_eval/accuracy_nli.py`, canonical JSON SHA256 `e1e11debee729cebae0e73362022bf85fb6aa68bef2198d02baf5495100405bb` |
| Schema | `exact_label_provider_schema()`, canonical JSON SHA256 `9f4dc71606fdbc29c9272e29f6867b198348461934827ec7391926823b3bdcce` |
| Evidence | Direct global. Per-hypothesis rank K20, one adjacent span on either side on the same page. Union deduplicated by canonical span, ordered by source position, and selectable by every hypothesis. |
| Batch / examples | 17 hypotheses, zero-shot |
| Validation | Strict per-hypothesis DTO, duplicate/missing isolation, request-local alias membership, canonical source/hash/version resolution, exact-atom checks, and explicit incompatible evidence for Contradiction. No label repair. |
| Caps | 32,768 counted input tokens and 4,096 output tokens including thinking |

DocILE remains frozen at 23/25 candidate values and 21/25 localized occurrences.
The selection pass used only the established ContractNLI TRAIN/DEV material.

Artifacts are under `local-data/contract-selection-v1`. Baseline config SHA256
`e8a3e60f341d19525992544431003668d253ee52930beb1a85be028b712ff151`.
Stronger-model config SHA256
`19ff48e3ad8ef4d8bf7ec990e7d563316435e2f20ef8f5c791e75f7c696f8ef2`.
Development comparison seal SHA256
`5d41af476f94e56e8b052501b82da74e91b0dab0f18a15619b3776a1d64f524d`.

Focused verification passed 59 tests. The complete `uv run --frozen python
scripts/verify.py` gate passed 1,064 tests in 1,999.07s, including PostgreSQL
integration/migrations, matching bounds, lock/dependency, Ruff, format and strict
mypy (41 files). Isolated restart passed four tests in 62.39s. Compilation and
the Phase 0/2/3 and prior development seal checks passed. The production graph,
financial validators and authority boundaries retain their existing behavior.
External AI and automation are disabled. Full local logs are
`local-data/verification/20261109T115210406903Z.log` and
`local-data/verification/isolated-restart-20261109T115212107836Z.log`.

## FINAL CONTRADICTION-REASONING PASS

This comparison uses the saved global MINIMAL reference as a historical control
and four new formulations on the same 3 DEV and 8 TRAIN documents. Each new job
checks the complete source packet digest against the saved reference before the
provider call. The model, MINIMAL setting, global K20 with adjacent context, all
17 hypotheses, aliases, provenance checks, 32,768 input cap and 4,096 output cap
are shared. The historical control is scored from its saved output.

| Variant | Decision formulation |
| --- | --- |
| A | Explicit three-way rubric with the exact reference label enum and response schema. |
| B | Strict JSON support and explicit-conflict booleans. A single positive maps to its class, two negatives map to NotMentioned, and two positives fail that item. |
| C | Separate support and conflict alias arrays and the exact label enum. The local adapter rejects a missing or incompatible evidence role. |
| Few-shot | A plus five frozen labeled TRAIN demonstrations from distinct documents outside both evaluated cohorts. |

B and C use simple schema shapes with only the fields required by their respective
formulations. Neither adds provider-side array bounds. Accepted B/C fields pass
through the same strict item and source validators used by the reference. Raw
B labels derive only from the declared truth table, and raw A/C/few-shot labels
retain exact literals before role and source validation. The scorer keeps absent,
invalid and duplicate decisions in the full denominator.

The disjoint TRAIN demonstrations were selected in deterministic hash order from
label- and source-cue strata. They were frozen before provider admission.

| Demonstration category | TRAIN document / hypothesis |
| --- | --- |
| Explicit entailment | `198` / `nda-3` |
| Contradiction with negation | `202` / `nda-17` |
| Contradiction with an exception cue | `597` / `nda-7` |
| NotMentioned, absence | `191` / `nda-1` |
| NotMentioned, lexical overlap | `365` / `nda-4` |

Demonstration SHA256 `470657811e6038a6ee0bf860b8edb2ba0c67ec7223b0de563203c056b74340dc`.
The model receives only the disjoint examples' excerpts, hypotheses and answers.
Their `DEMO` aliases have no authority in the evaluated packet. Evaluated gold
remains scorer-only. The frozen TRAIN sanity set contains all 18 TRAIN
Contradiction positives and hash-selected 9 Entailment and 9 NotMentioned controls.
It uses a subset of the same predictions, with no extra calls.

The selection thresholds were frozen before inference. A material TRAIN
Contradiction F1 gain is at least .05. Consider a DEV gain only alongside TRAIN
stability and full-cohort quality. Allow at most .02 macro-F1 loss, require at
least 95% grounded coverage and at most 25% unsupported assertions on both splits,
and keep input and output token use within 1.5 times the control. Also check
malformed outputs, alias failures, latency and the direction of the paired results.
The source-cue taxonomy records observed label outcomes, citation overlap and
validation outcomes. Scope, temporal, exception and negation cues describe the
annotated text and do not reveal the model's internal reasoning.

### Classification and evidence results

Accuracy uses the full split denominator. Class F1 is grounded and ordered
Entailment / Contradiction / NotMentioned. Unsupported assertions are assertive
predictions that disagree with the gold class, divided by all assertive predictions.

| Split | Formulation | Raw correct / macro-F1 | Grounded correct / macro-F1 | Grounded class F1 | Grounded coverage | Unsupported | Evidence-overlap F1 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| DEV | Saved reference | 44/51 / .5943 | 42/51 / .5727 | .9180/.0000/.8000 | 49/51 | 6/34 | .7021 |
| DEV | A, rubric | 41/51 / .5570 | 41/51 / .5570 | .8710/.0000/.8000 | 49/51 | 7/34 | .6546 |
| DEV | B, binary | 44/51 / .5833 | 44/51 / .5833 | .9000/.0000/.8500 | 51/51 | 4/31 | .6467 |
| DEV | C, evidence roles | 44/51 / .5982 | 44/51 / .5982 | .9000/.0000/.8947 | 51/51 | 6/33 | .7183 |
| DEV | TRAIN few-shot | 43/51 / .5889 | 43/51 / .5889 | .9333/.0000/.8333 | 51/51 | 7/35 | .7366 |
| TRAIN | Saved reference | 106/136 / .7116 | 106/136 / .7116 | .8392/.5385/.7573 | 136/136 | 19/86 | .7736 |
| TRAIN | A, rubric | 105/136 / .5801 | 105/136 / .5801 | .8531/.1053/.7818 | 136/136 | 17/79 | .8105 |
| TRAIN | B, binary | 105/136 / .5782 | 105/136 / .5782 | .8794/.1053/.7500 | 136/136 | 14/77 | .7336 |
| TRAIN | C, evidence roles | 109/136 / .7315 | 109/136 / .7315 | .8571/.5333/.8039 | 136/136 | 19/87 | .7812 |
| TRAIN | TRAIN few-shot | 98/136 / .7197 | 98/136 / .7197 | .8455/.5714/.7423 | 119/136 | 13/75 | .7415 |

Raw and grounded accuracy and macro-F1 agreed for the four variants. A still
lost two incorrect DEV decisions to the evidence validator, moving coverage
from 51/51 raw to 49/51 grounded. The reference lost two correct DEV decisions
to item validation. All 17 hypotheses in the failed few-shot TRAIN request stay
in the table and are classified as provider failures in the grounded score.

### Formats, aliases and transport

`U/O/M` counts unknown aliases, outside-scope aliases and malformed label literals.
For B, the format count refers to invalid boolean decisions. Latency is the
provider generation median/p95 in seconds, excluding pacing and token counting.
The reference uses its saved attempt log.

| Split | Formulation | U/O/M | Failed attempts / calls | Observed input/output tokens | Median/p95 s |
| --- | --- | --- | ---: | --- | --- |
| DEV | Saved reference | 0/0/0 | 1/4 | 45786/3158 | 3.168/3.450 |
| DEV | A | 0/0/0 | 0/3 | 45771/3165 | 4.773/5.113 |
| DEV | B | 0/0/0 | 0/3 | 45720/2647 | 3.130/6.975 |
| DEV | C | 0/0/0 | 0/3 | 45756/2855 | 3.616/3.674 |
| DEV | TRAIN few-shot | 0/0/0 | 0/3 | 47640/3200 | 4.437/8.084 |
| TRAIN | Saved reference | 0/0/0 | 0/8 | 72651/8347 | 3.121/9.097 |
| TRAIN | A | 0/0/0 | 2/10 | 72611/8286 | 3.245/7.568 |
| TRAIN | B | 0/0/0 | 3/11 | 72475/6850 | 3.048/4.711 |
| TRAIN | C | 0/0/0 | 0/8 | 72571/7344 | 2.937/3.340 |
| TRAIN | TRAIN few-shot | 0/0/0 | 3/10 | 69909/6868 | 2.955/3.885 |

All 529 declared variant aliases were valid and in scope. Successful responses
had zero duplicate or missing hypothesis rows, malformed labels or invalid binary
decisions. There were no validation cascades. The four synthetic controls passed
and the 44 development jobs recorded 51 generation attempts. Of eight corpus
HTTP 503s, five recovered and three exhausted one few-shot job's allowance.
One additional HTTP 503 occurred during synthetic admission and recovered. The
43 successful corpus responses reported 472,453 input and 41,215 output tokens.
There were zero HTTP 400s, token-cap rejections or semantic retries. Total new
activity was 56 generations and 113 HTTP operations, including the model lookup.

### Contradiction taxonomy and TRAIN sanity set

Every formulation, including the reference, assigned Entailment to one DEV gold
contradiction and NotMentioned to the other before validation. Both annotations
were fully selectable. In each case pair, the Entailment answer selected text
overlapping the annotated conflict but interpreted it as support. The NotMentioned
answer selected no overlapping conflict text. No variant declared an explicit
conflict role with a different label on these DEV positives.

| TRAIN formulation | Gold contradictions correctly labeled | Labeled Entailment | Labeled NotMentioned | No decision, provider failure | Wrong label with gold overlap | No conflict overlap among misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Saved reference | 7/18 | 4 | 7 | 0 | 4 | 7 |
| A | 1/18 | 7 | 10 | 0 | 9 | 8 |
| B | 1/18 | 3 | 14 | 0 | 3 | 14 |
| C | 8/18 | 4 | 6 | 0 | 4 | 6 |
| TRAIN few-shot | 10/18 | 0 | 6 | 2 | 0 | 8 |

All TRAIN contradictions had fully available annotated evidence before inference.
The taxonomy records each item locally. The party/scope and exception cues appear
in the DEV error set. TRAIN misses also include temporal and explicit negation
cues. These cues identify where to inspect the source. They do not establish
which mental inference the model made. The six wrong few-shot TRAIN labels were
NotMentioned with no annotated overlap, and two additional contradictions had no
response. No wrong gold-contradiction answer was lost to local validation.

| Formulation | Frozen TRAIN sanity accuracy | Coverage | Macro-F1 | Contradiction F1 |
| --- | ---: | ---: | ---: | ---: |
| Saved reference | 24/36 | 36/36 | .6698 | .5600 |
| A | 18/36 | 36/36 | .4634 | .1053 |
| B | 18/36 | 36/36 | .4799 | .1053 |
| C | 25/36 | 36/36 | .6979 | .6154 |
| TRAIN few-shot | 25/36 | 31/36 | .7639 | .7143 |

### Decision

**Retain the saved global MINIMAL reference and hold Phase 3B.** C improves
overall DEV and TRAIN scores, answers two more DEV hypotheses, and finds one more
TRAIN contradiction. Its contradiction F1 gain in the frozen sanity subset
(.5600 to .6154) does not extend to full TRAIN (.5385 to .5333) or DEV (.0000).
The few-shot variant improves full TRAIN contradiction F1 by .033, below the
frozen .05 threshold, and its 87.5% TRAIN coverage falls below the gate. On the
seven successful TRAIN documents, a secondary matched comparison shows 98/119
versus 93/119 and contradiction F1 .6061 versus .4545. The failed document remains
in the primary comparison. The few-shot benefit is a TRAIN signal, with no DEV
contradiction improvement. A and B materially regress on full TRAIN contradiction.

Decision formulation does affect results on this model, especially TRAIN recall.
The repeatable DEV errors with evidence present still suggest a semantic
reasoning limit in the tested setup. This single-model comparison cannot establish
an intrinsic capacity ceiling or separate it from the prompt. There is no basis
here to replace the reference or open a held-out run.

The campaign is in `local-data/contradiction-v2`. Config SHA256
`131566e151b48527b872d620b36a3c414815ee7bb155f63566a7f35334c07f5b`.
The additive result `scorer-only/results-v2.json` corrects a counter that initially
called the unavailable 17 rows duplicates. It leaves all predictions and scores
intact, preserves the first diagnostic artifact and keeps the provider failures
explicit. Final seal SHA256
`651602676338d28fda0c46684c77cbee198d69235c4a59f8a4ba95ac572012dc`.

### Verification

Focused suite: 68 passed. The full `uv run --frozen python scripts/verify.py`
gate passed **1,073 tests in 2,064.40s**, including PostgreSQL migrations and
integration, matching bounds, lock/dependencies, Ruff, format and strict mypy
(45 files). Isolated PostgreSQL restart passed four tests in 52.46s. The final
scorer-only counter correction was also checked directly against the two result
artifacts, focused tests, compilation and strict typing. Phase 0/2/3, both prior
development seals and the corrected experiment seal verified. External AI and
automation flags were disabled. The original reference implementation and the
production financial and retrieval paths retain their existing behavior.

Local logs: `local-data/verification/20261109T125744313054Z.log` and
`local-data/verification/isolated-restart-20261109T125743611303Z.log`.

## FINAL MODEL-CAPACITY ABLATION

The comparison pairs the saved 3.5 Flash-Lite MINIMAL global reference with one
new 3.5 Flash MINIMAL run. The latter is the same Free-tier model admitted for the
earlier hybrid comparison. It supports the same MINIMAL setting, allowing this
pass to test the global reference without changing the reasoning setting.
[Gemini thinking levels](https://ai.google.dev/gemini-api/docs/thinking).
[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

The 11 frozen reference jobs provide the three DEV and eight TRAIN documents,
17 hypotheses each, and the same direct global K20 plus adjacent context. The
zero-shot prompt, exact enum, aliases, validators, 32,768 input cap, 4,096 output
cap and existing development scorer are shared. The control uses its saved
predictions and attempt records. The runs were made at different times, so
latency is an observed comparison rather than a contemporaneous benchmark.
The stronger model uses the existing Flash transport pacing, excluded from
generation latency. Candidate identity and synthetic admission precede source
inference. The local manifest hash is
`490dab70710e7921c8865cd31d75317c4332a42fab5a7791def750c4050d9535`.

Promotion requires a correct DEV contradiction, a material TRAIN contradiction
F1 gain (the previous .05 criterion), and consistent grounded quality. The
previous 95% coverage and 25% unsupported-assertion boundaries remain the
quality checks. A small DEV overall accuracy gain alone does not qualify.

### Full-denominator results

All 11 source packet, prompt, schema and thinking hashes matched the saved
reference. Synthetic admission passed in the existing Free project. `E/C/N`
lists Entailment / Contradiction / NotMentioned F1. Unanswered hypotheses remain
in the denominator. The unchanged scorer counts absent predictions as
abstentions, and the transport table separately identifies provider failures.

| Split | Model | Grounded accuracy | Macro-F1 | E/C/N F1 | Coverage | Evidence F1 | Unsupported assertions |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| DEV | Flash-Lite | 42/51 (82.35%) | .5727 | .9180/.0000/.8000 | 49/51 (96.08%) | .7021 | 6/34 (17.65%) |
| DEV | Flash | 14/51 (27.45%) | .2616 | .5238/.0000/.2609 | 17/51 (33.33%) | .4077 | 3/14 (21.43%) |
| TRAIN | Flash-Lite | 106/136 (77.94%) | .7116 | .8392/.5385/.7573 | 136/136 (100%) | .7736 | 19/86 (22.09%) |
| TRAIN | Flash | 27/136 (19.85%) | .3286 | .2500/.3478/.3881 | 34/136 (25%) | .2015 | 6/20 (30%) |

| Split | Model | Malformed / missing label fields on returned rows | Unknown / outside-scope aliases | Terminal failed jobs | Failed generation attempts / attempts | Observed input/output tokens | Median/p95 generation s |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| DEV | Flash-Lite | 0/0 | 0/0 (54 declared) | 0/3 | 1/4 | 45786/3158 | 3.168/3.450 |
| DEV | Flash | 0/0 | 0/0 (18 declared) | 2/3 | 7/8 | 9445/1040 | 10.823/18.866 |
| TRAIN | Flash-Lite | 0/0 | 0/0 (97 declared) | 0/8 | 0/8 | 72651/8347 | 3.121/9.097 |
| TRAIN | Flash | 0/0 | 0/0 (25 declared) | 6/8 | 19/21 | 14947/2184 | 0.479/18.486 |

Flash had 20 HTTP 429 `RESOURCE_EXHAUSTED` and six HTTP 503 `UNAVAILABLE`
corpus attempts. The terminal failures account for 34 DEV and 102 TRAIN
hypotheses. The provider did not identify the exhausted quota dimension.
Generation latency includes failures and excludes pacing and token counting.
Flash's low TRAIN median is dominated by fast rate-limit responses and does not
measure successful inference speed. Observed tokens cover successful
responses only. The three successful Flash corpus calls reported 24,392 input
and 3,224 output tokens. The run made 29 corpus generations, one synthetic
generation and one model lookup, for 61 HTTP operations.

### Matched responses and decision

All annotated contradiction passages were fully selectable for both models on
the frozen global packets. Flash's single successful DEV document contained
zero of the two DEV contradiction examples. On its 17 hypotheses, Lite scored
15/17 and Flash 14/17. Flash's zero full-denominator DEV Contradiction F1 therefore
reflects missing responses on both positives. Its DEV contradiction reasoning
could not be assessed in this run.

On the two TRAIN documents with responses from both models, Lite scored 25/34
and Flash 27/34. Flash correctly identified four of the five gold contradictions
versus three for Lite, with Contradiction F1 .8000 versus .6667. This is a small,
provider-selected subset. The primary comparison retains all eight TRAIN
documents, including the six failures. It does not establish a consistent
capacity improvement across cohorts.

**Retain Gemini 3.5 Flash-Lite MINIMAL and hold Phase 3B.** Semantic reasoning
with available conflict evidence remains a limitation of the reference. The
stronger candidate's availability prevented a decisive cross-split capacity
comparison, and the paired TRAIN signal is insufficient for promotion. This
concludes the architecture and prompt tuning pass.

The additive scores and request audit are in `local-data/model-capacity-v1`,
development seal SHA256
`201730f1c4adc50d2a676bc879e902810622b77dc8da8775840b970127f0fef0`.
Historical Phase 0/2/3 and all prior development seals verified. This pass used
only an additive local configuration, the existing runner and the existing
scorer. No implementation change required a focused or regression rerun.
