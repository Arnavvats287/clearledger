# Persistent chronological application adapter — protocol 1

This is the application-side JSONL implementation of the independently supplied public
`PROTOCOL.md` and `runner_image/bridge.py`. Baseline: `a7cb6ec` (`cf6bf75` application
evaluation). The previous [single-snapshot measurements](POST_M09_APPLICATION_EVALUATION.md)
remain unchanged. This adapter does not implement Milestone 10, run the independent
scorer, or establish benchmark accuracy or full 420-receipt/426-stage coverage.

## Transport and stage identity

Run `python scripts/chronological_adapter.py` as the bridge's subprocess command.
One UTF-8 JSON object in/out per line; stdout contains protocol responses only. Explicit
stderr routing includes Alembic's captured output stream. No HTTP server transport is
added. The adapter consumes **only Base64 payload bytes**, never `CL_INPUT_ROOT` or a
benchmark directory. Only the four existing CSV paths and original-document directories
from the prior visible-export harness are accepted. Sidecars, inventories, schedules,
code, hidden-answer directories, unsafe paths, invalid hashes/Base64 and extra message
fields are rejected. Duplicate JSON keys/nonfinite constants are forbidden.

Binding preserves exact company, run UUID, request/snapshot UUIDs, nonce, complete
transaction natural key (including account_ref), and the **original as_of string**.
Manifest digests use sorted-key compact UTF-8 JSON, ensure_ascii=false, finite values.
Input is limited to 10,000 files, 2 MiB/file, 64 MiB decoded total and 96 MiB/wire line;
responses are limited to 8 MiB. The operator's hard 120-second deadline is unchanged.
The adapter budgets 105 seconds including setup, checks remaining time around API work,
caps individual HTTP operations at 20 seconds, and worker children at 30 seconds or the
remaining budget. PostgreSQL preflight has connection/statement/lock timeouts. The
trusted operator remains responsible for hard process/container termination at 120s;
Python checks are not a hard real-time scheduler. Oversized workloads fail, never gain
a larger timeout silently. No uncertain/failed work is automatically retried.

Operator clarification: both IDs are distinct for every stage, including tied cutoffs.
An exact completed-stage retry retains its original IDs and reuses the immutable saved
response without HTTP/database work. A fresh transport nonce may be rebound to that
same saved response; `files` is an optimization and does not change stage identity.
Conflicting ID reuse, reused nonces across stages, changed run/company, backward time,
or changed inputs at the same cutoff fail closed and poison the session. Old successful
responses may be replayed after later stages without rerunning an earlier snapshot.
The operator must supply all tied-cutoff stages before advancing: this application
cannot infer unseen stage completeness without the prohibited complete schedule.

## Database, API and worker lifecycle

Provision a **fresh empty database named `clearledger_chrono_<32 lowercase UUID hex>`**
outside the runner. DATABASE_URL must use `postgresql+psycopg`, name that database's
owner, and have no superuser/CREATEDB/CREATEROLE/replication/BYPASSRLS flags or role
memberships. URL query overrides are forbidden and session_user must equal current_user.
Nonempty/public-relation/function or extra-user-schema databases are rejected before
migration. A clean EOF is not permission to reuse a database in another run. There is
no resume of an incomplete run. The external trusted owner discards it and starts fresh.
The trusted provisioner must assign each owned database to exactly one adapter process;
this JSONL interface is single-session, not a distributed multi-run HTTP service.

`chronological_resources.owned_database` is **test bootstrap code only**. Its admin URL
never enters bridge/adapter/API/worker environments or the runner image. It generates
and later removes only its exact owned role/database. The runner does not create/drop
databases and rejects inherited TEST_DATABASE_URL/PGPASSWORD/PGPASSFILE/PGSERVICE and
external model credentials. Do not put production credentials in this environment.

On first request only: migrate the empty owned database to existing `0011_review`,
check drift, configure one company derived from run/company, provision one temporary
LOCAL_DEMO_ONLY AR_ANALYST, and start the actual FastAPI factory on loopback. The
same engine, Uvicorn process, HTTP session and database serve subsequent stages. The
reused real API client handles demo login; it grants **no finance authority**. No
verified finance adapter, controller, source keys or intent attestations are installed.
Financial reads must still return 503. All source mutations use real HTTP APIs.

`chronological_host.factory` and bounded worker children use Settings(_env_file=None).
The parent passes an allowlisted environment, disables both external-AI paths, sets
extraction=disabled/investigation=deterministic, empties Gemini key/model and source
registry, disables tracing and sets daily/shared provider budgets to zero. The frozen
factory/worker fail if these settings differ. Matching/investigation limits remain
application defaults. The normal PostgreSQL outbox drain runs in deadline-bounded
children; RETRY/DEAD/unfinished work aborts the evaluation run. No new queue, service,
clock framework, dependency, application schema or financial behavior is introduced.

## Cumulative ingestion and source chronology

All received manifests are validated, not only `files`. Original CSV v1.0 validation
is reused before any writes. Natural keys are customer external_reference, normalized
alias, invoice_number and the complete bank triple. Raw-field payload digests are
immutable: changed spelling/timestamps/amounts or removal of accepted rows is rejected
even where the underlying importer might accept semantic equivalence. Headers/row
ordering may change, provided row payloads remain identical. Header-only files are
retained but never sent to CSV APIs. Only new rows enter in customer → alias → invoice
→ bank order. The real bank API creates receipts atomically. Stable API idempotency
UUIDs derive from run plus operation/content/source metadata. No financial rows are
inserted directly by the adapter. Row/source mappings and exact cumulative input bytes
are retained privately alongside the actual delta imports for provenance.

Existing document paths/digests cannot change/disappear. New originals are uploaded
byte-for-byte with synthetic approval=false, checked through original/text/span APIs,
and extracted with allow_external=false. Application canonical-pages digests are
independently checked; valid/forged-span probes use **actual application text**. No
offline TXT digest, citation offset or trust label is substituted. Correlation receives
no verified UTR assertion, so candidates remain unlinked. New source-backed claims may
materialize through the normal worker; no shortfall-derived claims are manufactured.
The requested receipt's cases and new documents' cases are refreshed when stale,
queried for available native invoice evidence, and submitted to the normal deterministic
investigator only when actual persisted claims exist. Unsigned documents are not
converted to registered/signed evidence records without an authorized contract mapping.

Receipt/alias timestamps and India-calendar invoice issue dates cannot exceed the
request cutoff. Documents' availability is supplied by the trusted current projection;
their text cannot authenticate availability, sender or payment intent. Nothing reads
the hidden truth, future stage, complete schedule or benchmark generation code.

**Clock limitation:** ClearLedger has no approved replay clock. The adapter preserves
input-availability chronology and performs clock-independent matching against only
currently ingested records, including invoice/receipt source dates. It does not backdate
database creation, review/authentication/audit timestamps, age/expiry/legal checks or
workflow wall clocks. Responses explicitly mark historical_application_clock NOT
EVALUABLE. Future cutoffs are rejected. Consumers must not score unsupported historical
clock-dependent behavior as if a replay clock existed. No future-contaminated state is
re-executed with an earlier label: regressions fail and old responses are immutable.

## Outputs, safety and private provenance

Actual exact/advanced proposal outcomes, extraction route/status/hashes/spans, scoped
case versions, evidence/investigation counts, HTTP latency and finance-denial status are
returned in bounded api_observations. Raw responses, UUID/natural-key mappings, source
manifests, accepted natural-key hashes, request bindings and before/after fingerprints
are exclusively created in private stage files. SHA-addressed input objects preserve
the exact received bytes; existing objects are integrity-checked, not overwritten.
Each stage response cites its raw observation SHA. API errors preserve a minimal bound
prediction with ERROR, safe diagnostics and private raw observations; they do not
populate invented capability outputs. Malformed unbindable protocol input exits 2.
Managed source/observation/response artifacts are capped at 1 GiB and 10,000 stages;
originals/progress/API process logs additionally live in the restricted private state
boundary. Storage failure aborts without claiming a retained provenance digest.

Financial PASS requires two checks: previous source rows survived new imports unchanged,
and an independent SQL snapshot **after legitimate source ingestion** equals the state
after matching/document/case/evidence/investigation work. Ledger journals/lines, cash
allocations, noncash settlements and provider reservations must remain empty. PASS
excludes intentional append-only source imports; it is not evidence of posting authority
or historic GL correctness. Missing checks are NOT_EVALUABLE; failed invariants are FAIL.

With no verified payment intent, actual predictions abstain, return no incremental cash
allocations and financial_authority=false. Mathematical UNIQUE is never promoted to
supported intent. Missing receipt stages use minimal bound predictions and ABSTAIN.
Unsupported financial/journal/claim/citation capabilities are omitted. Source authenticity,
statutory tax, production identity, legal adjudication, paid Gemini accuracy and benchmark
answer accuracy remain unverified. There is no feedback loop from scorer answers.

Private output contains confidential input/response material: keep it outside Git and
model inputs, under trusted operator custody. The supplied bridge needs PYTHONUTF8=1
(or Python `-X utf8`) on Windows so its locale-dependent subprocess text pipes preserve
Unicode. The adapter itself explicitly configures strict UTF-8. No operator file is changed.

## Reproduction and verification

Set only the app-owner DATABASE_URL and a **new, absent** CL_ADAPTER_OUTPUT directory
for a live runner. Do not give it the admin test URL, local `.env`, dataset root, operator,
scorer or schedule. Set bridge CL_HARNESS_COMMAND_JSON to a JSON argv array, e.g.
`["<absolute python>","<absolute repository>/scripts/chronological_adapter.py"]` and
PYTHONUTF8=1. The trusted bridge alone reads its current CL_INPUT_ROOT projection.

Application-only Docker build uses an explicit allowlisted context, **never `docker
build .`**. It contains source, lock/config/migrations and eight required harness scripts;
no `.env`, tests, admin bootstrap, dataset, operator, scorer, schedule or local logs.
Runtime UID=10001, read-only root, dropped capabilities/no-new-privileges, bounded memory/
CPU/PIDs and an internal network are exercised by the verifier. Existing shared harness
utilities remain dependencies; the new privileged role/database bootstrap and verifier
are excluded from the image, and legacy helpers receive no administrator credentials.
Mount only a fresh private
writable state directory (or appropriately owned volume) plus `/tmp`; never privileged
inputs. The test PostgreSQL container has a separate loopback bootstrap network; the
adapter stays on the internal network with only its app-owner database credentials.

The native Windows verifier is a trusted-host functional test, not filesystem isolation
against compromised code running as the same Windows user. Use the restricted Docker
profile for independently operated runs; payload allowlisting and an app-owner database
role alone do not deny an arbitrary host process access to privileged directories.
Elapsed stage measurements begin after protocol decoding/validation and include actual
setup/API/worker wall time; they exclude bridge overhead. Per-call timings exclude login
and readiness. No CPU or RSS measurement is claimed from the configured resource caps.

```powershell
uv run --frozen python scripts/build_chronological_image.py
uv run --frozen python scripts/verify_chronological_bridge.py --bridge '<public bridge.py>'
uv run --frozen python scripts/verify_chronological_bridge.py --bridge '<public bridge.py>' --docker
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

The bridge verifier uses only minimal existing test rows: three stages (two tied, one
later), an unavailable then newly available second receipt, original JSON extraction,
delta-only imports and an identical replay. It preserves private provenance and cleans
only labelled resources/owned databases. It never runs the independent operator/scorer.
Actual measurements and final verification/checkpoint identifiers are recorded in STATUS.
Final local gate: **672 tests passed**, all prior 621 retained, plus **4 isolated restart
checks**; static/dependency/migration gates passed. Actual supplied bridge verified three
stages plus replay in both Windows and restricted Docker profiles; measured maximum
stage durations were **11.448s** and **14.238s** respectively. These are minimal integration
fixtures, not benchmark accuracy/coverage or a performance SLA.
Initial transport/connectivity diagnostic failures are retained privately and excluded
from passing results. The fixed 120s budget has not been proven for the unseen full study;
large input bursts may require the operator to version its protocol, not silent relaxation.
