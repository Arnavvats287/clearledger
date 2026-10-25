# ClearLedger data contract — version 1.0

M08 adds a **separate** finance-1.0 simulation API in
[ACCOUNTING_SIMULATOR.md](ACCOUNTING_SIMULATOR.md). CSV schemas, identity rules, paise
representation and ordering are unchanged. Imported labels grant no financial authority;
no dataset is generated, modified or seeded.

Milestone 04 adds a **separate** authenticated document interface and versioned remittance JSON/extraction contract in [DOCUMENTS.md](DOCUMENTS.md). PDF/email/text/JSON bytes go to `/documents`, never the financial CSV importer. No CSV columns, amounts, IDs, natural keys, order or version changed. Argon can supply documents against that separate contract; no Argon data is generated, modified or assumed integrated. Extracted references/claims are untrusted facts, not approved financial data or direct table-import instructions.

Milestone 03 retains **all four CSV schemas, import ordering and version 1.0 unchanged**. Its additive proposal/evidence API is specified in [MATCHING.md](MATCHING.md#advanced-matching--milestone-03--advanced-mitm-v1). Argon need not modify existing CSVs. To exercise explicitly instructed multi-invoice partials, Argon may optionally put `{"allocations_paise":{"<invoice_number>":<positive_integer_paise>}}` in the original bank `memo` CSV field (normal CSV JSON quoting, total memo ≤2000 characters). Matching requires separate source-backed INVOICE_REFERENCE attestations for every exact key and an explicit structured-mode API request. This optional memo convention is not a new required CSV column, automated trust, a separate dataset import or a change to monetary semantics. Document/remittance-file ingestion remains milestone 04; no Argon files are modified/generated here.

Status: milestone 01 import contract, retained unchanged by milestone 02. Send `X-Data-Contract-Version: 1.0` on every import. A change to column names, types, identity rules or meaning requires a new contract version and, where needed, a migration. Unsupported versions return 422. This contract describes application inputs and persistence; it does not supply or authorize a demonstration dataset. Milestone 02 matching metadata is an additive API extension described below; Argon's CSV formats remain 1.0.

**Argon owns dataset research and construction. Codex does not generate, download, curate or seed demonstration/evaluation data.** Argon should provide compatible CSV files; do not insert directly into application tables, assign internal IDs, modify the schema, or depend on the old `fixtures/demo-case.json` as an import format. That existing reference is unchanged. Minimal isolated code-test fixtures are separate from dataset artifacts.

## Company configuration and trust

One deployment serves one company. Set `ORGANIZATION_ID` in `.env` to the company's UUID, apply migrations, then explicitly provision that company with:

```powershell
uv run --frozen python -m clearledger.cli init-organization --name "<your company name>"
```

Provisioning creates only the organization row (UUID/name), never customer or financial data. The command is idempotent for the same UUID/name and refuses an existing UUID with a different name. There is no organization upload or tenant-selection API. Missing/unprovisioned configuration produces 503 on business endpoints; process health and database readiness remain independent.

Every business query and import derives its company from this server setting. CSV files must not contain `organization_id`, `tenant_id`, internal UUIDs, versions or generated balances. Foreign keys use company plus internal ID, preventing a reference from crossing companies even through direct database writes. Two companies may use the same external references independently.

`X-Actor-ID` is a required, locally asserted provenance label (1–100 ASCII letters/digits/`_.@-`), **not authenticated identity**. Authentication/roles are not implemented in this milestone. Run the API on loopback with local test data; headers and alias verification metadata are not controller approval or accounting authority. No source text is executed or treated as instructions.

## CSV transport and validation

POST raw file bytes to `/imports/customers`, `/imports/payer-aliases`, `/imports/invoices` or `/imports/bank-transactions`. Required headers:

| Header | Value |
|---|---|
| Content-Type | `text/csv` (optional charset parameter; bytes must still be UTF-8) |
| X-Data-Contract-Version | `1.0` |
| Idempotency-Key | A UUID chosen by the caller for this request; retain for retries |
| X-Actor-ID | Local operator label described above |
| X-Source-Filename | CSV basename, 1–128 characters, ending in `.csv`; no path separators/NUL; metadata only |

UTF-8 with an optional initial BOM, comma delimiter, RFC-style double quoting, LF or CRLF record endings. A single header row is required. Column order may vary, but the **exact column set** must match one of the four schemas below. Duplicate, extra, missing or padded header names are rejected. Every listed column is required, including the two bank columns whose cell values may be empty. No blank records, surplus/missing cells, control characters (including tabs/newlines within cells), NUL, or leading/trailing whitespace in any value. Values are never silently trimmed. Quoted commas/double quotes in text are allowed.

Limits: **2,097,152 bytes**, **10,000 data rows**, at least one data row. Oversized bodies return 413 before ingestion and are not persisted. CSV parser fields also have Python's default 131,072-character limit; lower per-field schema limits apply. Validation reports up to 100 row/field errors. Row numbers count logical CSV records, including header as row 1; the first data row is row 2. A malformed CSV syntax error reports the parser's physical line. No spreadsheet formula is evaluated; strings are retained as untrusted data.

All identifiers are strings, never numbers (so leading zeros in **identifiers** are preserved). Identifiers are case sensitive unless explicitly noted. Empty strings are forbidden except `payer_name` and `memo`. Maximum lengths are Unicode character counts. `null`, `NULL`, `NaN` and whitespace are not special missing-value markers.

Money is **integer paise**, not rupees. CSV lexical form is `0` or a nonzero digit followed by up to 18 further digits. No sign, decimal point, comma, exponent, padding, boolean, missing amount or float. Range: 0 through **9,223,372,036,854,775,807** (signed PostgreSQL BIGINT maximum), subject to stricter positivity rules below. JSON read APIs return integer numbers. No conversion or rounding happens during import. Domain conversion utilities are separate. Currency is exactly uppercase `INR`.

Dates: exactly `YYYY-MM-DD`, valid Gregorian calendar dates, independent of timezone. Financial dates are supplied using the relevant India local calendar. Timestamps: `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` or the same with an explicit `+HH:MM` / `-HH:MM` offset; 1–6 fractional digits if present. No naive timestamps, epoch values or locale date guessing. Stored timestamps and API timestamps use UTC. Bank `occurred_at_source` retains the original timezone-bearing string. Raw import bytes retain original date/time text for every source. Server `created_at` is UTC, generated on ingestion.

## Exact input columns

### customers.csv → POST /imports/customers

```csv
external_reference,name
```

| Column | Type | Constraints |
|---|---|---|
| external_reference | string | Required, 1–100; unique within company; stable external customer key |
| name | string | Required, 1–200 |

Natural identity: `(organization_id, external_reference)`. Exact same name is a duplicate; a different name under the same key is a conflict. Import does not rename customers. Creation provenance links through the append-only `customers.created` audit event (`entity_id` → customer UUID; source run and row → original CSV). Existing milestone 00 customers are preserved and remain import-compatible.

### payer-aliases.csv → POST /imports/payer-aliases

```csv
customer_reference,alias,verified_by,verified_at,evidence_reference
```

| Column | Type | Constraints |
|---|---|---|
| customer_reference | string | Required, 1–100; existing customer external_reference in this company |
| alias | string | Required, 1–200; normalized form must also fit 200 characters |
| verified_by | string | Required, 1–100; supplied verification provenance, not authentication |
| verified_at | timestamp string | Required, max 40; explicit timezone |
| evidence_reference | string | Required, 1–200; supplied stable verification source reference |

Natural identity: `(organization_id, normalized_alias)`, where normalization is `" ".join(alias.split()).casefold()`. This is only an alias uniqueness rule, not payer resolution or a matching algorithm. The same normalized alias cannot point to multiple customers. Differences in the alias's original spelling or other substantive fields are conflicts. These are asserted verification records; this milestone neither validates external evidence nor uses an alias to assign receipts. Do not put secrets or personal bank credentials in evidence references.

### invoices.csv → POST /imports/invoices

```csv
customer_reference,invoice_number,issued_date,due_date,original_amount_paise,open_amount_paise,currency
```

| Column | Type | Constraints |
|---|---|---|
| customer_reference | string | Required, 1–100; existing customer external_reference in this company |
| invoice_number | string | Required, 1–100; unique within company, not just within customer |
| issued_date | date | Required |
| due_date | date | Required; on or after issued_date |
| original_amount_paise | integer paise | Required; strictly positive gross original billed amount |
| open_amount_paise | integer paise | Required; 0 ≤ opening/current imported balance ≤ original_amount_paise |
| currency | literal string | Required; `INR` |

Natural identity: `(organization_id, invoice_number)`. Imported open balance becomes **both** `initial_open_amount_paise` and `open_amount_paise`. The former is the immutable opening baseline for future application reconciliation, not necessarily the gross billed amount. Import does not reconstruct prior payments. Status is generated: `OPEN` when balance > 0, `CLOSED` when zero. No matching, allocations, tax components or invoice lines exist yet. Replay never overwrites current balances; it compares the original imported payload.

### bank-transactions.csv → POST /imports/bank-transactions

```csv
source_system,account_ref,external_transaction_id,occurred_at,amount_paise,currency,payer_name,memo
```

| Column | Type | Constraints |
|---|---|---|
| source_system | string | Required, 1–100; stable source namespace |
| account_ref | string | Required, 1–100; stable local account token; use nonsecret synthetic identifiers |
| external_transaction_id | string | Required, 1–100; source's stable unique transaction ID/UTR |
| occurred_at | timestamp string | Required, max 40; explicit timezone |
| amount_paise | integer paise | Required; strictly positive incoming credit amount |
| currency | literal string | Required; `INR` |
| payer_name | string | Column required; empty allowed; max 200; untrusted description, never resolved automatically |
| memo | string | Column required; empty allowed; max 2000; untrusted description |

**Only incoming credits eligible for initial receipt registration belong in this file.** Debits, reversals, netted/negative amounts, transfers requiring classification and records with no reliable source identity are unsupported; do not invent identities or infer them from amount/name. No fuzzy fingerprints substitute for a missing external_transaction_id in version 1.0. Argon should supply suitable records separately from unsupported raw source rows.

Natural identity: `(organization_id, source_system, account_ref, external_transaction_id)`. File name, row number and file digest are **not** transaction identity. Exact semantic duplicates skip registration. Any change to amount, currency, payer, memo or timestamp under the same key conflicts. Timestamp strings representing the same UTC instant compare equal. Bank originals cannot be edited/deleted through the API or ordinary DB UPDATE/DELETE/TRUNCATE.

Each newly accepted bank row creates exactly one receipt in the **same transaction**, for the same company, amount and INR currency. Initial `unapplied_amount_paise = amount_paise`, status `UNAPPLIED`, version 1. The receipt has no assigned customer. No separate receipts CSV/creation API exists, and no bank GL recognition occurs. `/payments` is a read-only alias for `/receipts`, not a payment initiation API.

## Import ordering

1. Apply migrations and configure/provision the organization. This is company configuration, not dataset seeding.
2. Import customers.
3. Import payer aliases (optional) and invoices referencing those customers.
4. Import bank transactions; receipts are automatic. Bank imports do not depend on customer import or resolve customer identity.

Foreign references in CSV use the defined external customer key, not internal IDs. The importer resolves them only within the configured company. A reference that exists only in another company returns the same `UNKNOWN_CUSTOMER` result as an unknown reference. No automatic cross-file orchestration or partial acceptance; split files according to limits and retry each with its own key.

## Persisted schema

These are the **required ingestion tables** at import version 1.0. PostgreSQL also has `alembic_version(version_num varchar(32))`. The additive matching tables below are application-managed metadata, not Argon inputs. Argon supplies CSV, not internal-table dumps.

All application tables have: `id UUID PRIMARY KEY` (server-generated UUID4), `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `version INTEGER NOT NULL DEFAULT 1`. All except `organizations` also have `organization_id UUID NOT NULL REFERENCES organizations(id)`. Customer references and new financial/source/audit tables have a unique `(organization_id,id)` key to support composite FKs. New table versions must be > 0. The organization/customer legacy version columns are unchanged. Monetary columns are signed BIGINT, with entity-level CHECK constraints rejecting unsupported signs. Every additional field below is NOT NULL unless marked nullable. No cascading deletion is configured.

| Table | Additional columns (database types) | Keys and relationships |
|---|---|---|
| organizations | name VARCHAR(200) | Configured ID is the ownership root; no dataset upload |
| customers | external_reference VARCHAR(100), name VARCHAR(200) | UNIQUE(company, external_reference); creation source via audit event |
| source_imports | idempotency_key UUID, contract_version VARCHAR(20), kind VARCHAR(32), source_name VARCHAR(128), content_sha256 VARCHAR(64), raw_bytes BYTEA, actor_id VARCHAR(100), status VARCHAR(20), row_count INTEGER, result JSONB | UNIQUE(company, idempotency_key); raw bytes ≤2 MiB; row_count 0–10000; status PROCESSING/ACCEPTED/REJECTED; PROCESSING is only internal to the ingestion transaction, never a successful response |
| payer_aliases | customer_id UUID, alias VARCHAR(200), normalized_alias VARCHAR(200), verified_by VARCHAR(100), verified_at TIMESTAMPTZ, evidence_reference VARCHAR(200), plus imported fields below | FK(company,customer_id) → customers(company,id); UNIQUE(company,normalized_alias) |
| invoices | customer_id UUID, invoice_number VARCHAR(100), issued_date DATE, due_date DATE, original_amount_paise BIGINT, initial_open_amount_paise BIGINT, open_amount_paise BIGINT, currency VARCHAR(3), status VARCHAR(20), plus imported fields | FK(company,customer_id) → customers; UNIQUE(company,invoice_number); balance/date/currency/status checks as above; index(company,customer_id,status) |
| bank_transactions | source_system VARCHAR(100), account_ref VARCHAR(100), external_transaction_id VARCHAR(100), occurred_at TIMESTAMPTZ, occurred_at_source VARCHAR(40), amount_paise BIGINT, currency VARCHAR(3), payer_name VARCHAR(200), memo VARCHAR(2000), plus imported fields | UNIQUE(company,source_system,account_ref,external_transaction_id); UNIQUE(company,id,amount_paise); positive/INR checks |
| receipts | bank_transaction_id UUID, amount_paise BIGINT, unapplied_amount_paise BIGINT, currency VARCHAR(3), status VARCHAR(20) | UNIQUE(company,bank_transaction_id); composite FK(company,bank_transaction_id,amount_paise) → bank_transactions(company,id,amount_paise); positive/INR/balance/state checks |
| audit_events | source_import_id UUID, actor_id VARCHAR(100), event_type VARCHAR(64), entity_id UUID nullable, source_row INTEGER nullable, details JSONB | FK(company,source_import_id) → source_imports; entity_id denotes the affected record when applicable; generated event ID/order preserve append-only history |

**Imported fields** on aliases, invoices and bank transactions: `source_import_id UUID`, `source_row INTEGER`, `payload_sha256 VARCHAR(64)`. Composite FK `(organization_id,source_import_id)` → source_imports; source_row is the original CSV logical record number. SHA-256 is lowercase hexadecimal. Semantic payload hashing uses compact sorted-key UTF-8 JSON (`ensure_ascii=False`), with validated dates as ISO strings, money as integers, and timestamp fields converted to UTC ISO strings. The file content digest hashes **exact uploaded bytes**, including BOM/newlines; these hashes serve different purposes.

Receipts link to source through their bank transaction. Customers link through `customers.created` audit records. Every bank/invoice/alias retains its original creation source; duplicate files get their own immutable run and duplicate events rather than replacing provenance. GET import results exclude raw_bytes; original bytes remain in the DB for provenance. No document/extraction tables, allocation/ledger tables or dataset tables are part of this contract.

Receipt DB checks allow future PARTIALLY_APPLIED/FULLY_APPLIED balances with consistent status, but milestone 01 creates only UNAPPLIED receipts and exposes no balance mutation. Invoice current balance cannot exceed initial opening balance. The receipt-to-bank composite FK enforces exact ownership/amount agreement; uniqueness prevents another receipt for the same bank row. All new tables are indexed by company.

## Atomicity, duplicates and errors

Imports acquire a transaction-scoped PostgreSQL advisory lock derived from company UUID. All business rows, automatic receipts, accepted ingestion metadata and creation/duplicate audit events commit together. A row validation/reference/identity/constraint failure rolls back **all** business changes from that file, including earlier valid rows, then commits only a REJECTED run and rejection audit event. There is no quarantine or partial acceptance mode. Row validation reports up to 100 errors; reference/identity failures report the first such failure after validation. Rejected row_count is 0 (no accepted rows); rejected raw bytes/digest remain available internally.

Natural-key duplicates with identical payloads are skipped within a file, across files/renames, and across concurrent imports. Different source identities with equal amounts are separate records; no matching inference. Conflicting payloads under an existing natural key return 409 and never overwrite. No writeoff, credit note, tax decision or journal is created.

The idempotency key is unique per company across all import kinds. Reuse with the same bytes, kind and version returns the stored outcome (including its original counts/IDs, or rejection), even if the filename changes. Reuse with changed content/kind/version returns 409 `IDEMPOTENCY_CONFLICT`; use a new key for a different request or corrected rejected file. Same bytes with a fresh key create a new ingestion run and audit duplicates without duplicating business rows. Exact-key replay records `import.replayed`; key misuse records `import.key_conflict` against the original run. It does not create a second source run.

Successful response (HTTP 200): `import_id` UUID string, `status=ACCEPTED`, `row_count`, `inserted`, `duplicates`, `receipts_created` integer counts and `record_ids` (one ID for each input row, including duplicates, in input order). Rejection response: HTTP 422 for validation/reference/version errors or 409 for identity/DB constraint conflict; `import_id`, `status=REJECTED`, `code`, `errors:[{row,field,message}]`, and zero inserted/duplicates/receipts_created. HTTP status is stored as `result.http_status` in import metadata; it is omitted from the top-level POST response. Key conflicts return code/message without creating a new run.

Error codes: `INVALID_ENCODING`, `INVALID_HEADER`, `INVALID_CSV`, `EMPTY_IMPORT`, `TOO_MANY_ROWS`, `INVALID_ROWS`, `UNKNOWN_CUSTOMER`, `UNSUPPORTED_CONTRACT`, `IDENTITY_CONFLICT`, `CONSTRAINT_CONFLICT`, `IDEMPOTENCY_CONFLICT`. Transport/schema errors (missing/invalid headers, unknown kind, missing company, invalid filename/media type, oversized body) are rejected before ingestion and do not create runs. Error messages omit raw bank fields and SQL diagnostics.

Source imports become immutable after ACCEPTED/REJECTED; originals, finalized run metadata and results cannot be changed by ordinary UPDATE/DELETE/TRUNCATE. Audit events are append-only with DB triggers; bank originals are likewise protected. Corrections require a future explicit compensating workflow, not CSV overwrites. The local PostgreSQL owner can administer/disable triggers; this is not tamper-proof storage against an administrator.

## Read APIs

Milestone 02 adds application-managed matching_evidence, matching_proposals and matching_requests with scoped FKs and immutable/idempotent snapshots. Their exact fields, verification payloads, bounds and stale-state rules are specified in [MATCHING.md](MATCHING.md). They are populated by matching APIs, never by Argon CSVs. The four import schemas and version 1.0 remain unchanged.

GET collection and GET `/{record_id}` for `/customers`, `/payer-aliases`, `/invoices`, `/bank-transactions`, `/receipts`, `/payments`, `/imports`, `/audit/events`. Collection responses are arrays, ordered by `(created_at,id)` with `limit` 1–100 (default 100) and `offset` ≥0 (default 0). Unknown or cross-company IDs return 404. Public read payloads are typed in `src/clearledger/views.py`, exclude source raw bytes, and include generated IDs/company/version/UTC created_at. No general SQL or file-execution endpoint exists. Financial registration remains limited to the four POST CSV imports; the matching extension adds only evidence/proposal metadata writes. Edits/deletes and standalone receipt creation are unavailable.

## Import commands (operator-supplied files only)

With migrations applied, company configured/provisioned and the API running:

```powershell
$key = [guid]::NewGuid().ToString()
curl.exe --fail-with-body -X POST http://127.0.0.1:8000/imports/customers `
  -H "Content-Type: text/csv" -H "X-Data-Contract-Version: 1.0" `
  -H "X-Actor-ID: local-operator" -H "Idempotency-Key: $key" `
  -H "X-Source-Filename: customers.csv" --data-binary "@<path-to-Argon-customers.csv>"
```

Use `/imports/payer-aliases`, `/imports/invoices` and `/imports/bank-transactions` with their corresponding CSVs and new request keys. Retain each original key for network retries. Inspect results with `GET /imports/<import_id>` and receipts with `GET /receipts`. No Argon data is bundled, fetched or imported automatically; external dataset compatibility is unverified until Argon supplies files conforming to this version.

## Milestone 09 authorization profile (CSV schemas unchanged)

[REVIEW_RECOVERY.md](REVIEW_RECOVERY.md) defines explicit whole-application role mode.
When REVIEW_DEMO_ENABLED or REVIEW_ACCESS_ENABLED is true, imports require authenticated
analyst/controller authority; auditor/missing/old-service-token requests cannot mutate.
The server records canonical actor/role provenance, instead of trusting X-Actor-ID.
Local demo roles do not authorize financial approval/posting. Both switches false retain
the original local-only compatibility profile, which is not production authentication.
No CSV column, paise type, format, identity constraint or version 1.0 semantics changed.
