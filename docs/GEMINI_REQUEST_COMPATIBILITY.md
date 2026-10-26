# Offline Gemini extraction compatibility review — 2026-10-26

Subsequent authorized verification,27 October: exactly one request using this
schema failed at CONTENT_GENERATION / HTTP503 / provider status UNAVAILABLE. This
does not prove the prior400 was fixed or that schema compilation succeeded. No
successful live extraction is established. Full measured result: [live report](LIVE_GEMINI_EVALUATION.md).

## Finding and limits of the evidence

The latest real attempt established CONTENT_GENERATION / HTTP_API / HTTP400 after
model lookup/token-count checks passed. The provider body was intentionally not
retained. **No specific rejected field is established, and no live repair is claimed.**
This task made no Gemini/model/quota/token-count/generation call; only public Google
documentation was fetched. The remaining conservative budget stays66 paise.

Reviewed the locked **google-genai2.33.0** implementation and captured its actual
serialized request with httpx.MockTransport, which cannot contact Google. The
original request contains contents/systemInstruction/tools and generationConfig:
candidateCount1, maxOutputTokens512, temperature0, responseMimeType application/json
and responseJsonSchema. Automatic-function-calling controls do not leak onto the
wire. SDK t_json_schema passes the supplied dictionary through unchanged.

[Google's model specification](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
lists structured output for this exact model. The
[generateContent reference](https://ai.google.dev/api/generate-content) documents the
JSON MIME type and responseJsonSchema field/subset. No local evidence identifies a
wrong MIME type, misspelled wire field, model switch, mutually exclusive responseSchema,
unsupported automatic-function-calling field, or SDK serialization corruption.
Deprecation in current docs is not evidence that an accepted legacy field caused400.

[Google's structured-output guidance](https://ai.google.dev/gemini-api/docs/structured-output)
identifies bounded arrays and numeric ranges as possible decoder-complexity causes
of400. It also says string-length constraints are ignored. Therefore minLength/
maxLength are **not** established causes, and documented $defs/$ref/anyOf/closed
objects are not arbitrarily declared unsupported. Original JSON size2238 bytes alone
does not establish an oversized request. Token-count success does not prove that
generation-time constraints can be compiled.

## Small provider-only compatibility mitigation

`gemini_schema.remittance_response_schema()` exports the existing field structure
without minimum/maximum, minItems/maxItems or minLength/maxLength. This removes the
explicit bounds risk (including100-item lists and the signed-bigint monetary maximum)
from the provider decoder, and redundant ignored string limits. It retains all
field names, integer/null types, required fields, enum values, references and
additionalProperties=false. Serialized schema size becomes1961 bytes. No generation
parameter, MIME type, provider/model or prompt change was made.

**This is a documented-risk mitigation, not a proven diagnosis of the previous400.**
Offline checks cannot reproduce Google's private schema compiler or establish
service acceptance. A single later authorized live result is still needed.

ClearLedger's internal Pydantic schema is unchanged byte-for-byte in tests: strict
integer paise, bigint/range/page/offset/string/list bounds and extra-field rejection
remain enforced independently. Parent decoding, privacy restoration, source quote/
amount/category verification and document ownership/version/integrity checks still
run before facts are stored. Wire bounds never authorize money or trust a citation.
Existing100KiB response and token/process limits remain in force.

Both countTokens' embedded request and actual generateContent serialization use the
same new schema, system text, data and generation settings (structurally compared
using the real SDK). Only remittance extraction uses this export; the investigation
schema/provider path is unchanged and external investigations remain disabled.
The original v1 contract is historical; current `gemini-remittance-shape-v4` is
persisted in extraction input provenance/cache identity. It adds explicit page-base/
source-containment instructions and bounded exact token positions derived solely from
projected text; it never repairs returned citations. The internal schema is unchanged.
The3.5 live experiment reached persisted core facts and valid source spans, with one
incorrect optional reason-code classification; see LIVE_GEMINI_EVALUATION.md.
Legacy rows default to strict-domain-v1. Non-Gemini request input shape/idempotency
remains unchanged, with a specific replay regression test. No historical extraction is rewritten or
silently reused under a different wire contract. CSV1.0/internal extraction1.0 remain
unchanged; no migration or financial-rule change is required.

## Offline verification and intended AI value

- Local SDK serialization proves the old/new request envelopes differ only in the
  schema dictionary; JSON mode, zero tools, disabled automatic functions and512
  output limit remain identical.
- Actual API + real SDK tests intercept every HTTP operation in memory. The
  existing synthetic free-form PROSE first returns deterministic NEEDS_REVIEW with
  no SDK activity, then a deliberately scripted response traverses the real
  transport/domain/source-validation/persistence path.
- Negative controls reject floats, negative/over-bigint amounts, wrong source money,
  fabricated spans, added financial authority, oversized reference lists and invalid
  uncertainty. API responses retain review/no authority; financial state is unchanged.
- Scripted acceptance demonstrates plumbing only, **not model reasoning or live AI
  success**. This task establishes no accuracy improvement or successful Gemini run.
- Initial focused run:88 passed, seven new API contract cases failed because the
  test adapter omitted run_worker's default timeout. Corrected the test signature;
  no production failure was inferred from that harness mistake. Final affected
  contract/cache/quota/refusal run:39 passed in60.89s. Final Gemini-only version-scope
  and schema check:16 passed in21.12s, including legacy disabled-provider replay.
  Combined focused coverage:117 distinct tests passed across these runs. Ruff passed;
  no full suite or Docker build.

The intended live value is narrow: extract invoice I-1 and an asserted damage
deduction101 paise from the unchanged free-form sentence that the deterministic
parser abstains on. Payment INR9.00 is not another deduction. Payment-total extraction
is not part of the current schema. Do not convert the fixture to strict lines/JSON
just to make a demonstration pass.

## Acceptance gate for ONE separately authorized live test

1. Obtain new explicit authorization. Recheck same model/key access, current official
   pricing/FX, project quotas and exact approved privacy projection. No billing change.
2. Fresh disposable PostgreSQL only. Same original PROSE bytes, current canonical
   text/hash/version and synthetic upload attestation. External investigations off.
3. One caller, one attempt, one document. Cap input2048/output512 and reservation17
   paise, within remaining66; after an uncertain attempt retain the reservation.
   The existing runner now records remaining66 and cannot continue to other fixtures.
   Its date-bound price-review lock must be honored, not bypassed on a later day.
4. Count tokens for this exact wire schema/system/data before generation; abort if
   limits fail. No model switching, output-cap escalation or automatic retry.
5. Actual Gemini output must enter the existing persisted extraction result and
   be SUCCEEDED or NEEDS_REVIEW **with valid facts**, not merely HTTP200. Expected:
   invoice reference I-1; one damage claim amount101 paise; no invented UTR, payer,
   deduction900, reason code, approval or statutory conclusion. Unknowns remain explicit.
6. Independently verify invoice/description/amount source spans against the exact
   document via the real API; original/canonical integrity, tenant/version checks,
   uncertainty, requires_human_review=true and financial_authority=false remain mandatory.
7. Compare financial fingerprints unchanged. Record source-linked facts, missing/
   unsupported fields, invalid citations, real usage/latency/estimated cost (or UNKNOWN).
   On failure retain only sanitized diagnostic phase/category/status and stop.
8. Disable/clear process external-AI settings/key/gateway; persistent defaults stay off.
   Report the actual outcome and consume at most17 more paise, leaving at least49
   conservatively. A mocked contract pass cannot satisfy this live acceptance gate.

No frontend, benchmark, sealed split, hidden ground truth, operator, new framework
or dataset was accessed/changed by this task. Local commands/logs/checkpoint: STATUS.md.
