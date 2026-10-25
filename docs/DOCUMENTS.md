# Document intelligence contract — milestone 04

Version: **remittance-extraction-1.0**; canonical parser **canonical-text-v1**; privacy projection **projection-v1**. This is a separate interface from financial CSV DATA_CONTRACT v1.0. All four CSV schemas/identities/import ordering remain unchanged. Argon supplies realistic documents/datasets; none are bundled/generated/imported automatically. Examples/test inputs are minimal isolated code fixtures.

## Access and local configuration

Every `/documents` endpoint requires `Authorization: Bearer <DOCUMENT_API_TOKEN>`. Configure a random token of at least 32 characters in ignored `.env`; absent/weak configuration fails closed with 503, absent/wrong credentials with 401. Company ownership comes only from server `ORGANIZATION_ID`, never a body/header selector. Unknown/foreign IDs return 404. Document responses use no-store/nosniff; originals are attachment-only octet-stream with generated UUID filenames. Actor/key headers are required for uploads/extraction/correlation. This local shared-secret boundary protects document access; it is **not** user roles, maker-checker, source authentication or a remedy for audit G1's unauthenticated financial APIs/actor labels. Run locally with approved synthetic data.

Settings: `DOCUMENT_ROOT=local-data/documents`, `DOCUMENT_API_TOKEN` (SecretStr), `EXTRACTION_PROVIDER=disabled|gemini|fake` (default disabled), `EXTERNAL_AI_ENABLED=false`, `GEMINI_API_KEY` (SecretStr), `GEMINI_MODEL` (explicit supported model ID), `PRIVACY_REVIEW_REFERENCE` (operator's privacy/provider-terms review reference), `LLM_TIMEOUT_MS=10000` (100–30000), `LLM_ATTEMPTS=2` (1–3), `LLM_REQUESTS_PER_MINUTE=10` (1–60). Fake transport is injected explicitly in tests, never a fabricated default answer. `.env.example` contains no credentials. No API returns keys/configuration or supplies them to a frontend/model prompt.

Gemini uses the official **google-genai 2.33.0** SDK, locked with **pypdf 6.21.2**. References checked 2026-10-25: [Google SDK](https://googleapis.github.io/python-genai/), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [PDF text limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html). Model availability and provider terms require an operator review; no hardcoded price/model selection or live-provider accuracy claim is made.

## Ingestion and storage

`POST /documents` takes **raw bytes**, not multipart. Headers: actor, UUID Idempotency-Key, X-Source-Filename (basename ≤128 characters), Content-Type, optional `X-Synthetic-Data: true|false` (default false; explicit attestation, not automatic proof). Supported pairs: application/pdf/.pdf, message/rfc822/.eml, text/plain/.txt, application/json/.json. HTML, archives, office/binary formats and mismatched extensions are unsupported. Filenames with paths/drives/control characters/leading dots are rejected. Text is strict UTF-8 (optional BOM); financial CSV rules are unaffected.

Limits: nonempty ≤2,097,152 bytes streamed before storage; ≤20 PDF pages; ≤100000 canonical characters across pages. PDF limits include 4096 dictionary/array/object budget, bounded page-tree/form traversal, 2 MiB stream expansion, 8 MiB accumulated decoding and allowlisted text filters (Flate/ASCIIHex). Active content, encryption, unsupported filters, malformed pages and exhausted resources fail closed. Images are not decoded for OCR; empty/scanned or mixed empty pages become NEEDS_OCR, with no invented text/model fallback. PDF text spans are **canonical text**, not verified visual layout/bounding boxes. Lost layout is never evidence of a reliable invoice/amount relationship; human review remains required.

Email supports plain text and bounded MIME plain-text parts (≤32, decoded bytes ≤2 MiB). UTF-8/ASCII only; HTML, attachments/archives, unsupported charsets/transfer encodings and MIME defects fail closed. No attachments are expanded/saved, no external resources fetched, no sender-address identity inferred. Canonical email includes Subject (if present) and plain body; address headers remain only in originals. An arbitrary Subject/body requires semantic extraction/review instead of silently discarding potentially relevant text.

Original SHA-256 hashes exact uploaded bytes. The local adapter's logical key is `(organization UUID, raw SHA-256)` under the configured root, never an uploaded path/name. Exclusive creation, fsync, no overwrite/delete API, tenant directories and digest checks implement logical immutability; DB originals/metadata/history also reject UPDATE/DELETE/TRUNCATE. Canonical pages normalize CRLF/CR→LF, strip a UTF-8 BOM for text, preserve page order and reject controls other than LF/tab. Canonical SHA-256 hashes compact JSON serialization of the pages array using the existing `matching.digest` serialization (sorted keys, default ASCII escapes, UTF-8). Page offsets are zero-based **Unicode character** offsets, exclusive end; page numbers start at 1. They are not original byte offsets or PDF visual coordinates.

Same company/content bytes deduplicate to one document and ingestion event. A new key for the duplicate adds a request mapping, not another ingestion event. Same key/body survives renames/restarts; changed bytes/MIME/synthetic attestation under a key conflict. Reclassifying existing bytes with another MIME/synthetic flag also conflicts. Unsupported/oversize transport is rejected before storage; supported malformed sources retain immutable originals with PARSE_FAILED and HTTP 422 `{document_id,code}`. Scans return NEEDS_OCR. No partial financial import or financial mutation occurs.

Original file writes precede DB commit; a crash can leave an unreferenced blob. It cannot overwrite a known original. Automatic deletion/orphan cleanup is deliberately absent. Storage root/DB/backups need trusted host permissions; this is not WORM/tamper-proof against a host/database administrator. Integrity failure blocks reading/external extraction; original corruption is never silently repaired.

## Extraction schemas and routing

`POST /documents/{id}/extract` body:

```json
{"expected_document_version":1,"revision_label":"initial","allow_external":false}
```

Strict integer version and boolean; extra fields rejected. Different revision_label explicitly appends another extraction run. Natural identical-input/configuration attempts reuse one immutable run, including failed/blocked ones. Same key with another operation/body conflicts; changed configuration under a prior key conflicts. Snapshot includes source/canonical hashes, versions, parser/schema/privacy versions, model/provider and effective limits/rates; elapsed time is not input identity. Extraction versions increase per document, without editing earlier results/originals.

Routing is deterministic code: exact supported structured JSON/line format → deterministic parser, otherwise → review, or explicitly permitted Gemini if semantic extraction is required. Model routing cannot select an expensive fallback automatically. External calls require **all** of: server enabled, privacy/provider review reference present, configured provider/model/key/transport, explicit request allow_external, and upload marked approved synthetic. Unmarked documents remain blocked even with a configured provider. Merely configuring a key does not enable a call. This task/CI never authorizes a paid call. Real-data transmission remains unsupported pending explicit privacy/provider-terms review and broader security controls.

Output fields (strict Pydantic, no extra fields at any nesting):

| Field | Contract |
|---|---|
| invoice_references | Up to 100 `{value,span}`; value string ≤200, exact source literal |
| utr_references | Up to 20 source references; never inferred from an invoice/payer/amount |
| payer_hint | Source reference or explicit null; not customer identification |
| claims | Up to 100 objects: category, description span, amount_paise or null, amount_span or null, reason_code source reference or null |
| category | tax/damage/short_shipment/rebate/early_discount/other/unknown; source assertion only, no TDS/GST/legal adjudication |
| amount_paise | Strict integer 0..9223372036854775807, never float/bool/string; unknown is null |
| uncertainty | none/review/unknown; never accounting authority |
| unparsed_fields | Up to 100 exact source spans; no invented explanatory prose |

Span: `{page,start,end,quote}`; quote nonempty ≤2000 characters and exactly matches canonical page slice. Parent validation independently checks page/ranges/quote, complete identifier boundaries and appropriate invoice/UTR labels; exact words elsewhere cannot become references of another kind. Claims need a source cue for category, explicitly sourced amount inside the claim, and any reason code inside that same claim. Monetary units must be explicit INR/Rs (≤2 decimal places) or integer paise. Ambiguous money/bare prose numbers reject; structured JSON amounts are explicitly declared paise. No rounding/tolerance guesses, unsupported currencies, negative deductions, invented missing values or approval fields. Invalid Unicode, controls, duplicated JSON keys, nonfinite constants, malformed/oversized outputs and fabricated spans/amounts fail closed.

Result envelope records schema/run version, route/reason, status SUCCEEDED/NEEDS_REVIEW/FAILED/BLOCKED, fixed error code, provider/model, usage/latency/cost metrics and input hash. **Every result** has `financial_authority=false`, `source_authenticity=UNVERIFIED`, `requires_human_review=true`, `layout_verified=false`. SUCCEEDED means supported extraction/schema consistency, not authentic source, legitimate claim, authorization or approved settlement. Raw model replies/prompts are not persisted/logged; only validated facts/spans or controlled failure metadata are stored.

### Deterministic structured formats

JSON document interface **remittance_version 1.0**, distinct from CSV contract v1.0. Exact required keys:

```json
{
  "remittance_version":"1.0",
  "invoice_references":["<exact invoice_number>"],
  "utr_references":["<exact bank external_transaction_id>"],
  "payer_hint":null,
  "claims":[{"category":"damage","amount_paise":101,"reason_code":"damage"}]
}
```

References are nonempty ≤100 characters; payer_hint null or ≤200; category/amount/reason_code fields all required, nullable money/reason explicit, reason ≤100. Lists use the bounds above. Extra keys, duplicate keys, unsupported versions and excessive nesting reject; JSON Pointer-aware lexical parsing locates exact source tokens/claim objects, including escaped strings. Values cannot use internal tenant IDs or declare financial approval. This is a schema example, not a dataset; Argon may construct files against it without changing application tables.

Offline line format: nonblank lines must be exactly `INVOICE: <reference>`, `UTR: <reference>`, optional single `PAYER: <hint>`, or `CLAIM <category>: INR 1.01` (also Rs / integer paise). Anything beyond this strict grammar requires semantic extraction/review; no heuristic "fixture answer" is fabricated.

## Privacy and isolation

Provider preprocessing detects PAN/GSTIN, IFSC, bank-account context, contacts, phone/email/URLs and labeled personal fields. Beyond detectors, unknown words/numbers/symbols are masked by a small **financial vocabulary allowlist**. Only recognized labeled invoice/UTR references and explicit financial amounts are deliberately retained. Known sensitive content overlapping an essential reference/amount fails closed, rather than silently sacrificing privacy or inventing a relationship. This may abstain on long numeric IDs/amounts or atypical formats. Names/addresses in narrative are not assumed safe because regex detectors missed them; unknown words are masked. Allowlisted financial words can still be ambiguous names/context, so this is a conservative projection, **not a proof that arbitrary real documents are anonymized**.

Masking preserves Unicode character lengths/page offsets. The reversible mapping is private in-memory span metadata plus original canonical text in the trusted orchestrator; it is never persisted/exported to the provider/API/logs. The provider sees only projected pages (not original bytes, addresses/filename/actor/DB URL, token mapping or finance policy). Parent validates output spans against the exact projection, restores source text by offsets and independently checks semantics against the original canonical text. This preserves auditability without sending originals; restored source spans remain confidential and require document authentication.

Parser and transport are separate credential-isolated subprocesses, with minimal environment and bytecode writes disabled. Parser: no network. Both: no subprocess/tools, no application/.env/policy-file reads or filesystem writes after trusted imports, no DB credentials/session/functions. Gemini transport alone permits DNS for generativelanguage.googleapis.com and connections to its resolved public addresses on port 443; no local DB, arbitrary URL, Google File upload or tool/agent interface. SDK automatic function calling is disabled and tools are empty. API key is explicit private stdin configuration, not command-line arguments or model content. SDK logs/child stderr are suppressed; parent stores fixed codes, never exception bodies. Verification redacts URL/password/key/token/secret configuration from logs.

Limits: at most 2 worker jobs/process; parser wall timeout 10s; Windows Job aggregate memory 512 MiB, 2 processes (venv launcher + interpreter), kill-on-close; POSIX 512 MiB address space, 5 CPU seconds, zero file/core-output limits. Gemini request timeout is configurable with a hard parent deadline (+3s); retries bounded 1–3, SDK hidden retries disabled. Per-process gateway concurrency 1 and sliding-window requests/minute count **each attempt**; no distributed quota is claimed. JSON output ≤100 KiB, max model output 4096 tokens. Resource/sandbox unavailability fails closed, never silently runs unbounded. Python audit guards/resource jobs are defense in depth; they are **not** an OS principal/container isolation guarantee against arbitrary dependency RCE. Production/shared real-data use requires stronger isolation, least-privilege storage/DB and review; G1 remains open.

Metrics include reported input/output (output includes reported reasoning), total/reasoning/cached counts where supplied, latency_ms, actual attempts and usage_complete. Missing/failed-attempt usage is unknown. Optional configured INR paise-per-million-token rates produce integer ceiling estimated_cost_paise only for complete usage; absent rates/partial retry usage yields null, never invented zero. Estimates are not provider billing/FX facts. No prompt/result body is in telemetry.

## Late remittance correlation and reads

`POST /documents/{id}/correlate`:

```json
{"extraction_id":"<UUID>","expected_document_version":1,
 "verified_utr_values":["<locally verified exact UTR>"],
 "expected_receipt_versions":{"<receipt UUID>":1}}
```

Local authenticated operator attests the **complete extracted UTR set**, not the legitimacy of claims. Without attestation only candidates are stored. Only one exact UTR, exactly one company bank/receipt match, valid bank source, latest successful extraction, nonconflicting verified customer identity and known consistent invoice owners can link. Unknown referenced invoices, conflicting owners/identity/evidence, superseded extraction, wrong UTR or duplicate UTR across accounts/sources abstain. UTR-only association does not assign a customer. No amount/name fuzzy matching, cross-company lookup, invoice eligibility/application inference or source-authenticity claim is made. Candidate lookup is capped at 101 (100 + overflow), yielding SEARCH_INCOMPLETE on overflow. Ambiguous candidates do not trigger repeated source parsing/automatic selection.

Associations persist LINKED/CANDIDATES/UNRESOLVED/SEARCH_INCOMPLETE, candidate IDs, exact source/version snapshot and explanation. LINKED requires expected target receipt version. Different concurrent keys reuse the same immutable snapshot and creation event under the existing company lock/DB uniqueness. New receipt collisions, versions, evidence/identity/owners or extraction revisions stale old associations; GET computes is_stale, retries conflict instead of silently accepting changed inputs. A stale LINKED row is historical, never a financial action. No case/version/claim lifecycle or asynchronous event engine exists until milestone 05.

Reads: GET `/documents` and `/{id}`, `/{id}/original`, `/{id}/text`, `/{id}/extractions`, `/{id}/associations`, `/{id}/events` (histories limit 1–100, offset≥0). POST `/{id}/verify-span` independently checks original/canonical hash and the supplied span; returned pointer includes immutable document ID/version/raw+canonical digests. Source consistency is not provenance authenticity, signed approval, ownership/date-policy validity or claim legitimacy; generalized evidence adjudication remains milestone 06.

## Persistence and verification

Migration **0005_documents** adds documents, document_extractions, document_associations, document_operations and document_events. All have UUID/company/version/UTC creation fields, scoped FKs/indexes/uniqueness and immutable update/delete/truncate triggers. Document content is unique/company; extraction input hash and increasing version are unique/document; association input snapshots and operation keys deduplicate. No financial tables/CSV kinds are modified. Development is upgraded **up only**, with pre-existing row fingerprints compared; migration roundtrip/destructive integrity tests use independent disposable databases. Raw local storage must be preserved/backed up separately from PostgreSQL.

`uv run --frozen python scripts/verify.py` retains all financial/matching/restart/concurrency/migration/dependency/lint/format checks and expands strict typing/security tests. Offline defaults override local model settings in tests; fake provider/real SDK over MockTransport exercise construction/validation with **no paid requests**. Real HTTP import/application restart, original/canonical/hash/span checks, MIME/PDF limits, privacy leakage, hostile documents/outputs, worker capabilities, retries/rates, upload/extraction races, tenant/auth and non-mutation are tested. See STATUS for actual results/logs. Live Gemini/provider terms, OCR, real-data privacy, remote Actions/Linux application execution and Argon accuracy benchmarks remain explicitly unverified/deferred. STOP at milestone 04.
