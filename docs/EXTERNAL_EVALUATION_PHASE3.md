# External evaluation Phase 3 — final grounding hardening

2026-10-28. Completed and sealed. **Invoice-reference extraction improved on the
fresh slice; legal classification and evidence recall regressed substantially.**
Source-valid citations did not compensate for rejected legal outputs. Phase 2 v1
remains immutable history. There was no post-score tuning or inference rerun.

## Frozen selection and method

Source-ID plan SHA256:
`73fd2a85c27c2c7708d9a61590089a8c4e43385f28d6a72f5625a375894a1057`.
The external plan at `C:/ClearLedgerEval/external-runs/phase3-v1/evaluation-plan.json`
contains exact IDs, split/source hashes, seed and exclusion lists. Selection is the
lowest SHA256(seed|dataset|source-ID), excluding the entire v1 scored selection:
24 unused ContractNLI TEST documents/408 pairs and 100 unused DocILE VALIDATION docs.
No label/document-type stratification, difficulty replacement or new gold inspection.
Development uses application-owned minimal fixtures plus existing 3 DEV/8 TRAIN
adapter documents, never v1 final examples as a tuning loop.

Model remains Gemini 3.5 Flash-Lite. Two bounded plan/synthesis generations per
ContractNLI document; one invoice classification/ID-selection generation per eligible
DocILE document. Clearly out-of-scope/no-candidate documents abstain deterministically.
All100 remain in denominator. Unknown headings may receive typed classification in
the same request; the model cannot emit IDs for NON_INVOICE/UNKNOWN classification.

No retries, self-consistency samples, extra generations for score improvement or
model substitution. At most 165 generations including controls/smoke, one caller,
six total provider HTTP operations/minute. Per-request ceilings remain 32,768/4,096
legal input/output and 8,192/1,024 invoice input/output tokens. Thinking is MINIMAL,
no sampling parameters are added. Effective prompts/schemas, model, code and packet
hashes are frozen before scored inference, with count-token admission and reservations.

The operator's current task authorizes these fresh public-dataset evaluations;
prior dataset-holder/Free-tier decisions remain historical, not rewritten as a
general production-data consent. Existing Free project/key/model are retained.
No billing/project/AutoPay change. Account quotas are operator UI evidence, not
model-API exposed remaining allowance. Published pricing/quotas are checked against
official Google documentation. No private/sealed benchmark or production data.
Official references checked 2026-10-28: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
lists 3.5 Flash-Lite standard Free-tier input/output as free, and paid reference
rates of USD0.30/1M input and USD2.50/1M output including thinking.
[Model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
identifies the exact model alias. Request responses do not expose account invoices;
reported cost must distinguish this schedule/operator evidence from observed billing.

## Metrics and leakage boundaries

Original V1 scorers are not modified. ContractNLI reuses the original classifier,
unsupported-conclusion, unique-quote and union-character metrics exactly, including
its ambiguity rules. Accepted span-ID integrity is reported separately; it does
not replace poor classification/evidence recall with a synthetic100% accuracy claim.

DocILE keeps original NFC/outer-trim, ID-set P/R/F1, coverage and all-document
denominators. A selected canonical occurrence now deterministically supplies exact
text/token location, instead of asking an LLM to generate a free quote and rescuing
it by string search. Repeated values use the selected occurrence, never gold boxes.
Missing coordinates remain missing and cannot count as localized support. Native
conditional document_id KILE uses unchanged official 0.3.5 defaults, plus exact-text
results. It is not a full DocILE or all-invoice-fields score.

Prediction workers read source-only packets and cannot import gold/application DB
modules or access financial tools. Gold/source truth joins happen in a separate
scorer only after both prediction/selection artifacts are SHA256-sealed. No raw
documents, quotes, labels or sensitive predictions enter Git-facing reports.
V1 preservation uses metadata and existing sealed hashes; annotation contents are
not opened for pre-inference checksumming. Automatic approval review rejected that
proposed pre-seal gold read, and the step was omitted rather than bypassed.

## Implementation and development checks

[SOURCE_GROUNDING.md](SOURCE_GROUNDING.md) defines shared DTOs, candidate discovery,
admission, lexical retrieval, privacy/source binding and OCR fallbacks. Financial
authority, public financial APIs, existing migrations, outbox and graph nodes remain
unchanged. Legacy decoder/rehearsal responses remain compatible; live v3 requires
offered span IDs. No hidden chain-of-thought or financial approval is persisted.

Initial complete gate: 1019 passed, 2 failed in1759.12s. Both failures were historical
offline acceptance fixtures omitting v3 span IDs. Fixture response updated with
offered IDs; no assertion removed or weakened. Affected acceptance, graph and actual
API group: 13 passed in 121.65s. Current source/worker focused checks passed. Final
complete frozen gate passed: **1,029 tests in 1,833.27 seconds**, including PostgreSQL
migration/integration checks. Lock/dependencies, Ruff lint/format, strict domain
typing and matching-bound checks passed. This is test-suite runtime, not product
latency. Detailed log: `local-data/verification/20261027T222742635195Z.log`.
Separate isolated PostgreSQL restart check: 4 passed in 48.15s; log
`local-data/verification/isolated-restart-20261027T220756414376Z.log`.
Focused grounding plus existing external-evaluation tests: 130 passed; current
source/worker checks: 24 passed; strict evaluation-module mypy: 5 files passed;
domain mypy: 28 files passed; compile/import and original/frozen hash checks passed.

The next run reached the old 1,800-second test-runner wall-clock deadline; its
timeout log is preserved at `local-data/verification/20261027T215603058544Z.log`.
This is not evidence of an application/provider/database timeout. The already
running replacement was launched with a 3,600-second orchestration bound; the
persistent runner bound is now 2,700 seconds following the operator clarification.
No individual test, request/provider/DB timeout, financial limit, retry or model
configuration changed. A future runner timeout preserves sanitized partial output
and exits 124 instead of losing captured progress.

Synthetic admission: all three generations succeeded. Development smoke:
ContractNLI 1/3 accepted, 2/3 rejected for unoffered span IDs; DocILE 7/8 accepted,
1/8 exceeded the fixed input cap and made no generation call. These are retained
outcomes, not grounds for prompt changes or retries. No held-out gold was opened.
Inference config SHA256:
`dbe02bfcc4485a8751f7971650282bc4593883d561e439a12c684b5780880109`.

Provider generation, token-count and per-document paced wall time are retained
separately. Deliberate Free-tier pacing and regression-suite runtime are not product
latency measurements. A separate bounded product-path performance pass is deferred
until after this phase; no performance optimization is part of this task.

## Reproduction (one-shot; not authorization to rerun scored samples)

```powershell
.venv/Scripts/python.exe scripts/external_phase3_plan.py --runs C:/ClearLedgerEval/external-runs --source C:/ClearLedgerEval/external
.venv/Scripts/python.exe scripts/external_phase3.py prepare --runs C:/ClearLedgerEval/external-runs --source C:/ClearLedgerEval/external
.venv/Scripts/python.exe scripts/external_phase3.py freeze --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase3.py preflight --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase3.py smoke --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase3.py final --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase3.py seal --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase3_score.py --runs C:/ClearLedgerEval/external-runs --source C:/ClearLedgerEval/external
```

Exclusive artifacts prevent overwrites. Existing outputs are not deleted, samples
are not replaced, and failed generations are not retried. These datasets are legal
and business-document evaluations, not production AR accuracy. No private/sealed
ClearLedger benchmark is run automatically after this task.

## Fresh held-out results versus immutable v1

These are different source-ID-disjoint slices, not paired reruns or a statistical
causal estimate. Same primary model: `gemini-3.5-flash-lite`.

| Metric | Phase 2 v1 | Fresh Phase 3 |
|---|---:|---:|
| ContractNLI documents / hypotheses | 12 /204 | 24 /408 |
| Full-denominator accuracy | 81.86% | **37.50% (153/408)** |
| Answered-only accuracy | — | 69.23% (153/221) |
| Macro-F1 | 0.7588 | **0.3454** |
| Contradiction F1 | 0.5946 | **0.0870** |
| Unsupported assertive conclusions | 35/128 (27.34%) | **3/38 (7.89%)** |
| Exact-valid published quotes | 117/136 (86.03%) | 124/124 (100%) |
| Evidence character-overlap F1 | 0.5355 | **0.3996** |
| Joint correct-label/evidence F1 | 0.4990 | 0.1980 |
| DocILE documents | 50 | 100 |
| Invoice-ID precision / recall / F1 | 0.5357 /0.5000 /0.5172 | **0.8222 /0.6981 /0.7551** |
| Exact predicted-ID-set match | 30/50 | 81/100 |
| Accepted source localization | 21/28 (75%) | **42/45 (93.33%)** |
| Whole-source adapter failures | 5/50 | 0/100 |
| Native conditional location F1 | 0.1724 | 0.6481 |
| Native conditional location+exact-text F1 | 0.1379 | **0.6296** |

### External legal evidence-reasoning benchmark (ContractNLI)

All 408 hypotheses remain in the denominator. Final output validation rejected 11
documents, causing 187 abstentions; 221 answers remained. Plan validation failed 12/24
documents. Across 48 scored generations there were 23 output-validation failures
(12 plans, 11 syntheses), with zero provider/rate/JSON-parse failures. No deterministic
fallback answers were fabricated. The fixed policy downgraded 76 assertive outputs
to NotMentioned; lower unsupported-assertion rate comes with a severe coverage cost.
Downgrade reason counts overlap: 70 relevance-gate rejections, 5 explicit-conflict
rejections and 12 plan/relation inconsistencies. These are deterministic rejection
reasons, not proof that every rejected semantic assertion was wrong. Surface-term
relevance checking is particularly conservative on legal paraphrases.

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| Entailment | 0.9167 | 0.1813 | 0.3028 |
| Contradiction | 1.0000 | 0.0455 | 0.0870 |
| NotMentioned | 0.6448 | 0.6484 | 0.6466 |

Confusion counts (gold rows):

| Gold | Entailment | Contradiction | NotMentioned | Abstain |
|---|---:|---:|---:|---:|
| Entailment | 33 | 0 | 44 | 105 |
| Contradiction | 0 | 2 | 21 | 21 |
| NotMentioned | 3 | 0 | 118 | 61 |

Gold support counts are 182/44/182. Evidence character P/R/F1:
0.5390 /0.3175 /0.3996; joint label+evidence: 0.5547 /0.1205 /0.1980.

The model declared 284 plan and 269 synthesis span references. Respectively 24 and 21
were outside the allowed per-hypothesis pools: 45/553 (8.14%). These counts do not
distinguish a globally nonexistent ID from an existing ID offered for another
hypothesis. They must not be described as 45 proven fabricated citations.
All 124 published references were independently resolved again against frozen
source text/pools after sealing. Published citation integrity is 100%; raw membership
was only 91.86%. The 98% grounding goal is therefore not an unqualified model-success
claim. Source existence does not establish relevance, legal entailment or authenticity.

### DocILE invoice-reference slice

The 100-document denominator contains 67 tax invoices and 33 other documents, as
determined by the scorer only after seals. Secondary set scoring has 53 per-document
distinct reference targets: TP 37, FP 8, FN 16. Native scoring has 66 boxed field
instances; distinct-value sets and location instances are different denominators.
No gold value/box was available to candidate discovery or selection.

82 documents made one generation each; 14 abstained deterministically without a
call; 4 exceeded the frozen input cap and made zero generations. No provider,
rate-limit, JSON-parse or output-validation failures occurred on generated invoice
outputs. Coverage 43%, empty-output/abstention 57% (includes failures); exact-set
match 81%. Non-invoice false emissions 0. Published quotes 45/45 valid; 42/45 localized,
3 lacked trustworthy coordinates. Seven repeated-value emissions were collapsed
under existing set-scoring rules. Unsupported-field rate 8/45 (17.78%) uses the
frozen erroneous/unsupported-ID definition, not a claim about extra schema fields.

12 documents retained explicit partial/fallback provenance. No whole-source input
failed, but combined whole-source and input-cap failures are 4/100 (4%), not 0%.
Three candidate searches hit the 64-candidate completeness bound. These are retained
limitations; no source/limit was repaired after inference.

**Conditional document_id KILE on the mapped DocILE subset**, official 0.3.5,
67 invoice documents; original boxes/default evaluation behavior unchanged:

| Native mode | AP | Precision | Recall | F1 | TP /FP /FN |
|---|---:|---:|---:|---:|---:|
| Location | 0.4526 | 0.8333 | 0.5303 | 0.6481 | 35 /7 /31 |
| Location+exact text | 0.4400 | 0.8095 | 0.5152 | 0.6296 | 34 /8 /32 |

This is not full DocILE performance or extraction of totals, dates, vendors,
customers, payments, currencies, tax or line items.

## Calls, tokens, latency and failures

| Phase | Generations | Input | Output | Total | Generation median /p95 /max seconds |
|---|---:|---:|---:|---:|---:|
| Synthetic preflight | 3 | 1,162 | 230 | 1,392 | 1.981 /2.136 /2.136 |
| ContractNLI smoke | 6 | 82,846 | 6,865 | 89,711 | 4.898 /5.771 /5.771 |
| DocILE smoke | 5 | 9,151 | 145 | 9,296 | 1.497 /1.803 /1.803 |
| ContractNLI scored | 48 | 562,149 | 54,196 | 616,345 | 4.5175 /5.708 /6.296 |
| DocILE scored | 82 | 171,094 | 3,689 | 174,783 | 1.636 /2.905 /5.207 |
| **All** | **144 /165 cap** | **826,402** | **65,125** | **891,527** | — |

Provider-reported input/output/total are available for all 144 generations.
Separate thinking/cache categories are unavailable, not asserted zero. No retries
or extra score-improvement calls. Contract smoke had 4 rejected stages/2 accepted;
DocILE smoke had 5 model successes, 2 deterministic abstentions, 1 input-cap failure.
Across the entire run: 0 provider/rate/auth/timeouts, 0 JSON parse failures,
27 output-validation failures (legal), 5 input-cap rejections/zero generation.
There were 294 total HTTP operations, including count-token requests and one model
lookup; generation calls and total HTTP operations are distinct counters.
Full raw attempt metadata/usage and paced stage wall times remain local and sealed.
The table excludes deliberate pacing from generation latency and is not a measured
ClearLedger product/API end-to-end latency result. The separate product pass is pending.

Free tier is operator-confirmed; published standard input/output tariff is USD 0.
The API exposes no invoice/billed amount, so **observed billed USD is UNKNOWN**.
No billing/key/project change. Paid-price reference only: USD 0.4107331 using observed
tokens and published rates; this is not an actual charge.

## Goals and remaining weaknesses

Met on this slice: accepted exact quotes, unsupported-assertion rate below 12%,
invoice-ID P/R/F1 thresholds, and higher conditional native text-aware F1.
Missed: NLI macro/Contradiction/evidence-overlap goals, reliable raw span selection,
95% localization (93.33%), and combined 2% input-failure goal (4%). Accepted-citation
validity must always be coupled with 187 abstentions and 11 rejected legal documents.

The largest weakness is brittle per-hypothesis ID selection plus conservative
whole-output rejection and policy downgrades. Legal evidence recall/classification
became substantially worse, despite fewer unsupported assertions. Hashes and lexical
agreement are necessary integrity checks, not a deterministic legal entailment oracle.
Missing OCR geometry and dense candidate payloads remain bounded failure modes.
Product grounded-provider changes have actual-API/offline coverage; this external
evaluation is not a new live production remittance/AR reliability proof.
No post-gold compatibility fix, prompt tuning, scorer change or rerun was performed.

## Seals, safety and freeze

- Plan: `73fd2a85c27c2c7708d9a61590089a8c4e43385f28d6a72f5625a375894a1057`
- Config: `dbe02bfcc4485a8751f7971650282bc4593883d561e439a12c684b5780880109`
- Contract predictions: `742fc8ae2cc8c25f752ff5348d8fd4a7dfa662f89c2df230192aaeb643d80055`
- DocILE predictions: `0ecf3f1f7f4a9cea7d6a164c578029f4abd3b80604d4299b200d9ac54bb71854`

Run root: `C:/ClearLedgerEval/external-runs/phase3-v1`. Both prediction/grounding
seals existed before any gold interpretation. `seals/complete-run.json` additionally
sealed 318 prediction/request/usage/config/source-manifest metadata files. Post-score
verification confirms all these bytes unchanged. Scoring/aggregate.json,
completion-metadata.json and docile-native-summary.json contain exact machine results.
`seals/scored-results.json` seals the ten completed score/provenance output files;
no prediction, score, configuration or existing hash was altered to create it.
V1 artifact set/metadata and existing critical sealed hashes verified unchanged;
original Phase0 plan still matches its published hash. Old scorers and sample IDs
were not changed. Raw source/quotes/answers remain outside Git.

Implementation checkpoint: `9fbf097826af03086fab3abff077bb15e2bc563e`. Config captured
the reviewed source bytes before that commit; a separate checkpoint mapping confirms
all frozen code hashes match it without mutating config. Production graph shape,
financial authority, APIs, migrations, Director/outbox and maker-checker unchanged.
Evaluation workers had no DB or financial tools; allocations, journals, postings,
balance mutations, write-offs and finance approvals are all 0. Actual-API regression
snapshots independently verify financial non-mutation. External AI/investigation
and both extraction automation flags are disabled. Private AR benchmark, RecBench,
UI, README and deployment were not run/changed. Backend feature expansion is frozen.
Private/sealed AR execution requires a separate explicit instruction.

Safe public claims are limited to these exact slices/metrics and tested safety
boundaries, including the legal regression. Neither dataset establishes production
AR accuracy, bank reconciliation accuracy, tax compliance, customer ROI, financial
posting accuracy or production readiness.
