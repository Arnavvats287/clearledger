# External evaluation — current status and historical gate records

## 2026-10-28 — Free-tier authorization recorded; no scored results

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

## SAFE TO CLAIM PUBLICLY

No scored model-performance claim: the current attempt has produced no scored
ContractNLI/DocILE predictions. Operator authorization and offline gate checks are
not substitutes for an executed external model evaluation.

## NOT SUPPORTED BY THIS EVALUATION

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
