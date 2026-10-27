# External scored evaluation — pending paid-project verification

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

## SAFE TO CLAIM PUBLICLY

- The dataset holder authorized this specifically scoped evaluation.
- Frozen source-only adapters/scorers were verified offline in prior phases.
- The paid-provider gate stopped execution before unverified document transmission.

## NOT SUPPORTED BY THIS EVALUATION

- Any scored ContractNLI/DocILE model metric or held-out model-performance claim.
- Production AR accuracy, bank reconciliation accuracy, customer ROI or saved work.
- Full DocILE/invoice extraction performance, model citation reliability or model-run
  financial safety. No model/application financial operation was executed here.
