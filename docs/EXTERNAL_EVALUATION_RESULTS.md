# External evaluation results — frozen Phase 2 v1

Completed 2026-10-28. Model: **gemini-3.5-flash-lite** (the same identifier was
returned in every generation's provider metadata). No model substitution, retries,
score-driven tuning, sample replacement or manual prediction repair.

## Authorization and configuration

The historical `STOPPED_AT_PROVIDER_PAYLOAD_TERMS_GATE` below is **RESOLVED by
explicit operator review and payload attestation**. Dataset rights/API processing
are USER-RESOLVED/AUTHORIZED; Free-tier payload admissibility is
OPERATOR-REVIEWED/AUTHORIZED for these frozen samples only. See the additive
[authorization record](EXTERNAL_EVALUATION_AUTHORIZATION.md). Free/Paid data
conditions are not identical. This is not permission for production, customer,
private, sealed-benchmark or unrelated data. No raw sources or evidence quotes
are included in this Git-facing report.

Authentication/model lookup and all three synthetic schema-admission generations
passed. Current tier/quota evidence is operator AI Studio confirmation: Free tier,
15 RPM, 250,000 input TPM, 500 RPD. Displayed usage 3 RPM/approximately 2,350 TPM/30 RPD
was not treated as exact consumed daily allowance. Account tier/remaining quota
are not exposed by model lookup. No billing, AutoPay, key or project changes.

The operator amended pacing only to six total HTTP operations/minute, one caller,
ten-second minimum request-start spacing, below 15 RPM. Original plan/checksum,
prompts, schemas, model, token caps, scorer formulas and failure handling stayed
frozen. Requests used JSON MIME plus original response JSON schemas, MINIMAL
thinking and omitted sampling parameters. HTTPX had retries=0, redirects disabled,
no SDK retry layer or proxy-environment middleware. Count-token and generation
requests shared pacing. Fixed source-only packets were the only dataset inputs.

## Smoke and execution integrity

- ContractNLI smoke: 3 frozen dev documents / 51 hypotheses, 6 generations; all plans
  and all answers parsed. Two documents had source-quote failures. No smoke accuracy
  is presented as final performance; no tuning followed.
- DocILE smoke: 8 frozen train documents, 8 generations, all typed responses parsed
  and source localization checks completed without reported failures.
- Final predictions for **both** datasets were completed and SHA256-sealed before
  the separate scoring process read any gold. Gold readers were not imported by
  the inference worker. Original predictions were never modified after sealing.
- One local preflight launch failure occurred before any HTTP call: a Windows
  environment filter omitted SYSTEMROOT, causing TLS-context construction failure.
  Offline reproduction/regression proved the fix. Original failed config is retained;
  synthetic admission revision 2 passed. This was not a failed scored request/retry.
- No scorer semantics changed after predictions. The pre-frozen DocILE denominator
  bridge was independently tested equivalent to the original missing-output metric;
  rejected OCR inputs were not represented by invented source packets.

## External legal evidence-reasoning benchmark (ContractNLI)

Frozen test scope: **12 documents / 204 hypothesis pairs**, three-way legal/NDA
classification. This is not an AR benchmark or evidence of production AR accuracy.

| Metric | Result |
|---|---:|
| Full-denominator accuracy | 81.86% (167/ 204) |
| Answered-only accuracy | 81.86% (204 answered) |
| Macro F1 | 0.7588 |
| Abstentions / missing answers | 0 /0 |
| Provider / parse / schema failures | 0 /0 /0 |
| Deterministic fallback pairs | 0 |
| Unsupported conclusions | 35/128 assertive predictions (27.34%) |
| Exact source quote validity | 117/136 (86.03%); 19 missing quotes |
| Evidence character-overlap P/R/F1 | 0.9093 / 0.3795 / 0.5355 |
| Joint correct-label evidence P/R/F1 | 0.9339 / 0.3404 / 0.4990 |

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| Entailment | 0.7664 | 0.9318 | 0.8410 |
| Contradiction | 0.5238 | 0.6875 | 0.5946 |
| NotMentioned | 0.9737 | 0.7400 | 0.8409 |

Confusion matrix, gold rows and prediction columns:

| Gold | Entailment | Contradiction | NotMentioned | Abstain | ProviderFailure |
|---|---:|---:|---:|---:|---:|
| Entailment | 82 | 4 | 2 | 0 | 0 |
| Contradiction | 5 | 11 | 0 | 0 | 0 |
| NotMentioned | 20 | 6 | 74 | 0 | 0 |

The frozen unsupported-conclusion denominator is predicted Entailment/Contradiction;
wrong assertive labels count as unsupported. Quote validity establishes literal
source occurrence, not entailment or authenticity. Raw evidence overlap is scored
only on gold Entailment/Contradiction pairs; NotMentioned has no positive evidence
target. Joint scoring treats wrong-label evidence as empty. No source boundaries
were obtained from gold during prediction. Seven test documents had at least one
invalid quote; all predictions and invalid quotes were retained for honest scoring.

## DocILE — all-50 secondary results

Frozen scope:50 validation documents (36 tax invoices,14 other document types).
Only `document_id` → `invoice_references[].value` is supported. No totals, dates,
vendors, customer identity, payment-reference/UTR, tax or line-item claims.
Normalization remains NFC and outer trim only; case, punctuation, leading zeroes
and internal whitespace are preserved.

| Metric, complete frozen 50 denominator | Result |
|---|---:|
| Invoice-ID micro precision / recall / F1 | 0.5357 / 0.5000 / 0.5172 |
| TP / FP / FN (unique source-grounded IDs per document) | 15 /13 /15 |
| Exact predicted-ID-set match | 30/50 (60.00%) |
| Extraction coverage | 25/50 (50.00%) |
| No emitted IDs | 25/50 (20 model empty outputs +5 input failures) |
| Strict adapter/input failures | 5/50 (10%):2 EMPTY_OCR_PAGE,3 INVALID_OCR_WORD |
| Documents actually model-called | 45 |
| Provider / parse / schema failures on model calls | 0 /0 /0 |
| Non-invoice false emissions | 1 ID across 14 non-invoice documents |
| Exact quote/source localization validity | 21/28 unique fields (75%);7 ambiguous |
| Localization-failure documents | 7/45 model-called documents |
| Duplicate fields | 5, excluded by frozen unique-value rules |
| Frozen unsupported-field count/rate | 13/28 (46.43%) |

All five bad inputs received zero model calls and stayed in recall, coverage and
exact-set denominators as missing outputs. No OCR repair, replacement or dropping.
Exact-set match includes empty gold sets and must not be read as invoice recall.
The unsupported-field metric counts incorrect or ungrounded invoice IDs, not
attempts at unsupported field types; the typed schema exposes only invoice IDs.
Literal source occurrence is not proof of the correct semantic document ID.

### Conditional document_id KILE on the mapped DocILE subset

Official `docile-benchmark==0.3.5` completed successfully over the 36 mapped tax
invoice documents. Native evaluator default IoU threshold 1.0 was preserved.
Original gold boxes/values were used in a separate scorer-only view. Other printed
field rows are empty/unscored; this is **not full DocILE performance**.

| Native variant | AP | Precision | Recall | F1 | TP / FP / FN |
|---|---:|---:|---:|---:|---:|
| Location | 0.04704944 | 0.2500 | 0.1316 | 0.1724 | 5 /15 /33 |
| Location + exact text | 0.02923217 | 0.2000 | 0.1053 | 0.1379 | 4 /16 /34 |

Native annotation-instance counts differ from secondary unique-ID sets. The frozen
exporter uses score 0 when model confidence is absent; AP is not a calibrated
confidence-ranking claim. No dummy prediction was inserted or annotation-assisted
localization performed. Official result/log remain local under `scoring/`.

## Calls, actual tokens and latency

**86 generation attempts total**, including three synthetic controls; zero retries.
83 generations used dataset packets:30 ContractNLI (6 smoke +24 final),53 DocILE
(8 smoke +45 final). Eighty-six token counts plus 86 generations plus one model GET
=173 provider HTTP operations. No RecBench or future evaluation run was made.

| Phase | Generations | Provider input tokens | Provider output/candidate tokens | Provider total tokens |
|---|---:|---:|---:|---:|
| contract_smoke | 6 | 30,435 | 10,905 | 41,340 |
| docile_smoke | 8 | 13,347 | 138 | 13,485 |
| contract_final | 24 | 82,964 | 39,420 | 122,384 |
| docile_final | 45 | 55,394 | 2,275 | 57,669 |
| preflight_contract | 2 | 290 | 171 | 461 |
| preflight_docile | 1 | 89 | 60 | 149 |
| **Total** | **86** | **182,519** | **52,969** | **235,488** |

All 86 generations exposed input/candidate/total usage. Thinking and cache token
categories were absent in 86/86 responses: **UNAVAILABLE**, not claimed zero.
Original generation ceiling 88 and input/output ceilings 1,458,176/182,272 were
not exceeded. No extra requests were spent improving scores.

Nearest-rank p95; provider latency excludes pacing, document latency includes token
counting, generation and intentional pacing. DocILE document timing covers 45 actual
model-called documents; five zero-call input failures have no provider latency.

| Final latency | Median | p95 | Max |
|---|---:|---:|---:|
| contract_final provider generation | 5.177s | 6.806s | 7.110s |
| contract_final document, including pacing | 39.465s | 41.628s | 41.628s |
| docile_final provider generation | 1.277s | 1.948s | 8.619s |
| docile_final document, including pacing | 19.983s | 20.951s | 26.668s |

Current official [pricing](https://ai.google.dev/gemini-api/docs/pricing), retrieved
2026-10-28, lists Free-tier input/output as free of charge for this model (paid
standard reference prices USD 0.30/2.50 per million input/output-including-thinking
tokens). The operator confirmed Free tier; no billing was enabled/changed. Expected
Free-tier API charge is USD 0 under that tariff. **Actual billed USD is UNKNOWN /
not independently invoice-verified**: generation metadata does not expose charges
or account billing. Token usage above is observed, not a cost estimate. See
[provider terms](https://ai.google.dev/gemini-api/terms) and historical privacy
analysis; Free/Paid treatment is not represented as equivalent.

## Failures, boundaries and limitations

- Authentication, rate-limit, timeout, provider, parse and typed-output validation
  failures: **0** among the 86 real generation attempts. These transport outcomes
  are not a claim of correct predictions.
- ContractNLI:19 invalid exact quotes and 35 unsupported assertive conclusions;
  evidence recall 37.95% and contradiction F1 approximately 0.5946 are weaknesses.
- DocILE:5 unprojectable source inputs,7 ambiguous localized fields,13 incorrect
  or ungrounded ID emissions; conditional native text-aware F1 only 0.1379.
- No final samples were removed. Five DocILE inputs were not model-evaluable but
  remained secondary failures; all 204 ContractNLI pairs and all 50 DocILE documents
  stayed in denominator. Native evaluation was computable over its 36-document scope.
- No human/financial authority was granted to model output. **Zero** allocations,
  journal entries, receipt applications, postings, balance mutations, write-offs,
  settlements or finance approvals: the isolated transport had no application
  imports, database connection, production credentials or financial APIs. This is
  an isolation-based observation, not an independent audit of a production database.
- Production code, migrations, UI, both pilot ZIPs, private/sealed ClearLedger
  benchmark, trusted operator, chronological image and RecBench remained untouched.
- Single model, small frozen slices, one run, no retries; behavior can vary. Real
  public/business/legal text is not synthetic. This does not establish statistical
  production reliability or real-customer financial performance.

The biggest measured weakness is evidence grounding/localization rather than HTTP
operation: unsupported legal assertions remain material, and native DocILE spatial
matching is much weaker than ID-set correctness. No tuning follows these scores.

## Hashes and reproduction

| Artifact | SHA256 |
|---|---|
| Original Phase0 plan | `a83dc857f3f4ee8d0f6468fd945358504b59173e4ad55f53845bec3c7d00589d` |
| Final inference configuration | `7b11a670df8852455a7b19e9ae035e6f438bb3384afc9b5b6c0e00455c450a60` |
| ContractNLI final predictions | `1590d79e898b2282aa5e221087511bf03de2a4e7be628d74853602b08b02aea9` |
| DocILE final predictions | `56cdfeb7fb038e9c2dece5e58eef0ff17e2f282402b19e4f939dd3fe738c5cd2` |

Configuration freezes Git/code reference `4b6b461`, exact original request-spec
hashes, prompts/schema hashes, source-packet hashes, model/configuration and limits.
The original frozen plan and source/spec/scorer hashes were checked unchanged.
Pacing is an additive amendment, not a rewrite of the plan/checksum. Original failed
preflight configuration, historical provider stops and all attempt markers remain.

Machine artifacts are under `C:/ClearLedgerEval/external-runs/phase2-v1/`:
`config/`, `preflight/`, `inputs/`, `attempts/`, `logs/metadata/`, `predictions/`,
`seals/`, `scoring/`. `scoring/aggregate.json` has exact machine metrics;
`docile-official-summary.json` is an aggregate view of the native result.
Raw prediction quotes/source packets remain local and are not committed.

[Implementation and exact execution commands](EXTERNAL_EVALUATION_IMPLEMENTATION.md)
cover prepare → synthetic preflight → freeze → smoke → final → seal → score.
Commands are one-shot/exclusive, not permission to rerun failed scored examples.
No inference reruns are required to inspect already sealed scores.

Verification:106 focused offline tests passed; Ruff lint/format, strict mypy
(11 source files), compilation/import and frozen-hash checks passed. No production
regression/database/browser suite was run because this task changes only evaluation
helpers and documentation. A full production-readiness claim is not inferred.

## SAFE TO CLAIM PUBLICLY

- The evaluation-only Gemini 3.5 Flash-Lite adapter achieved 81.86% accuracy and
  0.7588 macro-F1 across 204 frozen ContractNLI test hypotheses. This is external
  legal/NDA evidence reasoning, not AR accuracy.
- On the frozen 50-document DocILE validation slice, supported source-grounded
  invoice-reference extraction achieved precision 0.5357, recall 0.5000, F1 0.5172,
  retaining five input failures. This is not complete invoice extraction.
- 117/136 ContractNLI evidence quotes resolved literally to source text; this is
  citation validity, not a guarantee that the conclusion follows.
- The bounded evaluation made 86 no-retry generations with no financial application
  mutations and no autonomous financial authority.

## NOT SUPPORTED BY THIS EVALUATION

Production-ready status; customer productivity/manual-work improvements; real-world
AR accuracy; full invoice extraction; complete DocILE benchmark performance; real
bank reconciliation; financial posting accuracy; customer ROI; fully autonomous
reconciliation; verified USD 0 invoice charge; statistically established production
reliability; source authenticity or valid financial decisions based only on quotes.

---

## Historical 2026-10-28 — Free-tier authorization recorded; no scored results

The operator now explicitly authorizes Free-tier API processing for the frozen
public DocILE/ContractNLI samples and accepts its data-treatment conditions. Dataset
rights remain USER-RESOLVED; paid service is no longer an operator requirement.
See the [additive authorization amendment](EXTERNAL_EVALUATION_AUTHORIZATION.md).
No billing/AutoPay/project/key changes are requested or made.

Current official [Unpaid Services terms](https://ai.google.dev/gemini-api/terms)
retain a separate sensitive/confidential/personal-information restriction. Existing
heuristic source screening does not establish that every unchanged payload complies.
No provider exception has been established. Status is therefore
**STOPPED_AT_PROVIDER_PAYLOAD_TERMS_GATE**, not stopped merely for using Free tier.
The dataset-holder authorization is recorded, not rejected or re-investigated.

| Requested observation | Current result |
|---|---|
| Exact model actually used | NONE; intended alias remains gemini-3.5-flash-lite |
| Free-tier/synthetic preflight | NOT RUN; account tier/quotas/model admission not verified |
| ContractNLI smoke/final204 pairs | NOT RUN; no classification or evidence metrics |
| DocILE smoke/final50/native conditional KILE | NOT RUN; no extraction/localization metrics |
| Model calls/input/output/total tokens |0/0/0/0; none observed from provider |
| New API charges from this attempt |No calls; no provider invoice/billing check or monetary inference from assumed Free tier |
| Provider/rate/schema/citation failures |NOT OBSERVED; zero attempts is not a successful test |
| Prior DocILE input failures |5 retained; no repair/replacement/new model calls |
| Prediction/config hashes |NOT CREATED; no premature inference freeze or seals |
| Frozen artifacts/production/financial state |No changes; no application/DB/financial operation executed |

No scored public-performance claim is supported. The strongest demonstrated result
is preservation of the frozen evaluation and source boundary while recording the
operator's revised authorization. No model-quality weakness was measured; the
unresolved issue is payload admissibility under current provider terms.

No billing setup is requested. The frozen v1 Free-tier run needs an applicable
provider clarification or local confirmation that its complete unchanged payloads
meet the restriction. Redaction/subsetting is not performed as a workaround.

## 2026-10-27 — historical paid-project verification stop

2026-10-27. **STOPPED_AT_PROVIDER_BILLING_GATE. No model results exist.**

The [user authorization amendment](EXTERNAL_EVALUATION_AUTHORIZATION.md) resolves
dataset-use/API-processing rights for this experiment, subject to provider terms.
Historical rights/privacy findings are preserved. The configured development key's
billing status is unknown; an independently verified suitable paid evaluation
project/key is not available in current scoped configuration. No cloud changes
or document/model/token-count requests were made.

| Requested result | Status |
|---|---|
| External legal evidence-reasoning benchmark (ContractNLI),204 pairs | NOT RUN; no accuracy/F1/evidence/latency measurement |
| DocILE all50 secondary metrics | NOT RUN; no precision/recall/F1 or provider measurement |
| Conditional document_id KILE on the mapped DocILE subset | NOT RUN; official evaluator not invoked in Phase2 |
| Synthetic admission and adapter smoke | NOT RUN; waiting at the prior billing gate |
| Model calls / token usage / new token charges | 0 /0 /USD0 |
| Provider or citation failures in Phase2 | None observed because no calls occurred; not evidence of reliability |
| Previously known DocILE input failures |2 empty-page +3 invalid-word cases retained; no calls or repair |

The Phase0 plan/checksum, IDs and Phase1 scorer formulas are unchanged. No
inference configuration was frozen prematurely, no predictions were created or
sealed, and no gold/source document processing was performed in this task. No
production/UI/financial mutation or private benchmark access.

Machine artifacts under `C:\ClearLedgerEval\external-runs\phase2-v1\` record the
authorization, additive rights/provider transition and blocked provider gate.
They are **not scored results**. No placeholder metric is represented as zero
accuracy or a successful prediction.

Single setup action and current provider references are in the amendment. After
that gate is satisfied, remaining preflights and transport/freeze/smoke/scored work
must still be completed, within the existing maximum token-charge allocation and
without retries. No model-quality weakness can be inferred from an unexecuted run.

### Historical SAFE TO CLAIM PUBLICLY — 2026-10-27

- The dataset holder authorized this specifically scoped evaluation.
- Frozen source-only adapters/scorers were verified offline in prior phases.
- The paid-provider gate stopped execution before unverified document transmission.

### Historical NOT SUPPORTED BY THIS EVALUATION — 2026-10-27

- Any scored ContractNLI/DocILE model metric or held-out model-performance claim.
- Production AR accuracy, bank reconciliation accuracy, customer ROI or saved work.
- Full DocILE/invoice extraction performance, model citation reliability or model-run
  financial safety. No model/application financial operation was executed here.

## Historical pre-inference public-claim status

No scored model-performance claim: the current attempt has produced no scored
ContractNLI/DocILE predictions. Operator authorization and offline gate checks are
not substitutes for an executed external model evaluation.

## Historical pre-inference unsupported claims

- Production-ready status.
- Customer productivity improvement or reduction in manual work.
- Real-world AR accuracy.
- Full invoice extraction accuracy.
- Complete DocILE benchmark performance.
- Real bank reconciliation accuracy.
- Financial posting accuracy.
- Customer ROI.
- Fully autonomous reconciliation.
- Model citation reliability, actual Free-tier performance or statistical production
  reliability. No live run was performed; no score or actual billing is inferred.
