# External evaluation Phase 3 — final grounding hardening

2026-10-28. Implementation/development verification in progress; no Phase3 scored
model results are claimed at this checkpoint. Phase2 v1 remains immutable history.

## Frozen selection and method

Source-ID plan SHA256:
`73fd2a85c27c2c7708d9a61590089a8c4e43385f28d6a72f5625a375894a1057`.
The external plan at `C:/ClearLedgerEval/external-runs/phase3-v1/evaluation-plan.json`
contains exact IDs, split/source hashes, seed and exclusion lists. Selection is the
lowest SHA256(seed|dataset|source-ID), excluding the entire v1 scored selection:
24 unused ContractNLI TEST documents/408 pairs and100 unused DocILE VALIDATION docs.
No label/document-type stratification, difficulty replacement or new gold inspection.
Development uses application-owned minimal fixtures plus existing3 DEV/8 TRAIN
adapter documents, never v1 final examples as a tuning loop.

Model remains Gemini3.5 Flash-Lite. Two bounded plan/synthesis generations per
ContractNLI document; one invoice classification/ID-selection generation per eligible
DocILE document. Clearly out-of-scope/no-candidate documents abstain deterministically.
All100 remain in denominator. Unknown headings may receive typed classification in
the same request; the model cannot emit IDs for NON_INVOICE/UNKNOWN classification.

No retries, self-consistency samples, extra generations for score improvement or
model substitution. At most165 generations including controls/smoke, one caller,
six total provider HTTP operations/minute. Per-request ceilings remain32,768/4,096
legal input/output and8,192/1,024 invoice input/output tokens. Thinking is MINIMAL,
no sampling parameters are added. Effective prompts/schemas, model, code and packet
hashes are frozen before scored inference, with count-token admission and reservations.

The operator's current task authorizes these fresh public-dataset evaluations;
prior dataset-holder/Free-tier decisions remain historical, not rewritten as a
general production-data consent. Existing Free project/key/model are retained.
No billing/project/AutoPay change. Account quotas are operator UI evidence, not
model-API exposed remaining allowance. Published pricing/quotas are checked against
official Google documentation. No private/sealed benchmark or production data.
Official references checked2026-10-28: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
lists3.5 Flash-Lite standard Free-tier input/output as free, and paid reference
rates ofUSD0.30/1M input andUSD2.50/1M output including thinking.
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
conditional document_id KILE uses unchanged official0.3.5 defaults, plus exact-text
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

Initial complete gate:1019 passed,2 failed in1759.12s. Both failures were historical
offline acceptance fixtures omitting v3 span IDs. Fixture response updated with
offered IDs; no assertion removed or weakened. Affected acceptance, graph and actual
API group:13 passed in121.65s. Current source/worker focused checks passed. Final
complete frozen gate passed: **1,029 tests in1,833.27 seconds**, including PostgreSQL
migration/integration checks. Lock/dependencies, Ruff lint/format, strict domain
typing and matching-bound checks passed. This is test-suite runtime, not product
latency. Detailed log: `local-data/verification/20261027T222742635195Z.log`.
Separate isolated PostgreSQL restart check:4 passed in48.15s; log
`local-data/verification/isolated-restart-20261027T220756414376Z.log`.
Focused grounding plus existing external-evaluation tests:130 passed; current
source/worker checks:24 passed; strict evaluation-module mypy:5 files passed;
domain mypy:28 files passed; compile/import and original/frozen hash checks passed.

The next run reached the old1,800-second test-runner wall-clock deadline; its
timeout log is preserved at `local-data/verification/20261027T215603058544Z.log`.
This is not evidence of an application/provider/database timeout. The already
running replacement was launched with a3,600-second orchestration bound; the
persistent runner bound is now2,700 seconds following the operator clarification.
No individual test, request/provider/DB timeout, financial limit, retry or model
configuration changed. A future runner timeout preserves sanitized partial output
and exits124 instead of losing captured progress.

Synthetic admission: all three generations succeeded. Development smoke:
ContractNLI1/3 accepted,2/3 rejected for unoffered span IDs; DocILE7/8 accepted,
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
