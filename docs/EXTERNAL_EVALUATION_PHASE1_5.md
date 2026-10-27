# Phase1.5 — document screening, paid-provider review and bounded cost

Review date2026-10-27. **No transmission approved. No model, model-lookup or token-count
API calls; no billing/project/key changes.** Only public documentation GETs were
made. Production/UI, Phase0 plan/checksum/IDs, Phase1 adapters/scorers and private
benchmark artifacts are unchanged. This is an engineering assessment, not legal
advice. Copyright permission, personal/confidential-data suitability and provider
contractual protections are different questions.

## Decision matrix

| Dataset | Dataset rights | Document privacy | Paid Gemini terms | Technical readiness | Decision |
|---|---|---|---|---|---|
| ContractNLI | Local LICENSE/TERMS and official project give CC BY4.0; evaluation appears permitted with attribution | All3 dev/12 test source texts screened locally. Final12:10 manual review,2 proposed redaction reviews; no unredacted clearances | Paid safeguards help, but retention/cross-border handling and our authority still need acceptance | Offline adapter/scorer ready; separate paid transport, exact request counting and provider-schema admission unimplemented | **BLOCKED_PRIVACY**, also technical |
| DocILE | Research access established; actual downloaded grant permitting this third-party processing unresolved | All50 frozen val sources screened; no text changed. All50 denied while rights remain unclear | Paid safeguards cannot supply dataset rights |45 strict OCR projections accepted;2 empty-page and3 invalid-word rejections. Paid transport/token admission missing | **BLOCKED_RIGHTS**, also privacy/technical |

**Phase2 paid inference is not ready for authorization.** No sample was removed,
replaced or selected using answers. Redaction would change the source/evidence
representation; it requires explicit protocol v2, not a silent v1 substitution.

## Current official provider findings

Machine record: `phase1-5-v1/provider-terms-snapshot.json`:15 source URLs, page titles,
retrieval UTC, interpretations, HTTP status, byte count and SHA-256. Public HTML/PDF
snapshots are in `reference-snapshots/`. Provider findings use official Google
documentation only; three separate references cover dataset rights.

- [Paid Services terms](https://ai.google.dev/gemini-api/terms): active billing on
  the API project gives paid treatment; inputs/outputs are not used for product
  improvement. Security/legal logging and international processing remain.
- [Abuse monitoring](https://ai.google.dev/gemini-api/docs/usage-policies):55-day
  prompt/context/output retention and possible authorized flagged-content review.
  Policy-enforcement model use is a stated exception. This is **not zero retention**.
- [Processor DPA](https://business.safety.google/processorterms/): incorporated
  security/subprocessor/transfer protections; the customer retains controller or
  processor responsibilities and required authority. No automatic dataset consent.
- [Available regions](https://ai.google.dev/gemini-api/docs/available-regions): India
  is listed. It does not get the EEA/Swiss/UK unpaid-service exception. Paid treatment
  depends on billing status, with no India-only residency assurance. Local legal/tax
  applicability has not been adjudicated here.
- [Model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite):
  candidate **`gemini-3.5-flash-lite`**, stable published ID, structured outputs,
  input limit1,048,576/output65,536. Public availability is verified; availability
  to a future paid project and our evaluation schemas is **not API-tested**.
- [Current migration guidance](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6):
  minimal thinking; omit deprecated temperature/top_p/top_k and prefilled model
  turns. Therefore recommend a fixed model/configuration with those parameters
  **omitted**, not a fictitious fixed-temperature determinism guarantee. Production
  configuration was not changed.
- [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output):
  subset/complexity limits still need synthetic schema validation in a future task.
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): active synchronous
  RPM/TPM/RPD depend on project/model/tier and require AI Studio verification. No
  historical15RPM/free quota was reused. The documented Tier1 spend-rate protection
  can be$10/10minutes; it is not our evaluation budget.
- [Billing](https://ai.google.dev/gemini-api/docs/billing): published minimum$5 or
  local equivalent, with region/tier-specific UI confirmation. No purchase made.
  Keep auto-reload off. Prepaid credit expiry/refund conditions and delayed charging
  mean a balance is not a precise spending cap.

Pricing source: [official pricing](https://ai.google.dev/gemini-api/docs/pricing),
**Standard USD0.30/million input and USD2.50/million output including thinking**.
No caching, Batch, Flex, Contributor or Priority discount assumed. No grounding,
tools, file uploads or unrelated services proposed. Pricing is current at review,
not guaranteed for a later execution date. Reverify before any authorized call.

## Dataset rights and document-level findings

### ContractNLI

[Official project](https://stanfordnlp.github.io/contract-nli/) and local LICENSE/TERMS
agree on CC BY4.0 and requested paper attribution (Koreeda & Manning2021). The local
terms incorporate that license and distinguish third-party platform/privacy rights.
Local evaluation use appears reasonably licensed; it does **not** settle every
document's confidentiality/personal-data or processor-transfer basis.

All15 source texts were handled only by local scripts. Existing3 dev packets were
hash-checked; the frozen12 test source texts/public hypotheses were projected
**in memory through Phase1's whitelist**. Gold labels, evidence and span boundaries
were never used. No raw text was sent into model/chat context or written into reports.

Scored12 candidate-category document counts (overlap allowed): confidential context12,
signatory context11, address context7, company-sensitive context6, personal-name
context3, email1, phone1, tax-ID candidate1. These are **pattern candidates**, not
confirmed secrets or a complete PII inventory. Generic NDA confidentiality clauses
do not by themselves prove disclosure of actual trade secrets.

Final12 decisions:10 `MANUAL_REVIEW_REQUIRED`,2 `REQUIRE_REDACTION` (proposed,
subject to confirmation). Across dev+test:13 manual/2 redaction reviews. No
`APPROVE_UNREDACTED`. Per-ID records contain categories/counts/method, rationale,
canonical source-view hash and protocol-v2 warning, never matched values/snippets.

### DocILE

[Publisher site](https://docile.rossum.ai/) establishes request-based research access.
Its [scientific-research privacy notice](https://docile.rossum.ai/static/information_duty_on_scientific_research.pdf)
acknowledges real personal/contact/payment/account information and research sharing.
That describes the publisher's basis, not our downstream authority. No actual access
grant/terms file exists in the inspected local metadata. The public access form was
unavailable through the review tool; no form was submitted. The repository's MIT
software license is not proof of a dataset grant for paid third-party processing.
**Obtain the applicable grant/permission; transmission remains denied meanwhile.**

Only50 frozen validation OCR sources were screened; no train sources, PDFs or gold
fields/boxes/type were read for this screening. Candidate document counts: address30,
phone19, email7, signatory6, bank/payment5, personal-name3, confidentiality2, tax-ID1,
payment-credential context1. Each remains a manual-confirmation candidate.

The frozen adapter rejects5 of50:2 `EMPTY_OCR_PAGE`,3 `INVALID_OCR_WORD` (first
reported failure per document). Its strictness was **not changed**. A separate
read-only privacy view retains source word order, whitespace/page indices and
empty pages so every document can be screened. It exactly matches the frozen
canonical text on the45 accepted sources. The5 privacy-only views are explicitly
**not valid inference packets**. Their IDs/statuses are in external screening JSON.
No dropping, repairing, inventing OCR or normalizing away this incompatibility.

All50 decisions are `DENY` due to unresolved rights, with privacy/technical review
also required. Future separately approved adapter repair must preserve original
source evidence and frozen denominators; this phase does not implement it.

### Screening limitations

All checks are deterministic local patterns; qualified manual clearance has **not**
occurred. Absence of a match is not approval. OCR, obfuscated contacts, international
names/addresses and contextual confidentiality can evade patterns or create false
positives. Human review should occur locally against source-only material, not by
sending real documents back into chat. No automatic redaction or legal judgment.

## Tokens and exact arithmetic

No model-matching local tokenizer was established. No remote `countTokens` call
was made. [Google's token guide](https://ai.google.dev/gemini-api/docs/tokens)
gives roughly4characters/token; this report uses a deliberately more conservative
**planning estimate**: `ceil(serialized request UTF8 bytes /3) +256 framing tokens`.
It is **not exact tokenization or a mathematical upper bound**.

`request-cost-specification.json` records generic costing-only prompt/schema
prototypes, not approved inference prompts or production changes. SHA-256:
`ba8ddf041b44ea931b0ae4c6e03adbbf328c9dc3f5f65ae4fee909690260cdc1`.
Fixed overhead measured in serialized bytes: plan867, synthesis911, extraction810,
plus256 framing-token allowance per request. Full source/public-hypothesis/envelope
serialization is counted. Synthesis adds an assumed1024 input tokens for the prior
plan; actual generated content is unknown and remains inside the overall cap.
Changing a prototype/schema/configuration requires repricing before authorization.

| Frozen scored task | Calls | Estimated input | Capped input | Assumed output | Capped output incl. thinking |
|---|---:|---:|---:|---:|---:|
| NLI planning,12 documents |12|59,598|393,216|12,288|49,152|
| NLI synthesis,12 documents |12|72,063|393,216|24,576|49,152|
| ContractNLI total |24|131,661|786,432|36,864|98,304|
| DocILE50 |50|64,853|409,600|12,800|51,200|
| Combined final |74|196,514|1,196,032|49,664|149,504|

Per-document estimates (IDs only) are in cost JSON: NLI plan2,412–9,752 and
synthesis3,450–10,791; DocILE646–5,938. No token-count API or exact count is implied.
Output assumptions are1024 plan/2048 synthesis/256 extraction, not measured model
behavior. Maxima remain frozen32768/4096 per NLI call and8192/1024 per DocILE call;
no retries. [Thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)
describes combined thought/output accounting; future transport must verify/enforce
that cutoff on its chosen API. Truncated/failed outputs still consume reservations.

**Technical condition:** the input ceiling is not a setting automatically enforced
by this offline helper. A future transport must count the **complete actual request**
only after privacy approval, reject over-cap inputs and reserve each attempt before
generation, with SDK retries disabled. Counted schemas/system/prior-plan overhead
must agree with actual usage. No input estimate can substitute for this gate.

DocILE estimates include all50, including5 currently rejected sources; this is an
all-inputs-processable **hypothetical cost scenario**, not executable readiness.
Adapter smoke costs include3 permitted NLI dev documents and the frozen8 DocILE
train allocation. Train8 were not reopened: their expected input conservatively
uses their full frozen input allowance, with assumed256 output tokens/document.

## Paid cost scenarios — USD, before taxes/FX/fees

Formula: `input_tokens ×0.30/1,000,000 + output_tokens ×2.50/1,000,000`.
Machine JSON retains exact Decimal strings; no float money or intermediate rounding.
Expected cost is assumption-dependent, **not an exact bill**. Maximum is an exact
token-charge calculation **conditional on enforced caps**, not an all-in invoice.
INR conversion and local tax/card costs were not verified or invented.

| Scenario | Expected input | Expected output | Expected total | Worst input | Worst output | Maximum token charges |
|---|---:|---:|---:|---:|---:|---:|
| Final ContractNLI |$0.0394983|$0.0921600|**$0.1316583**|$0.2359296|$0.2457600|**$0.4816896**|
| Final DocILE |$0.0194559|$0.0320000|**$0.0514559**|$0.1228800|$0.1280000|**$0.2508800**|
| Final combined |$0.0589542|$0.1241600|**$0.1831142**|$0.3588096|$0.3737600|**$0.7325696**|
| Adapter smoke combined14 calls |$0.0347064|$0.0281600|**$0.0628664**|$0.0786432|$0.0819200|**$0.1605632**|
| Smoke + final88 calls |$0.0936606|$0.1523200|**$0.2459806**|$0.4374528|$0.4556800|**$0.8931328**|

Adapter detail: NLI expected$0.0380856/max$0.1204224; DocILE conservative
expected$0.0247808/max$0.0401408. Minimum prepaid funding (currently published$5)
exceeds the usage estimate; it is not the same thing as expected run consumption.

Optional full runs — **NOT AUTHORIZED**, no additional source documents inspected:

| Task | Calls | Sample-extrapolated expected cost | Maximum token charges |
|---|---:|---:|---:|
| ContractNLI123 test docs |246|$1.3494978|$4.9373184|
| DocILE500 val docs |500|$0.5145590|$2.5088000|
| Combined |746|$1.8640568|$7.4461184|

Full-run expectations extrapolate the frozen sample mean and may be wrong; full
privacy/readiness is unknown. No wholesale clearance or model-budget approval.

## Minimal future paid transport recommendation — proposal only

1. After rights/privacy clearance, explicitly authorize a **separate** non-production
   project/billing setup. No existing key/project change. If available in that future
   account, use minimum$5 prepaid/local equivalent and auto-reload disabled; confirm
   actual regional UI requirements and terms first. No action taken here.
2. Fix `gemini-3.5-flash-lite`, Standard pricing, minimal thinking, deprecated
   sampling parameters omitted, stateless requests, no tools/grounding/cache/
   contributor program or server conversation storage. Do not persist hidden thoughts.
3. Only approved source packets and the evaluation key are mounted. Gold, production
   credentials/DB/network and original dataset roots must be unavailable to the worker;
   permit only required Google HTTPS egress. Do not bypass synthetic-only product gates.
4. Before calls, verify that future project's actual model access, active billing,
   quotas, pricing and schema work on a separately approved synthetic control. No
   historical quotas assumed. One caller; proposed2 total HTTP operations/minute
   only if actual quotas permit, counting metadata/counting operations too.
5. No retries, including hidden SDK retries. At most14 smoke +74 scored generations
   if separately authorized. Use atomic local attempt/token/cost reservations and
   fail closed at **$0.8931328 pre-tax token allowance** for that full allocation
   (or$0.7325696 for final-only). No retry spend hidden inside that ceiling.
6. Log only IDs/hashes/fixed status, latency/tokens/cost; no prompts, response bodies,
   raw matched values, keys or URLs containing secrets. Predictions with necessary
   evidence quotes remain restricted local artifacts, outside Git/public reports.
7. Seal predictions and input/code/prompt/model hashes before separate gold scoring.
   Preserve failures/abstentions in frozen denominators. Disable key/API/project
   access afterward under explicit operator instruction; cleanup does not imply
   immediate provider deletion. No billing/purchases/project changes executed here.

## Outputs and offline verification

All machine outputs: `C:\ClearLedgerEval\external-runs\phase1-5-v1\`:

- `provider-terms-snapshot.json`, `reference-snapshots/`: official metadata/public docs only.
- `dataset-rights.json`: local license/terms hashes and rights findings.
- `screening-contractnli.json`, `screening-docile.json`: every frozen ID/categories/
  counts/decision/rationale; no raw source or snippets.
- `request-cost-specification.json`: fixed costing-only generic templates/schemas.
- `token-cost-model.json`: per-document estimates, exact Decimal scenarios and caveats.
- `decision-matrix.json`, `review-summary.json`: blockers/coverage, no inference approval.
- `verification.json`: exact frozen-ID coverage, check results and artifact/code hashes.

The helper reads only source fields via Phase1's whitelist, never imports gold
readers/scorers/application/provider SDK. It checks frozen source digests and does
not write source text. Initial review exposed the5 strict-adapter rejections;
privacy-only screening records preserve those failures rather than fix them.

Executed command (existing reports refuse overwrite):

```powershell
.venv/Scripts/python.exe scripts/external_privacy_cost.py --source C:/ClearLedgerEval/external --runs C:/ClearLedgerEval/external-runs --output C:/ClearLedgerEval/external-runs/phase1-5-v1 --provider-snapshot C:/ClearLedgerEval/external-runs/phase1-5-v1/provider-terms-snapshot.json
```

Focused checks cover screening candidates without values, no automatic clearance,
no silent redaction, frozen empty-page/word rejection, exact decimal sums, invalid
money inputs, output/thinking reservations and fixed sample/call caps. No inference,
API billing/key interaction, full app suite, DB, Docker or browser checks required.
No Phase2 execution is authorized by this report.

## Subsequent user authorization — additive transition,2026-10-27

The user has now explicitly confirmed reviewed dataset permissions and authorized
DocILE/ContractNLI evaluation/API processing where provider terms permit it. See
[authorization amendment](EXTERNAL_EVALUATION_AUTHORIZATION.md). The earlier
screening/rights findings above remain historical observations; they are not
rewritten as if clearance existed then. No source was redacted or altered.

| Dataset | Current dataset rights | Current API-processing scope | Provider gate | Current execution status |
|---|---|---|---|---|
| ContractNLI | USER-RESOLVED / AUTHORIZED FOR THIS EVALUATION | User-confirmed, only exact requests permitted by provider terms | Suitable paid project/key not verified | STOPPED_AT_PROVIDER_BILLING_GATE |
| DocILE | USER-RESOLVED / AUTHORIZED FOR THIS EVALUATION | Same restriction; prior research-grant blocker resolved by user attestation | Suitable paid project/key not verified | STOPPED_AT_PROVIDER_BILLING_GATE;5 known input failures retained with zero calls |

This resolves dataset rights, not provider policy, production consent, unrelated
data use or public redistribution. Existing pattern-screen categories remain
findings. The Phase2 instruction explicitly preserves the five DocILE failures
without requiring their repair or replacement. There has been no model call.

Observed verification: **89 offline tests passed in4.66s** (61 frozen Phase0/1
regressions +28 review tests); Ruff lint/format, strict mypy and compilation pass.
Frozen plan hash/provenance check passes; Git comparison confirms Phase1 code,
evaluator lock and Phase0 specification unchanged.

```powershell
.venv/Scripts/python.exe -m pytest --noconftest tests/test_external_phase0.py tests/test_external_phase1.py tests/test_external_privacy_cost.py --basetemp .local-runtime/phase1-5-tests-final -q
.venv/Scripts/python.exe -m ruff check scripts/external_privacy_cost.py tests/test_external_privacy_cost.py
.venv/Scripts/python.exe -m ruff format --check scripts/external_privacy_cost.py tests/test_external_privacy_cost.py
.venv/Scripts/python.exe -m mypy --strict --follow-imports=silent scripts/external_privacy_cost.py
.venv/Scripts/python.exe -m py_compile scripts/external_privacy_cost.py
```

Use a fresh nonexistent workspace basetemp on reproduction. Corpus reports use
exclusive creation; do not overwrite them or the frozen protocol. Public source
snapshots and review metadata are outside Git. No full application verification,
restart, browser or benchmark run was performed or needed for this offline review.
