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
