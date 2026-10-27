# External evaluation privacy / transmission gate

Reviewed 2026-10-27. **No transmission approved and no model calls performed.**
This is an engineering gate assessment, not legal advice or consent from document
subjects. No project/key/billing/settings changes. Public availability is not
synthetic approval, source authentication, financial authority or permission for
every downstream use. Production synthetic-only gates remain unchanged.

## Provider implications

The current [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms),
effective2026-03-23, describe product/model improvement and possible human review
of unpaid-service inputs/outputs. They prohibit submitting sensitive, confidential
or personal information to unpaid services. The stated EEA/Swiss/UK treatment is
not assumed for this India-based development project. A public-data license does
not establish that a particular document is appropriate for Free-tier processing.
No API key/model/quota lookup was made; account status was not reverified here.

## Dataset decisions

| Dataset | Source/license status | Exact proposed future model-visible content | Decision now |
|---|---|---|---|
| ContractNLI | Real public NDAs; local README/LICENSE/TERMS give CC BY4.0. [Official project](https://stanfordnlp.github.io/contract-nli/). Attribution and third-party rights remain relevant. | Evaluation document key, complete prepared contract text,17 public hypothesis IDs/texts. No raw dataset JSON, file/URL metadata, candidate spans, gold choices or evidence. | **DENY pending document-level privacy/rights review and explicit evaluation-transport approval.** Text can contain personal/signature/contact details and business terms; no proof all selected documents are safe for unpaid processing. |
| DocILE | Annotated real business documents, not the synthetic release. [Publisher](https://docile.rossum.ai/) offers research access. [Tool repository](https://github.com/rossumai/docile) MIT license does not establish the downloaded dataset's grant or third-party document rights. Local access terms/version remain unresolved. | Evaluation document key and canonical text from supplied OCR, separated by page, for invoice-ID extraction only. Word geometry stays local for quote localization; no PDFs/images/annotations/metadata/type/gold boxes. | **DENY pending dataset access/license clarification and document-level privacy review.** Invoices may contain names, addresses, contacts, bank/tax/account details. No assumption that the existing synthetic-only projection safely handles arbitrary public invoices. |
| RecBench-small | [Publisher dataset card](https://huggingface.co/datasets/end-close/recbench) identifies synthetic transaction data under CC BY4.0; generator0.1.0. Local manifest matching was established separately by the operator. | **Nothing.** This protocol has no model task. Four native source CSVs remain local; all truth/label files are scorer-only. | **DENY/out of scope for model transmission.** Synthetic origin permits planning, not a new model experiment. Attribution/provenance still required if outputs are shared. |

Neither ContractNLI nor DocILE is marked synthetic. The prepared packets are local
evaluation artifacts, not application evidence records, and are not uploaded into
ClearLedger's evidence store. External transport is intentionally absent.

## Requirements before any future inference

1. Resolve the dataset access grant, attribution and rights for the proposed use.
   Review the actual source-only packet contents locally without gold annotations.
2. Demonstrate that each transmitted payload is compatible with provider terms.
   If redaction is needed, preserve an auditable local mapping and independently
   verifiable source citations. A changed text/task representation needs explicit
   protocol approval; do not silently redact or truncate and claim the same score.
3. Obtain separate user authorization for the evaluation-only transport, exact
   dataset/payload, model, budget and quotas. Do not enable billing to bypass this
   gate or label real documents with `X-Synthetic-Data:true`.
4. Restrict the worker to source packets and provider credentials only; no gold
   mounts, source signatures, production DB handles, tools, approvals or posting.
   Treat source text and output as untrusted; log only bounded diagnostics/usage.
5. Recheck current provider terms/model/pricing/quota then. Seal predictions and
   source hashes before a separate scorer reads gold. Current offline validation
   establishes adapter/scorer behavior, **not** model accuracy or privacy clearance.
