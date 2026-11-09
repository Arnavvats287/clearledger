# Phase 3B final fresh external evaluation

Phase 3B is a held-out evaluation on public ContractNLI and DocILE data. Its
grounded output has no financial authority. Phase 2 and Phase 3 used different
held-out slices. Comparisons across phases are descriptive, and the slices do
not support a paired estimate of the effect of the architecture or prompt.

## Frozen scope and configuration

The selector ordered unused IDs by ascending SHA256 of the canonical JSON tuple
`[seed, dataset, source ID]`. The seed was `clearledger-final-external-phase3b-v1`.
It excluded the Phase 2 and Phase 3 scored and adapter IDs, recorded development
IDs, and disjoint TRAIN demonstration IDs. Source selection decoded only document
IDs from the pinned ContractNLI test JSON layout and the DocILE validation ID list.
It sealed **24 ContractNLI TEST documents / 408 hypotheses** and **100 DocILE
VALIDATION documents** before projecting source text. The new samples were drawn
from pools of 87 unused ContractNLI and 350 unused DocILE IDs.

| Setting | Frozen value |
| --- | --- |
| Model and thinking | `gemini-3.5-flash-lite`, `MINIMAL`, existing authorized Free project |
| ContractNLI evidence | Direct global K20, one adjacent span on each side when available on the same page, deduplicated canonical union |
| ContractNLI batch and prompt | 17 hypotheses per document, selected zero-shot `SELECTION_INSTRUCTION` |
| ContractNLI output | Exact `Entailment` / `Contradiction` / `NotMentioned` provider enum, strict per-item validation and request-local aliases |
| ContractNLI token caps | 32,768 input and 4,096 output including thinking |
| DocILE extraction | Existing candidate-first `document_id` mapping, occurrence-specific compact packet of up to 64 candidates, including up to 8 bounded PDF text candidates |
| DocILE source policy | OCR first, PDF text fallback tied to PDF digest and canonical text ranges, absent geometry remains absent |
| DocILE token caps | 8,192 input and 1,024 output including thinking |
| Transport | One caller, at least 10 seconds between HTTP operations, no retries, one generation per eligible document |
| Failure handling | All frozen IDs retained. No model call for out-of-scope, empty candidate pool or unavailable source. No sample replacement. |
| Scoring | Existing ContractNLI scorer, DocILE all-document value and localized set scores, official `docile-benchmark` 0.3.5 conditional KILE |

The freeze records the source split hashes, exclusions, selected IDs, code and
scorer hashes, and SHA256 for each source packet and admitted OCR/PDF file.

| Artifact | SHA256 |
| --- | --- |
| Source selection | `bb8f20b9559d13e82a8c130ef6016fe077dc082dabc6277566c35480ba8173d6` |
| Evaluation plan | `2ee162ed6fd6166b387c16f2dcb7a57d2ff75b02c29c137190e1815359e38b0c` |
| Inference configuration | `59dc054dca9557e6beeab42a5f8e397d98d5ead2fdf93b67a9626fb0d5a306ff` |
| Source manifest | `664e8de1d9a2dec19898d245107bdf9c9ec599b49a1c19e2e7e08cb9e37b3a99` |
| ContractNLI prompt | `e1e11debee729cebae0e73362022bf85fb6aa68bef2198d02baf5495100405bb` |
| ContractNLI provider schema | `9f4dc71606fdbc29c9272e29f6867b198348461934827ec7391926823b3bdcce` |
| DocILE prompt | `54856006dcf8ef361219231651b11014aa41fd9ec79adfe30709a8b02c9df1c2` |
| DocILE provider schema | `8a0f684634251924b8e1c2a4f7b27c502d6b22401b3ff81b58bc0de8fa2a3654` |
| Phase 3B scorer | `1eb4400e55da6180c091f6a2f98b0d1c4be192476dd3b642d66abf1b5e09d9d0` |

Artifacts are stored under `C:/ClearLedgerEval/external-runs/phase3b-v1`.
The isolated worker receives source-only packets and the evaluation credential
through stdin. Gold readers are in the separate scorer. Both prediction sets
and the offered DocILE candidates must verify before it accesses annotations.

## Sealed prediction and result hashes

| Artifact | SHA256 |
| --- | --- |
| ContractNLI predictions | `364531bbaf08b9ec4476683414b26ff54b90f0a8372b46a4b126b5778d84eaa0` |
| ContractNLI seal | `3fd5ee7eff354073523750d4c29a4b5a65670831bd7c7a6ece26e5c84c6248ab` |
| DocILE predictions | `4e9569e6a02eca034194c07915ec8cb010d9d67e2a3d68d7c482472634194147` |
| DocILE seal | `654e668a84361a3eadde3f617bdf569c7906592bf2091a1c59accb3d15289e1e` |
| Aggregate scores | `b9f1244cd3897aee3932f880fc4e13faef7c16860fa6ad2fd82917b406f153bf` |

Both prediction seals were written and checked before any scorer annotation
reads. The scorer recorded annotation hashes and verified the prediction seals
again at the end. The original Phase 2 and Phase 3 artifacts and all four prior
development seals verified. The [sealed plan](C:/ClearLedgerEval/external-runs/phase3b-v1/evaluation-plan.json)
contains the exact IDs and exclusions.

## External legal evidence-reasoning benchmark (ContractNLI)

Full-denominator accuracy was **303/408 (74.26%)**, answered-only accuracy
**303/386 (78.50%)**, and macro-F1 **.6782**. Grounded coverage was **386/408
(94.61%)**. There were five item abstentions due to strict typed validation and
17 provider-failure hypotheses from one HTTP 503 document. There was no
validation cascade. A single rejected item did not discard the other answers.

| Gold class | Support | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Entailment | 197 | .7890 | .8731 | .8289 |
| Contradiction | 46 | .6957 | .3478 | .4638 |
| NotMentioned | 165 | .7931 | .6970 | .7419 |

| Gold class | Entailment | Contradiction | NotMentioned | Abstain | Provider failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| Entailment | 172 | 4 | 12 | 0 | 9 |
| Contradiction | 8 | 16 | 18 | 2 | 2 |
| NotMentioned | 38 | 3 | 115 | 3 | 6 |

- Unsupported assertions were **53/241 (21.99%)**. This counts assertive
  predictions whose class disagrees with gold.
- Evidence character-overlap precision/recall/F1 were **.3632/.5811/.4470**.
  Joint correct-label evidence precision/recall/F1 were **.3616/.5573/.4386**.
- Of 625 declared alias references, none were unknown or out of scope. The
  accepted 623 references resolved to their canonical IDs. A separate audit
  verified **623/623** published quote ranges against the exact source text.
  The unchanged string scorer accepted **616/623 (98.88%)** and marked seven
  repeated-text quotes ambiguous. Those seven do not count in its evidence
  overlap. Canonical range integrity does not prove semantic relevance.
- Contradiction remains the weakest class. The selectable global packet union
  covered all **46/46** gold contradiction passages, including all 23,604
  annotated characters, yet only 16 positives were correctly classified.

## DocILE invoice-reference extraction

The all-document denominator includes **67 tax invoices and 33 other documents**.
For the mapped invoice identifier, precision/recall/F1 were **.6190/.6842/.6500**
(39 TP, 24 FP, 18 FN). Localized-only value set scores were identical. Exact-set
match was **72/100**, coverage **51/100**, and empty-output/abstention **49/100**
including terminal failures. Two values were emitted on non-invoices.

| Diagnostic | Result |
| --- | ---: |
| Gold distinct per-document values available in offered packets | 44/57 (77.19%) |
| Gold occurrences available with exact value, page and bbox IoU ≥ .5 | 54/67 (80.60%) |
| Candidate pools flagged incomplete | 8/100 |
| Exact selected source quotes | 72/72 |
| Selected occurrences with source geometry | 70/72 (97.22%) |
| Whole-source input failures | 0/100 |
| Partial OCR / PDF text available | 11/100 / 96/100 |
| PDF text candidates offered / selected | 172 / 2 |
| Non-invoice false emissions | 2 distinct values |

The two PDF text selections retained exact PDF ranges and no fabricated boxes.
They did not increase the correctly extracted distinct-value total. There were
94 accepted model outputs, three terminal HTTP 503s, two input-cap rejections
before generation, and one deterministic out-of-scope abstention. There were no
model output-validation failures or rejected candidate aliases in this slice.

**Conditional document_id KILE on the mapped DocILE subset** used the pinned
official 0.3.5 evaluator on the 67 tax-invoice documents and original gold boxes.
AP is shown at the precision printed by the official CLI.

| Native mode | AP | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| Location | .571 | .6912 | .7015 | .6963 | 47 / 21 / 20 |
| Location + exact text | .535 | .6618 | .6716 | .6667 | 45 / 23 / 22 |

The value-set score and the official localization score use different units.
The official score applies to the mapped identifier only. Totals, dates,
vendors, customers, payment references, tax and line items are outside its scope.

## Transport, usage and verification

| Scope | Generation attempts | Observed input / output / total tokens | Generation median / p95 / max seconds |
| --- | ---: | --- | --- |
| Synthetic controls | 2 | 615 / 225 / 840 | 1.674 / 2.143 / 2.143 |
| ContractNLI scored | 24 | 231,958 / 25,687 / 257,645 | 3.752 / 8.021 / 9.001 |
| DocILE scored | 97 | 200,788 / 2,663 / 203,451 | 1.564 / 6.230 / 7.513 |

The run made 123 generations, 125 count-token calls and one model lookup. The
scored total was 461,096 reported tokens, excluding failed-call usage that the
provider did not expose. Separate thinking tokens and billed USD were unavailable.
There were four HTTP 503s, zero HTTP 429s, zero HTTP 400s and zero retries.
Provider generation latency excludes count-token calls and deliberate pacing.

`uv run --frozen python scripts/verify.py` passed **1,076 tests in 2,242.80s**,
including PostgreSQL integration and migrations, dependency/lock, matching bounds,
Ruff, formatting and strict mypy (48 files). The focused suite passed 62 tests.
Compilation, history and Phase 3B seal checks passed. The local verification log
is `local-data/verification/20261109T142814414127Z.log`.

The evaluation worker had no financial database or financial action access.
Allocations, postings, journals, balance mutations, write-offs and approvals were
all zero. External AI and both automation flags were verified disabled in the
product configuration. Billing and project settings were untouched.

## Cross-slice comparison and public claim

All columns are different held-out ID slices. Changes cannot be attributed to
any one configuration change or read as a paired causal estimate.

| Metric | Phase 2 v1 | Phase 3 | Phase 3B |
| --- | ---: | ---: | ---: |
| ContractNLI documents / hypotheses | 12 / 204 | 24 / 408 | 24 / 408 |
| Accuracy | 81.86% | 37.50% | 74.26% |
| Macro-F1 | .7588 | .3454 | .6782 |
| Contradiction F1 | .5946 | .0870 | .4638 |
| Unsupported assertive conclusions | 35/128 | 3/38 | 53/241 |
| Exact-valid quote strings | 117/136 | 124/124 | 616/623 |
| Evidence character-overlap F1 | .5355 | .3996 | .4470 |
| DocILE documents | 50 | 100 | 100 |
| Reported invoice-ID P/R/F1 | .5357/.5000/.5172 | .8222/.6981/.7551 | .6190/.6842/.6500 |
| Exact ID-set match | 30/50 | 81/100 | 72/100 |
| Source localization validity | 21/28 | 42/45 | 70/72 |
| Conditional native location+exact-text F1 | .1379 | .6296 | .6667 |

Phase 3's reported invoice-ID score requires localization. Phase 3B reports
both value-only and localization-gated sets, which coincide on this slice.

The strongest defensible public claim is that, on this fresh 24-document
ContractNLI slice, the grounded evaluator answered 386 of 408 hypotheses and
got 303 correct, with all 623 published source ranges independently verified.
Separately, on the fresh 100-document DocILE slice, the invoice-reference task
achieved .6500 all-document F1 and .6667 conditional document_id location+text
KILE F1 on the mapped 67-document subset. Contradiction recall, over-selection
of legal evidence, invoice false positives, candidate misses and provider
failures remain limitations. These results establish neither legal reliability
nor accuracy on private ClearLedger AR workflows.
