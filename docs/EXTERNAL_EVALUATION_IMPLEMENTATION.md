# External evaluation Phase1 — offline adapters and scorer validation

2026-10-27, branch `eval/external-phase-1-adapters`, from status `5a0b50d`.
Production backend/domain/Investigator/UI/dependencies/settings unchanged. No model
inference, credential access, database, Docker, private benchmark or sealed-answer
operation. No test-answer or validation-annotation inspection: only3 selected dev
NLI documents and8 selected train DocILE documents used for development checks.

The [v1 plan](EXTERNAL_EVALUATION_PLAN.md), external JSON and checksum are **unchanged**.
Phase1 supplies previously missing code/tooling, not new samples, tasks or metrics.
This does not complete milestone11 or authorize any inference.

## Architecture and artifact boundary

Evaluation-only modules under `scripts/external_eval/`:

- `contracts.py`: strict Pydantic2 DTOs for source packets, NLI labels/quotes,
  invoice references, provider/fallback/failure metadata, geometry and graph edges.
  No AR category/claim/amount or production DTO reuse. Extra fields, unknown labels,
  duplicate hypotheses/answers, invalid confidence and unsafe identifiers rejected.
- `source.py`: public field whitelist, source-only canonicalization, quote checks,
  source-OCR geometry, hash-checked packet reader and four source CSV copies.
  No annotation reader, official Dataset object, model transport or application import.
- `scorers.py`: pure count/interval/edge scorers with explicit gold arguments.
- `gold.py`: separate scorer-only annotation/edge readers, native evaluator view,
  prediction sealing. Never imported by the packet reader/source projection.
- `tooling.py`: isolated package hash lock, dependency check and source-artifact
  provenance validation. `scripts/external_phase1.py` exposes offline commands.

Actual external layout (all regular copies; no dataset symlinks):

```text
C:\ClearLedgerEval\external-runs\
  contractnli-v1\inputs\adapter\     # 3 source-only JSON packets,51 public hypotheses
  contractnli-v1\adapter\            # reserved; no model predictions
  contractnli-v1\scored\             # empty, no final inference
  docile-v1\inputs\adapter\          # 8 source-only OCR/text/word-geometry packets
  docile-v1\adapter\                 # explicitly labeled geometry FORMAT FIXTURES
  docile-v1\scored\                  # empty
  recbench-v1\inputs\sources\        # only bank_statements/ledger/payouts/settlement_lines CSVs
  recbench-v1\adapter\               # empty, no matcher
  recbench-v1\scored\                # empty
  phase1-v1\projection-manifest.json
  phase1-v1\contract-dev-validation.json
  phase1-v1\docile-dev-validation.json
  phase1-v1\docile-scorer-only\       # train-only native gold view; never worker-visible
  phase1-v1\install-report.json
  phase1-v1\tooling-metadata.json
  phase1-v1\verification-v1.json      # final checks + implementation hashes, no model results
  phase1-v1\venv\                    # official evaluator only
```

Manifest lives **outside packet directories**, binds packet hashes to the frozen
plan. All four copied RecBench CSV hashes agree with Phase0 inventory. No labels,
truth directories, annotation fields, document type, metadata or scorer results
are copied into inputs. NLI raw split JSON is decoded only in trusted projection;
only selected source text/public hypotheses are serialized, never annotation data.

Packet readers reject extra files, hash changes, identifier/path mismatch, linked
files/ancestors and schema additions. A fresh isolated Python reader test denies
opens outside the packet directory, network and subprocess access; it reads packets
successfully but cannot read a synthetic scorer-only file. Gold/application/provider
modules are absent from that reader. This is a tested logical boundary and regular
file separation, **not an OS security guarantee against a malicious host owner**.
No model worker/transport exists here. A future transport must retain these limits.

Real scoring CLI verifies prediction seal + plan + manifest, source packet hashes
and Phase0 gold-file digests **before** answer interpretation. Model confidence
does not authenticate a source.
Seals are local SHA-256 snapshots, not cryptographic signatures or independent custody.
Development format probes use only the permitted dev/train gold, without model
predictions; their validation reports never claim model accuracy.

## ContractNLI adapter and frozen scorer

Input fields exactly `document_id`, `text`, `hypotheses[{hypothesis_id,text}]`.
No dataset spans, answer choices, annotation sets, URLs or filenames. Output has
document ID, bounded unique answers (ID, label, evidence quotes/ranges, optional
confidence/uncertainty) and transport-owned provider/model/fallback/failure metadata.
Labels: Entailment, Contradiction, NotMentioned, Abstain, ProviderFailure.
Transport—not model text—must supply truthful metadata on a future run.

Quotes are matched **exactly against predictor-visible source text**, with overlapping
occurrences considered. Missing, repeated/ambiguous and mismatched-offset quotes
receive no location credit. Supplied offsets cannot rescue ambiguous text. Gold
candidate boundaries never help locate a prediction. Unicode source text is not
rewritten; offsets remain Python character indices in that exact text.

For all frozen204 final pairs, scorer retains missing answers as Abstain; provider
document failure produces ProviderFailure dispositions. Extra/duplicate IDs, missing
gold coverage and contradictory success/failure envelopes fail validation.

- Accuracy = correct / all expected pairs, including abstentions/failures.
- Answered-only accuracy = correct / E,C,N predictions; N is an answer, not a failure.
- Per class TP/FP/FN gives P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN).
  Macro averages over the3 fixed classes. Undefined metrics are null; an undefined
  class F1 contributes0 to fixed-three-class macro, explicitly reported.
- Confusion rows are gold E/C/N; columns E/C/N/Abstain/ProviderFailure. Separate
  missing, abstention, provider/policy/parse/schema failure and fallback counts.
- Unsupported conclusion = E/C predictions disagreeing with gold / all E/C
  predictions (including gold N cases); zero denominator null.
- Quote validity = uniquely source-verified quotes / all submitted quotes, with
  separate missing/ambiguous/range-mismatch counts. Quotes on gold N reported.

Frozen character-overlap evidence scorer: only gold E/C pairs. Merge/union ranges;
TP=intersection character length, FP=predicted union minus gold, FN=gold minus
prediction. Micro P/R/F1 from summed characters. Joint score empties predictions
when the class is incorrect. Gold N has no positive evidence target. Overlapping
quotes do not earn duplicate character credit. No fuzzy matching or metric tuning.
Hypothesis property tests compare overlap arithmetic to an independent character-set
oracle; hand-computed tests cover class confusion, unsupported conclusions and
joint evidence. A minimal12×17 fixture proves the204-pair denominator without
opening actual test answers.

Actual dev check:3 frozen documents /51 pairs, source projection + empty-output
format probes; all51 counted as abstentions. This tests plumbing, **not accuracy**.
The12 frozen test answers were not read. Gold choice/evidence values are not printed.

## DocILE projection, geometry and official evaluator

Input OCR becomes canonical pages by joining words with spaces, lines with newline,
blocks with an extra newline. Each word retains independent start/end and original
normalized geometry. Native page numbering is zero-based, separate from production
document span conventions. Empty/unusable OCR fails explicitly; no OCR is invented.
This supplied-OCR track does not claim ClearLedger gained scanned-PDF OCR support.

Prediction value must occur in its source quote. Normalize **values only**: Unicode
NFC plus outer trim; preserve case, punctuation, leading zeroes and internal spaces.
Quote must be unique across pages; page hints/offsets cannot rescue duplicates.
BBox is union of overlapping input OCR word boxes; no annotation lookup, adjustment,
snapped-gold rescue or fabricated location. Unlocalized predictions are excluded
from native JSON because no honest box exists; their counts/failures and FP/FN
remain in secondary scoring, so native precision is not presented without coverage.

Only mapped output is `invoice_references[].value` → native KILE `document_id`,
conditional on scorer-only `metadata.document_type == tax_invoice`. All8/50 packets
are retained for secondary metrics/non-invoice emissions. After prediction sealing,
the scorer creates a **separate derived native view**: only selected tax invoices,
only document_id fields; original gold values/boxes untouched, no original dataset
modification. This partial-label-space result is **not a full official DocILE score**.
Non-invoice emissions are evaluated separately over all selected documents.

Custom secondary metrics: source-grounded invoice-ID TP/FP/FN, exact set match,
coverage/abstention, non-invoice false emissions, quote validity, unsupported fields,
missing output and failure categories. Duplicate exact normalized fields are counted
separately and deduplicated for scoring. Invalid source localization earns no TP;
emitted unsupported facts remain FP. No amount/date/vendor/payer/UTR/line-item score.

Official [rossumai/docile tooling](https://github.com/rossumai/docile) installed as
**docile-benchmark==0.3.5** in `phase1-v1/venv`, without OCR extras. Artifact SHA-256:
`3440a7d28cbae122edb2598d9ccfaacde1bd586fa8c9588a38fe0dc8f5579019`.
[`evaluation/requirements-docile.lock`](../evaluation/requirements-docile.lock) pins
all21 evaluator distributions and their exact wheel hashes for Windows CPython3.12.
Pip install report records public artifact URLs/hashes; dependency check passes.
Product `pyproject.toml`/`uv.lock` are unchanged. Adapter schemas use the existing
application test environment's Pydantic2.14.1, with zero production-domain imports.

Observed:8/8 source-only word→quote→geometry roundtrips pass. Official CLI accepts
nonempty geometry-format fixtures on the2 selected train tax invoices. These are
arbitrary source words for schema/location validation, **not inferred invoice IDs**.
No model-quality number is reported. An earlier empty-format check failed because
official0.3.5 requires at least one prediction. Failed artifacts/log preserved.
For a future genuinely all-abstaining run, report native score NOT COMPUTABLE due
to that tool limitation and retain secondary missed/abstained counts; **never insert
a dummy model prediction to make scoring succeed**.

Pinned future native command (do not run in Phase1):

```powershell
C:/ClearLedgerEval/external-runs/phase1-v1/venv/Scripts/docile_evaluate.exe --task KILE --dataset-path C:/ClearLedgerEval/external-runs/docile-v1/scored/results.native-view --split clearledger_val_v1 --predictions C:/ClearLedgerEval/external-runs/docile-v1/scored/results.kile.json --evaluate-x-shot-subsets "" --evaluate-fieldtypes --evaluate-also-text --store-evaluation-result C:/ClearLedgerEval/external-runs/docile-v1/scored/native-results.json
```

The derived view covers the36 tax invoices inside the frozen50; all50 remain in
secondary scoring. Default official PCC IoU threshold is unchanged (1.0); no custom
text normalization is substituted into native metric code. Native AP/F1/P/R are
reported as **conditional document_id KILE**, native text match separately. Our
secondary normalization is different by design and must be labeled separately.

## RecBench independent scorer scope

Only exact `(txn_id,line_id)` ledger↔processor edges. Set intersection TP,
predicted-only FP, gold-only FN; duplicates do not earn credit and are counted.
Typed keys/extra fields validated. Abstention transaction keys can count their
missed eligible gold edges; simultaneous prediction and abstention is rejected.
Duplicate gold edges fail rather than silently hiding source defects.
No real matcher predictions or gold performance run occurred. No payout/bank scorer,
foreign-currency conversion, financial mutation or AR performance claim exists.

The [publisher card](https://huggingface.co/datasets/end-close/recbench) now verifies
synthetic origin/CC BY4.0 and describes missing settlement reports requiring deposit
unbundling. This supports an intentional missing-report interpretation, but does
**not** establish the exact1047-key/level-c expansion rule. Linked detailed schema/
evaluation files were unavailable at those public URLs. Preserve the frozen protocol
and keep payout/bank scoring blocked. The card advertises a native evaluator; it
is not in the local package and was not fetched/executed. Our primitive is explicitly
independent, not the publisher headline auto-match metric or a new task approval.

## Reproduction

Run from repository in Windows PowerShell. Existing outputs refuse replacement;
use checks/tests to validate them, not regeneration. No commands below contact models.

Environment installation (already executed with pinned version; new environment
can use the hash lock):

```powershell
.venv/Scripts/python.exe -m venv C:/ClearLedgerEval/external-runs/phase1-v1/venv
C:/ClearLedgerEval/external-runs/phase1-v1/venv/Scripts/python.exe -m pip install --require-hashes -r evaluation/requirements-docile.lock
C:/ClearLedgerEval/external-runs/phase1-v1/venv/Scripts/python.exe -m pip check
```

Executed offline artifact preparation/validation commands (do not overwrite outputs):

```powershell
.venv/Scripts/python.exe scripts/external_phase1.py prepare --plan C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --source C:/ClearLedgerEval/external --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase1.py validate-contract-dev --plan C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --source C:/ClearLedgerEval/external --runs C:/ClearLedgerEval/external-runs
.venv/Scripts/python.exe scripts/external_phase1.py validate-docile-dev --plan C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --source C:/ClearLedgerEval/external --runs C:/ClearLedgerEval/external-runs --evaluator C:/ClearLedgerEval/external-runs/phase1-v1/venv/Scripts/docile_evaluate.exe
$env:PYTHONPATH='scripts'
.venv/Scripts/python.exe -m external_eval.tooling --runs C:/ClearLedgerEval/external-runs --lock-output evaluation/requirements-docile.lock
Remove-Item Env:PYTHONPATH
```

For existing artifacts use the same tooling command with `--check`; this revalidates
packet/CSV hashes, frozen IDs, hash lock and isolated evaluator dependencies without
rewriting metadata. It was executed successfully after implementation.

For a **separately approved later task only**, `prepare --tier scored` projects the
frozen12 test NLI texts and50 DocILE OCR records into `inputs/scored`; it writes
`phase1-v1/projection-scored-manifest.json`. It has not been executed. A future
provider consumes only those packets and emits JSONL matching the typed DTOs; no
transport/generation command is implemented/authorized here. Failures must become
truthful empty failure envelopes, not patched model answers or missing denominator.

Future sealing/scoring interface, example NLI; replace placeholders with actual
sealed output paths, not fabricated predictions:

```powershell
.venv/Scripts/python.exe scripts/external_phase1.py seal --plan C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --manifest C:/ClearLedgerEval/external-runs/phase1-v1/projection-scored-manifest.json --dataset contract-nli --predictions C:/ClearLedgerEval/external-runs/contractnli-v1/scored/predictions.jsonl --output C:/ClearLedgerEval/external-runs/contractnli-v1/scored/seal.json
.venv/Scripts/python.exe scripts/external_phase1.py score --plan C:/ClearLedgerEval/external-runs/evaluation-plan-v1.json --manifest C:/ClearLedgerEval/external-runs/phase1-v1/projection-scored-manifest.json --dataset contract-nli --tier scored --inputs C:/ClearLedgerEval/external-runs/contractnli-v1/inputs/scored --source C:/ClearLedgerEval/external/contract-nli --predictions C:/ClearLedgerEval/external-runs/contractnli-v1/scored/predictions.jsonl --seal C:/ClearLedgerEval/external-runs/contractnli-v1/scored/seal.json --output C:/ClearLedgerEval/external-runs/contractnli-v1/scored/results.json
```

Equivalent `--dataset docile` uses source `external/docile`, its packet directory
and `results.json`; scorer also creates native view/KILE JSON for the pinned command.
`--dataset recbench-small` reads only `csv/truth_ledger_processor.csv`, validates its
seal and computes independent edge metrics; no model, no payout scoring. Its source
manifest is the original projection manifest. No such real score was run here.

Focused verification (use a fresh nonexistent basetemp on each run):

```powershell
.venv/Scripts/python.exe -m pytest --noconftest tests/test_external_phase0.py tests/test_external_phase1.py --basetemp .local-runtime/phase1-tests-final -q
.venv/Scripts/python.exe -m ruff check scripts/external_eval scripts/external_phase1.py tests/test_external_phase1.py
.venv/Scripts/python.exe -m ruff format --check scripts/external_eval scripts/external_phase1.py tests/test_external_phase1.py
.venv/Scripts/python.exe -m mypy --strict --follow-imports=silent scripts/external_eval scripts/external_phase1.py
.venv/Scripts/python.exe -m compileall -q scripts/external_eval scripts/external_phase1.py
```

Observed61 focused tests PASS in4.09s (14 Phase0 +47 Phase1), Ruff lint/format PASS,
strict mypy PASS (7 files), compilation PASS.
Logs Git-ignored locally: `external-phase1-*.log`; native log and package metadata
stay under phase1-v1. Full application/database/browser gates were not run because
no product code/behavior changed. Prior regressions are unmodified.

## Remaining gates before live inference

See [privacy review](EXTERNAL_EVALUATION_PRIVACY.md): ContractNLI/DocILE transmission
currently **denied**, not synthetic. Resolve document-level rights/PII/provider terms
and DocILE dataset grant, then obtain explicit authorization for a bounded
evaluation-only transport, model/quota/budget and source-only payload. Freeze its
code/prompt/schema/model hashes before final predictions. No production synthetic
gate bypass, key/project/billing change or new authority. RecBench stays offline
and domain-incompatible with current AR imports; grouped payout semantics remain
out of scope. Phase0 samples/checksum and private evaluation remain untouched.
