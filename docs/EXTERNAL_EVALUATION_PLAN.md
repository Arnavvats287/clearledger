# External evaluation protocol v1 — frozen before inference

Phase 0, 2026-10-27. **No inference, model lookup, network request, application
import, database operation or Docker operation was performed.** Frontend and
backend behavior are unchanged. This protocol does not authorize a later model run.
The existing frozen ClearLedger evaluation is a separate experiment; its private
roots, operator, schedule, answers and image were not accessed or modified.

Machine plan: `C:\ClearLedgerEval\external-runs\evaluation-plan-v1.json`.
SHA-256: `a83dc857f3f4ee8d0f6468fd945358504b59173e4ad55f53845bec3c7d00589d`.
The sidecar `evaluation-plan-v1.sha256` and exclusive-create/check commands protect
against accidental replacement; these are local checksums, not signed custody.
All actual sample IDs are in that external file, not in Git.

## Local inventory and provenance

Only the three explicitly authorized public dataset children were traversed.
Canonical completed inventory:
`C:\ClearLedgerEval\external-runs\inventory\complete-v1\inventory.json`.
SHA-256: `f544efd454fd32314c32b1987750abea7b7c2211626218d1cbbffc4006f8611d`.
Adjacent per-dataset inspection JSON and relative-path/byte-size JSONL indices are
machine-readable. Scorer-side structural check:
`inventory\recbench-structure-v1.json`. No dataset content is committed.

| Dataset | Files / bytes including local duplicates | Available version / license |
|---|---:|---|
| DocILE | 17,044 / 2,820,610,254 | `annotated-trainval.zip` plus extracted files; explicit release and license UNKNOWN locally |
| ContractNLI | 613 / 83,759,009 | README initial release 2021-10-05; CC BY 4.0, local LICENSE/TERMS; attribute Koreeda & Manning, Findings EMNLP 2021 |
| RecBench | 23 / 469,586,124 | manifest generator 0.1.0, tier `small`, seed 1042; license/distribution policy UNKNOWN locally |

Efficient provenance: hash metadata/code/license files and split lists; hash the
selected 58 DocILE PDF/OCR/annotation triples (174 files), record the ZIP central
directory path/size/CRC digest, not a full archive content-integrity claim. Hash
ContractNLI split JSON files. Hash all 11 RecBench CSV mirrors; their row counts
match the manifest. Retain publisher-declared Parquet SHA-256 values without
claiming to have independently verified them. No Parquet engine is installed;
Parquet equivalence beyond manifest row counts is unverified. Path/size index
hashes are not content hashes. No bulk PDF/ZIP rehash was needed.

An initial inventory attempt stopped at an empty RecBench monetary cell. Empty
cells now count as **missing**, not zero; malformed integer cells count separately.
Partial output directories were preserved; `complete-v1` is the authoritative run.

## A. DocILE: narrow, conditional invoice-reference extraction

Local split lists: **5,180 train, 500 val, 5,680 trainval**, train/val disjoint and
trainval their union; each document has PDF, OCR JSON and annotation JSON, with
zero missing companions. No test split is present. The archive is redundant with
the extracted tree, not an extra split. No native evaluator/package source is
present locally and `docile` is not installed; official release/tooling cannot be
verified from this distribution alone. No package was fetched or installed.

Annotation field entries contain `fieldtype`, `text`, `page`, `bbox`; separate
line-item entries and table/header metadata exist. The observed native taxonomy
has **36 header fields and 19 line-item fields**, enumerated in the external
inventory. OCR has pages → blocks → lines → words, with word `value`, confidence,
geometry and snapped geometry. OCR coordinates are not application canonical text
offsets. Gold field boxes/text and annotation metadata are never prediction inputs.

The corpus is mixed: 3,850 tax invoices, 1,440 orders, 128 purchase orders, 75 sales
orders, 29 proformas, 116 receipts, 12 utility bills, 24 credit notes, 6 debit notes.
Currency metadata is mostly USD/other, not an INR financial import dataset.

| Native label / candidate | Existing ClearLedger extraction output | Confidence / decision | Frozen normalization and location rule |
|---|---|---|---|
| `document_id`, **tax invoices only** | `invoice_references[].value` + source span | Medium, conditional: invoice identity is legitimate; arbitrary document IDs are not invoice IDs | Unicode NFC and outer whitespace trim only; preserve case, punctuation, leading zeroes and internal whitespace. Unique source-only quote-to-OCR word alignment can yield boxes; otherwise localization unavailable/fails |
| `document_id` on orders/receipts/etc. | None guaranteed | Rejected as general invoice mapping | Retain documents; report non-invoice false emissions separately, never relabel their IDs as invoices |
| `payment_reference` | `utr_references` | Rejected: a generic payment reference is not necessarily an Indian UTR | No coercion or prefix guessing |
| `customer_billing_name`, `customer_id`, vendor names/IDs | `payer_hint` superficially similar | Rejected: billed customer/vendor is not verified bank payer | No identity attestation from invoice text |
| `date_issue`, `date_due`, payment terms | No corresponding extraction output | NOT IMPLEMENTED | No date scoring for this application contract |
| `amount_total_gross/net/tax`, `amount_due/paid`, tax detail amounts/rates, currency | No invoice-total output; `claims[].amount_paise` means a deduction claim | Rejected monetary mapping | Never turn invoice total/foreign minor units into an INR deduction; amount exact-match metric NOT EVALUABLE |
| Order/bank/account/address/registration identifiers and other header fields | No semantically equivalent typed output | NOT IMPLEMENTED | No field-name substitution |
| All 19 line-item fields | No line-item extraction output | NOT IMPLEMENTED | No LIR score |

Freeze **8 train documents for adapter validation, 50 val for final scoring**.
Selection used source IDs only, before per-document annotations. The frozen 50
contain 36 tax invoices and 14 other types; the adapter 8 contain 2 tax invoices,
2 receipts, 4 orders. No replacements to increase invoice yield. Scorer-only
document type establishes the conditional evaluation denominator, never a model
hint or a post-result selection criterion. Report all 50 dispositions.

Primary secondary metrics: invoice-ID micro P/R/F1, exact predicted-ID-set match,
document coverage/abstention, extra invoice-reference count on non-invoices,
quote validity, unsupported-field rate and failures. Define unsupported-field rate
as unsupported emitted facts / all emitted facts, with denominator and count shown;
only invoice-reference facts are scored as supported here. Do not equate other
unscored extraction fields with false invoice IDs. Empty gold and predicted sets
have exact-set match 1; P/R with zero denominator are N/A, micro totals retained.
Provider/privacy/parse failures retain their selected document and missed gold IDs.

**Official target:** DocILE KILE AP/localization via its native evaluator, restricted
to the mapped field, after pinning and validating an official evaluator release
and source-only OCR geometry conversion. Exact API, thresholds and installation
command are UNVERIFIED; no official metric has been run. Do not call custom field
F1 a full official DocILE result. No gold-assisted OCR/box alignment. Failure to
align must be reported, not filtered away to improve localization. Optional full
run: all 500 val documents with the same frozen configuration.

Application PDF limits (2 MiB, 20 pages, bounded text/decompression) remain in force;
unsupported/scanned/oversized cases are reported, not fixed by weakening ingestion.
Input OCR support is an **evaluation-only adapter not yet implemented**, distinct
from the actual PDF-only ingestion track. Never present supplied OCR as product OCR.

## B. ContractNLI: evaluation-only evidence reasoning, not AR accuracy

Confirmed **607 NDAs**, 17 fixed public hypotheses/document:

| Split | Documents | Labeled pairs | Frozen use |
|---|---:|---:|---|
| train | 423 | 7,191 | Development reference only; no final score |
| dev | 61 | 1,037 | 3 hash-selected documents ×17 =51 adapter pairs |
| test | 123 | 2,091 | 12 hash-selected documents ×17 =204 final pairs |

All document IDs are split-disjoint. All inspected candidate character spans and
annotation evidence indices are within source bounds. Root JSON contains
`documents` and `labels`; the latter defines public hypotheses, **not answer labels**.
Gold answers live in `annotation_sets[].annotations[ID].choice` and evidence indices
in `.spans`. Gold choices are `Entailment`, `Contradiction`, `NotMentioned`.
Evidence uses sentence/list-item candidate spans, may require multiple redundant
spans, and applies to Entailment/Contradiction, not NotMentioned. Raw contains
375 PDFs, 113 HTM and 119 TXT files; prepared JSON text is the frozen input view.
README references a separate baseline repository; evaluator code is absent locally.

Conceptual mapping: source supports assertion / source conflicts / cannot conclude.
This is **legal-text NLI**, not contract authenticity, legal advice, or AR deduction
accuracy. Current `EvidencePlan.assertion`, category/amount, seven read-only tools,
and strict AR synthesis cannot represent arbitrary legal hypotheses. Moreover the
AI Investigator currently receives scoped verified summaries, not arbitrary legal
document prose. An unmodified production workflow is **NOT EVALUABLE** for this
task. Do not fabricate a damage claim, amount, signed source or tool record to fit.

A future isolated evaluation-only NLI wrapper may reuse bounded transport/workflow
discipline with separate typed NLI input/output and a read-only document port.
It must not change production domain DTOs or acquire financial/database authority.
This adapter is **NOT IMPLEMENTED in Phase 0**.

Whitelisted predictor packet: source text + public hypothesis IDs/text only. Strip
annotation sets, choices, **all dataset candidate spans**, gold evidence indices,
URL/file-name/type metadata. Segment from text independently or request exact
quotes. Gold candidate boundaries are scorer-only, eliminating even boundary
leakage. Never pass the complete split JSON to a worker.

Freeze two generations/document: bounded plan, then source-grounded synthesis
covering all 17 hypotheses. A document over a cap fails/abstains for all affected
pairs; no silent truncation or sample replacement. No retries in v1.

Metrics: accuracy over all 204 pairs; macro-F1 over all three fixed classes,
per-class P/R/F1, confusion counts; answered-only accuracy separately. Explicit
abstention/provider failure is not the substantive NotMentioned label and counts
incorrect on the full denominator. Unsupported conclusion = predicted E/C on gold
NotMentioned or the opposite E/C class, divided by all E/C predictions; zero
denominator N/A. Report fallback count separately from accepted model predictions.

Secondary evidence P/R/F1: scorer unions gold character intervals and verified
predicted quote intervals within each document/hypothesis. Intersection character
count supplies TP; extra/missing characters supply FP/FN. Micro across gold E/C
pairs; report joint evidence score with incorrect-label predictions treated as
empty, plus quote validity and unsupported citations on NotMentioned. No evidence
score for NotMentioned; no guessed annotation indices. This is explicitly a
custom character-overlap metric until native evaluator semantics are verified.
Optional full run: all 123 test documents /2,091 pairs, same frozen configuration.

## C. RecBench-small: legitimate graph truth, different product domain

Manifest: generator 0.1.0, seed1042, start2025-01-01, 365 ledger days. No official
split, scorer, README/license or generator semantics are included locally. `small`
is a tier name, **not evidence of development-only or held-out suitability**.

| Source table | Rows | Relationship / observables |
|---|---:|---|
| ledger | 999,005 | charge/refund/dispute transaction, order/entity, currency, amount_minor, processor refs/dates |
| settlement_lines | 1,014,955 | capture/refund/chargeback/adjustment, gross/fee/net, FX, merchant/processor refs, payout_id |
| payouts | 73,955 | processor/entity, settle_currency, amount_minor, sales/arrival dates, payout_ref |
| bank_statements | 75,138 | account/currency, signed amount_minor, date, counterparty/reference, credit/debit |

Observed ledger currencies USD/GBP/EUR/AUD/CAD/JPY; settlement/bank currencies
USD/EUR/GBP. **No INR.** Refunds/debits are signed, some settlement gross/fee amounts
are absent (303,761 each); preserve missingness, signs, currency and integer units.
Do not treat USD cents as paise or invent FX roundings/fee policies.

Scorer-only `truth_ledger_processor` has 1,012,216 edges: capture, partial_capture,
refund and chargeback; zero duplicate pairs and full source FK coverage.
997,550 distinct ledger records link to unique processor lines, including
11,277 ledger keys with two or three lines. This **does contain legitimate
reconciliation-style gold pairings**, not merely document extraction annotations.
It can support exact edge P/R for that native graph task; not current AR matching.

`truth_line_payout`: 1,012,219 edges, zero duplicate pairs, valid line keys, but
3,642 edges reference payout keys absent from the payout source table.
`truth_payout_bank`: 75,002 edges, zero duplicate pairs, valid bank keys, but
**1,047 payout keys absent from source payouts**. `labels_payout` has 75,002 rows
and levels a/b/c (67,440/6,515/1,047). A virtual/grouped-payout interpretation is
plausible but **not established by documentation**. Do not invent its expansion
rule or silently drop these gold edges. Payout/bank scoring is blocked pending
that definition/candidate-universe clarification.

All `labels_ledger`, `labels_processor`, `labels_payout`, `labels_bank` are answers,
including is_matchable, ambiguous/duplicate groups, ref_scenario and member_count.
They are never input features. Source `settlement_lines.payout_id` is already an
observable relationship: 1,008,577 nonempty references all resolve; summing their
integer net amounts matches all 73,955 source payouts. Reporting discovery of those
known FK links as sophisticated matching would be misleading. Adjustment/duplicate/
truth semantics require separate documentation, not guessed monetary rules.

No native evaluator is locally available. Proposed future **independent** exact
edge scorer: typed natural-key pairs, set intersection TP, predicted-only FP,
gold-only FN; duplicates reported separately. Amount consistency is a separate
currency-preserving integer check, no tolerance or currency conversion. Abstention
misses eligible gold edges; report review routing, replay consistency and unsafe
mutation counts if an application route is legitimately available. Currently no
such financial adapter is valid: payouts are not customer invoices, chargebacks
are not damage deductions, and source refs are not authenticated payer intent.

Freeze 16 adapter and 128 disjoint scored **bank source IDs**, selected without
truth. All four input tables are the static source candidate universe; do not use
gold closure to assemble candidates. Any later currency/entity restriction uses
only source columns. Bank metrics cover selected bank rows; other graph levels
are separate optional full-table tasks, not selected using hidden relationships.
Optional full bank task: all75,138 rows. These are local partitions of one generated
scenario, not independent test distributions or a chronological availability test.
0 Gemini generations proposed. Current application reconciliation score remains
**NOT EVALUABLE**, rather than manufactured by remapping currencies/entities.

## Leakage boundary and freeze rules

Phase0 inspection is an authorized **metadata/scorer-side** activity. It counted
public annotations/relationships but did not emit their values into prediction
packets, application stores, prompts or model/tool inputs. No predictor exists yet.
Future process layout must physically separate:

1. Read-only original public roots, accessible only to projection/scorer preparation.
2. Whitelisted source-only packets in `external-runs/<dataset>-v1/inputs/`; no raw
   root mounts, symlinks, gold files or annotation metadata in prediction workers.
3. Predictions and telemetry in `<dataset>-v1/{adapter,scored}/`, with only natural
   source keys and independently verified source pointers.
4. Gold/scoring process with separate access, run **after predictions are sealed**.
   Labels never meet the model/application; predictions meet truth only here.

Hash sample order:
`SHA256("clearledger-external-phase0-v1|<domain>|<source-id>")`, ascending hexadecimal,
tie-break by exact ID. Domains: `docile:adapter`, `docile:scored`,
`contractnli:dev`, `contractnli:test`, `recbench:adapter`, `recbench:scored`.
RecBench scored selection first removes adapter IDs. No label-based replacement,
stratification or difficulty selection. All IDs frozen in the machine plan.
Do not tune prompts/model/app on scored examples. Freeze adapter/prompt/model/
schema/scorer hashes before scoring; plan changes require explicit version2 approval.

Public documents are **not approved synthetic data**. Existing extraction gates
require synthetic/privacy approval; there is a real conflict with transmitting
DocILE/ContractNLI verbatim under current policy. Stop before calls until separate
privacy/provider-terms review, license provenance and an honest evaluation-only
data policy are approved. Never bypass this with `X-Synthetic-Data:true`, signing
public sources as authenticated business records, or fabricated production identity.
Prompt injection remains untrusted content; NLI source consistency is not authenticity.

## Workload, measurement, run order and blockers

Run **ContractNLI offline adapter validation first**: text-only with fixed questions
isolates evidence reasoning without PDF geometry. This is an independent probe,
not a claim of production AR tool reuse. Then DocILE source-only adapter validation;
resolve RecBench grouped truth/domain semantics before attempting its scored task.
No scored model run is currently unblocked or authorized.

| Future bounded tier | Generations ceiling | Input token reservation | Output token reservation |
|---|---:|---:|---:|
| DocILE adapter8 + final50 | 58 (≤1/document) | 475,136 (8,192/request) | 59,392 (1,024/request) |
| ContractNLI adapter3 + final12 | 30 (2/document) | 983,040 (32,768/request) | 122,880 (4,096/request) |
| RecBench | 0 | 0 | 0 |
| Combined | **88**, no retries | **1,458,176 maximum** | **182,272 maximum** |

Expected actual usage is unknown before adapters/token counting. Rough source-text
estimate only: selected DocILE OCR has143,187 word characters including separating
spaces (~47,729 tokens at3 chars/token); selected ContractNLI text188,717 characters,
sent twice (~125,812 tokens). With illustrative1,000/2,000 prompt tokens per
DocILE/NLI request, ~292k total input tokens; this is **not a tokenizer measurement**
or API cost estimate. Reasoning/output and redaction expansion require real preflight.
Caps are fail-closed, no hidden truncation. Deterministic-first routing may reduce
DocILE calls; privacy/unsupported inputs reduce calls but remain in denominators.

Previously reported Gemini quotas15RPM/250k inputTPM/500RPD are historical, not
current availability. 88 generations are17.6% of that daily figure if still valid;
metadata/count/generation operations must each be reserved and paced. At up to
three operations/attempt the conservative ceiling is264 operations, ≥132 minutes
at the proposed2 total operations/minute; not a measured runtime. One caller,
no SDK/manual retries in v1. Verify model availability, live project quotas,
pricing/budget/privacy and approved configuration **only under future authorization**.
Optional full DocILE500 + NLI246 generations needs multiple quota days or separately
approved accounting; not authorized by this document.

Latency: monotonic `perf_counter_ns`, projection/parse/provider/validate/persist/total;
report successful/failed counts, median, nearest-rank p95, maximum, no discarded
timeouts. Provider, policy/privacy, parse, malformed output and citation failures
are distinct. Never label fallback as real AI success. Zero-denominator metrics N/A.
Any actual API track must snapshot and compare financial state, use disposable DBs,
and prohibit posting/approval tools; standalone probes have no financial DB access.

**Scorer command: NOT IMPLEMENTED/BLOCKED**, honestly recorded as null in machine
plan. No native evaluator exists in any local package. Before scored inference,
pin/test official tools where available; otherwise approve and verify the explicit
secondary metrics above. Do not invent a working `docile evaluate` CLI. This phase
freezes tasks, subsets, metric formulas and failure treatment, not nonexistent code.
Unresolved release/license, privacy, NLI adapter, DocILE OCR/localization and
RecBench grouped-ID contracts are gates, not completed capabilities.

## Offline reproduction and checks

From the repository, Windows PowerShell (use fresh output directories, never overwrite):

```powershell
.venv/Scripts/python.exe scripts/external_inventory.py --source-root C:/ClearLedgerEval/external --output C:/ClearLedgerEval/external-runs/inventory/complete-v1
.venv/Scripts/python.exe scripts/external_recbench_structure.py --root C:/ClearLedgerEval/external/recbench-small --output C:/ClearLedgerEval/external-runs/inventory/recbench-structure-v1.json
.venv/Scripts/python.exe scripts/freeze_external_plan.py --inventory C:/ClearLedgerEval/external-runs/inventory/complete-v1/inventory.json --structure C:/ClearLedgerEval/external-runs/inventory/recbench-structure-v1.json --output C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json
```

Those outputs now exist; creation commands intentionally refuse replacement. To
check the frozen artifact without running an experiment:

```powershell
.venv/Scripts/python.exe scripts/freeze_external_plan.py --inventory C:/ClearLedgerEval/external-runs/inventory/complete-v1/inventory.json --structure C:/ClearLedgerEval/external-runs/inventory/recbench-structure-v1.json --output C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --check
.venv/Scripts/python.exe -m pytest --noconftest tests/test_external_phase0.py --basetemp .local-runtime/phase0-check-20261027c -q
.venv/Scripts/python.exe -m ruff check scripts/external_inventory.py scripts/external_recbench_structure.py scripts/freeze_external_plan.py tests/test_external_phase0.py
.venv/Scripts/python.exe -m ruff format --check scripts/external_inventory.py scripts/external_recbench_structure.py scripts/freeze_external_plan.py tests/test_external_phase0.py
```

Use a **new, nonexistent workspace basetemp** on reproduction; pytest manages that
directory. Observed:14 focused tests passed; Ruff lint/format and frozen-plan check
passed. Initial default sandbox temporary directory was unavailable (7 passed,
3 fixture setup errors); workspace basetemp resolved it without skipping tests.
No application/full regression suite was needed or run for this offline-only plan.
