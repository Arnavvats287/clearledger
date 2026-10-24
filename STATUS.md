# Build status

- Repo state: **Milestone 01 financial data engine implemented; dataset construction belongs exclusively to Argon.**
- Current milestone: **01 — implementation verified; stop before milestone 02**.
- Verified checks: **83 tests passed against Docker PostgreSQL 16.15; strict imports, duplicates/concurrency, tenant isolation, API integration, DB guards, migrations, schema drift, live health/ready, restart persistence, lint/format and dependencies passed.**
- External integrations: **None**.
- Open decisions: Exact email extraction model and tax rule references to be selected/verified in later phases. Use stub extractors for local tests.

## Completion log
| Milestone | Status | Verified commands/results | Notes |
|---|---|---|---|
| 00 | Implemented; Docker verification passed | See verification logs below | No milestone 01 work started |
| 01 | Implemented; verified | 83 tests, migrations/restart, Ruff and dependency checks passed; details below | No dataset generated, fetched, curated or seeded |
| 02 | Not started | — | — |
| 03 | Not started | — | — |
| 04 | Not started | — | — |
| 05 | Not started | — | — |
| 06 | Not started | — | — |
| 07 | Not started | — | — |
| 08 | Not started | — | — |
| 09 | Not started | — | — |
| 10 | Not started | — | — |
| 11 | Not started | — | — |

## Milestone 00 implementation — 2026-10-25

Files added:
- `pyproject.toml`, `uv.lock`, `.python-version`: Python 3.12, uv-managed locked dependencies, pytest/Hypothesis and Ruff configuration.
- `src/clearledger/{config,db,main,models,customers,money}.py` and package initializer: FastAPI app factory, PostgreSQL-only settings, bounded connection timeout/UTC sessions, scoped customer lookup, minimal organization/customer models, pure money utilities.
- `alembic.ini`, `infra/migrations/env.py`, `infra/migrations/script.py.mako`, `infra/migrations/versions/0001_foundation.py`: explicit reversible schema migrations; no automatic table creation at startup.
- `compose.yaml`, `.env.example`, `.gitignore`: loopback-only PostgreSQL 16.15 service, persistent volume and health check, local configuration placeholders, ignored credentials/data/caches.
- `tests/{conftest,test_money,test_api,test_postgres,test_smoke}.py`: unit/property tests, disposable PostgreSQL integration, CLI migrations and a live Uvicorn HTTP smoke test.
- Updated `README.md` with setup, migration, server, test and shutdown commands, test database safety, and limitations. Planning/specification/prompt files were preserved.

Observed behavior and decisions:
- `GET /health` reports process liveness without accessing the database; `GET /ready` executes `SELECT 1` and returns a generic HTTP 503 on DB failure. Readiness deliberately does not imply schema currency.
- Only organization/customer persistence exists: UUIDs, UTC timestamps, aggregate versions, a customer organization FK, an organization index and organization-scoped unique external reference. Customer reads require both organization and customer IDs. No public business mutation endpoints or authentication yet.
- Money utilities accept signed values/zero, plain decimal strings, finite Decimal/string rates and percent units; they reject floats and boolean paise. Ties round away from zero with ROUND_HALF_UP. Integer persistence has no monetary columns yet because financial entities belong to later milestones.
- Used the simpler `src/clearledger` package layout permitted by the architecture document. No seeding/imports, speculative future tables, agents, frontend, workers, matching, policy/tax rules or posting were added.
- PostgreSQL integration tests use CREATEDB only to create/drop a generated `clearledger_test_<uuid>` database. They never downgrade the caller's database. A missing TEST_DATABASE_URL skips integration checks unless `--require-postgres` is specified, in which case it fails.

### Verification commands and actual results

Host: Windows PowerShell; bundled Python **3.12.14**. `uv` was unavailable initially, so uv **0.13.5** was bootstrapped into `.venv`. The ordinary venv bootstrap failed because this bundled Python could not run ensurepip; the bundled pip's `--python .venv` option installed uv successfully.

```powershell
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m venv .venv
# Failed during ensurepip; environment directory was created.
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pip --python .venv install uv
# Successfully installed uv-0.13.5 (network-enabled execution required).
$env:UV_CACHE_DIR="$PWD/.uv-cache"
./.venv/Scripts/uv.exe sync --python .venv/Scripts/python.exe
# Resolved, built and installed 37 packages; created uv.lock.
```

An initial `ruff check . --fix` scanned the workspace uv cache because this directory is not a Git repository; it modified cached dependencies and caused an import failure. Corrected by explicitly excluding cache/runtime directories and reinstalling all locked packages from a fresh cache:

```powershell
$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"
./.venv/Scripts/uv.exe sync --frozen --reinstall --python .venv/Scripts/python.exe
# Reinstalled 37 packages successfully; subsequent test results use the repaired environment.
```

Docker, psql and uv were not on PATH; Docker Desktop/PostgreSQL were not installed, and WSL reported not installed. To verify real PostgreSQL without installing a system service, downloaded the portable PostgreSQL **16.15** Windows archive from EDB into ignored `.local-runtime/`, extracted it, generated a temporary random password file and ran:

```powershell
./.local-runtime/pgsql/bin/initdb.exe -D .local-runtime/pgdata -U clearledger_test -A scram-sha-256 --pwfile=.local-runtime/pg-password --encoding=UTF8 --locale=C
./.local-runtime/pgsql/bin/pg_ctl.exe -D .local-runtime/pgdata -l .local-runtime/postgres.log -o '-h 127.0.0.1 -p 55432' -w start
# Initialized successfully; server started on loopback port 55432.
$testPassword = Get-Content -Raw .local-runtime/pg-password
$env:TEST_DATABASE_URL="postgresql+psycopg://clearledger_test:${testPassword}@127.0.0.1:55432/postgres"
./.venv/Scripts/python.exe -m pytest -q --require-postgres -s
```

Final observed output:
```text
No new upgrade operations detected.
No new upgrade operations detected.
alembic upgrade head: exit 0
alembic current: 0001_foundation (head)
alembic check: No new upgrade operations detected.
live HTTP: /health 200 {"status":"ok"}; /ready 200 {"status":"ready"}
41 passed, 1 warning in 6.91s
```

The tests execute Alembic upgrade → downgrade base → upgrade head on their disposable database, check table sets and metadata drift, enforce foreign keys/uniqueness and tenant scoping, exercise actual PostgreSQL rejection with readiness 503/liveness 200, and spawn the documented Alembic/Uvicorn commands. The Uvicorn subprocess is stopped in teardown and the disposable database dropped. Earlier verification found an invalid test attempt to disable connections from the current database; replaced that with a connection to a uniquely named nonexistent database and reran successfully.

```powershell
./.venv/Scripts/ruff.exe check .
# All checks passed!
./.venv/Scripts/ruff.exe format --check .
# 37 files already formatted
$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"
./.venv/Scripts/uv.exe sync --frozen --offline
# Checked 37 packages in 4ms
./.venv/Scripts/uv.exe lock --check --offline
# Resolved 37 packages in 1ms
```

### Limitations and next blocked items

- At initial verification, Docker was absent and Compose was unverified. This limitation is resolved by the Docker follow-up below; the portable PostgreSQL verification remains historical evidence.
- No type checker is configured; no typecheck success is claimed. Ruff and tests passed.
- One upstream Starlette TestClient deprecation warning recommends HTTPX2; no test failures. HTTPX remains a locked development dependency.
- Sandboxed test runs hung in Python's Windows asyncio socket-pair initialization. Those processes were stopped; network-enabled test execution completed successfully. Initial dependency downloads also required network-enabled execution after DNS failure in the sandbox.
- The portable PostgreSQL runtime, cluster/password/logs/archive, venv and caches remain local and ignored; no system service or external integration was installed. Cleanup query `SELECT count(*) FROM pg_database WHERE datname LIKE 'clearledger_test_%'` returned **0**. `./.local-runtime/pgsql/bin/pg_ctl.exe -D .local-runtime/pgdata -m fast -w stop` reported **server stopped**.
- This directory has no `.git`, so Git status/diff could not be obtained; no commit/push was attempted.
- Milestone 01 remains **not started**, awaiting a separate explicit task. Do not infer finance/import/authentication readiness from milestone 00.

## Docker development verification — 2026-10-25

Scope: configure and verify the existing milestone 00 environment only. No product code, schema, tests, dependency versions or Compose services changed. The previous portable PostgreSQL installation, cluster and databases were not started, stopped, modified or removed during this follow-up.

Environment/configuration:
- Verified Docker Desktop **4.96.3**, Docker client/server **29.9.2**, Compose **v5.6.1**, context `desktop-linux` (Linux engine).
- Initial inspection found no Docker containers/volumes and no listeners on host ports 5432, 5433 or 55432. Used **127.0.0.1:5432 → container 5432**; no existing process was terminated. If 5432 is occupied in another environment, use POSTGRES_PORT=5433 and update both Windows URLs.
- Created `.env` exclusively (did not overwrite an existing file), using a random 48-character hexadecimal development password. Both Windows database URLs use `postgresql+psycopg://clearledger:<redacted>@127.0.0.1:5432/clearledger`. `.gitignore` already covers `.env`; `.env.example` retains placeholders only. No credentials are recorded here.
- Kept `compose.yaml` unchanged: pinned `postgres:16.15-bookworm`, `pg_isready` health check, IPv4 loopback binding and named volume `clearledger_postgres_data` at `/var/lib/postgresql/data`. The current Compose file runs only the database; the backend runs on Windows.
- An API on the same Compose network must use `db:5432`, independent of the Windows host mapping. Authenticated service-hostname connectivity was verified from inside the container.

Files changed: `.env` (local/ignored), `.env.example`, `README.md`, `STATUS.md`; added `scripts/verify_docker.py`. The script compares host/container cluster identities before touching a database, creates a uniquely named disposable database, runs CLI migrations, checks committed data across a normal restart of this project's container, and removes only its generated database in teardown. No production/portable data or development tables are downgraded.

### Actual commands/results

Initial sandboxed Docker commands were denied access to the Docker named pipe. Repeated engine/container/network verification with approved local engine access; no Docker installation or settings changes were needed.

```powershell
docker version
docker compose version
docker context show
docker compose ls
docker ps -a --format '{{.Names}} {{.Image}} {{.Ports}}'
docker volume ls
Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -in 5432,5433,55432 }
# Engine/client 29.9.2, Desktop 4.96.3, Compose v5.6.1, desktop-linux.
# No initial containers/volumes or PostgreSQL port listeners.
docker compose config --quiet
# Exit 0; resolved configuration was not printed because it contains credentials.
docker compose up -d --wait --wait-timeout 120 db
# Pulled postgres:16.15-bookworm; created project network, volume and container; Healthy.
docker compose ps
docker compose port db 5432
# clearledger-db-1 healthy; 127.0.0.1:5432.
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
./.venv/Scripts/python.exe -m alembic check
# New development DB upgraded; 0001_foundation (head); No new upgrade operations detected.
./.venv/Scripts/python.exe scripts/verify_docker.py
```

Persistence script output (also rerun after the final IPv4 configuration):
```text
Windows DATABASE_URL verified against Docker PostgreSQL cluster identity
alembic upgrade head: exit 0
alembic downgrade base: exit 0
alembic upgrade head: exit 0
alembic current: 0001_foundation (head)
alembic check: No new upgrade operations detected.
Normal container restart: healthy; committed row persisted; same container
Generated disposable verification database removed
```

The CLI downgrade runs only against `clearledger_test_<uuid>`; the development database receives only upgrade/check. The script commits an organization probe in its disposable database before `docker compose restart db`, waits with `docker compose up -d --wait --wait-timeout 45 db`, then verifies the same row and container after restart. The persistent volume is retained. No volume removal or portable PostgreSQL commands were used.

The initial full Docker suite returned **40 passed, 1 failed**: its live readiness request timed out at one second when `.env` used `localhost`. Measured actual `SELECT 1` connection times with identical credentials: **localhost 3.025s; 127.0.0.1 0.036s**. Changed both local URLs and the example to explicit IPv4 loopback, matching the Compose binding and avoiding IPv6 fallback. Did not change application behavior, tests or timeouts.

```powershell
$env:TEST_DATABASE_URL = & ./.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"
./.venv/Scripts/uv.exe run --frozen pytest -q --require-postgres -s
```

Final suite output:
```text
No new upgrade operations detected.
No new upgrade operations detected.
alembic upgrade head: exit 0
alembic current: 0001_foundation (head)
alembic check: No new upgrade operations detected.
live HTTP: /health 200 {"status":"ok"}; /ready 200 {"status":"ready"}
41 passed, 1 warning in 6.65s
```

A separate temporary Uvicorn process ran `python -m uvicorn clearledger.main:create_app --factory --host 127.0.0.1 --port <free-port>` using the **configured development database** from `.env`. `Invoke-RestMethod` returned `/health` HTTP 200 `ok` and `/ready` HTTP 200 `ready`. Only that newly launched API process was stopped afterward; logs are local/ignored under `local-data/`. The test suite also exercises live HTTP with disposable databases.

```powershell
docker compose exec -T db pg_isready -U clearledger -d clearledger
# accepting connections
docker inspect --format '{{range .Mounts}}{{.Type}} {{.Name}} {{.Destination}}{{end}}' clearledger-db-1
# volume clearledger_postgres_data /var/lib/postgresql/data
docker compose exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h db -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT current_database()"'
# clearledger (authenticated db:5432 service-name connection)
docker compose exec -T db psql -U clearledger -d clearledger -Atc "SELECT version(); SELECT version_num FROM alembic_version; SELECT count(*) FROM pg_database WHERE datname LIKE 'clearledger_test_%';"
# PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2); 0001_foundation; 0 disposable databases.
./.venv/Scripts/ruff.exe check .
# All checks passed!
./.venv/Scripts/ruff.exe format --check .
# 38 files already formatted
$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"
./.venv/Scripts/uv.exe sync --frozen --offline
# Checked 37 packages
./.venv/Scripts/uv.exe lock --check --offline
# Resolved 37 packages
./.venv/Scripts/uv.exe pip check
# Checked 38 packages; All installed packages are compatible
```

Remaining limitations/next steps:
- No Docker verification blocker remains. The database is intentionally left running and healthy for Windows development; the temporary API is stopped. Start the backend with the README command when needed.
- One existing upstream Starlette TestClient/HTTPX deprecation warning remains. No static type checker or API Docker service is configured or claimed verified.
- Git ignore rules cover `.env`, but this workspace still has no `.git`; `git check-ignore --no-index .env` reported `not a git repository`. No Git repository was initialized, and no commit/push was attempted.
- Milestone 01 remains **not started**. Stop here; further product work requires a separate task.

## Milestone 01 — financial data engine (2026-10-25)

This section supersedes historical milestone 00 statements that milestone 01 had not started. Scope was explicitly approved in this task; milestone 02 remains not started.

### Git checkpoints and responsibility change

- No repository/history existed at task start. Initialized `main`, preserved all foundation files, extended ignore rules, inspected staged paths/content and confirmed the actual `.env` password was absent. Git initially had no identity; requested it and configured only the repository-local identity supplied by the user. Sandbox denied `.git` writes; retried with approved access. No remote push, destructive reset or branch overwrite occurred.
- Reran milestone 00 before implementation: **41 passed, 1 upstream warning in 7.08s**, Ruff lint passed and 38 files formatted. Created baseline **`a545b428996f33816c0aebc60e6841dd89a72554`**, message `chore: establish verified milestone 00 foundation`; then created **`feat/milestone-01-data-engine`**.
- `AGENTS.md` now requires verified Git checkpoints, intended-file staging/review, secret/data exclusions, preserved history, no automatic pushes and recording hashes/results. Baseline already includes these permanent checkpoint rules.
- Updated milestone 01 prompt, PLANS, architecture/evaluation docs and conflicting later prompts (06/10/11) to assign all demonstration/evaluation research/construction to Argon. Removed generator and seed deliverables. Only inline, isolated application-test inputs were added; no dataset was generated, downloaded, researched, curated, seeded or modified.
- Existing `fixtures/demo-case.json` remains byte-for-byte unchanged: SHA-256 **`4A3C91AF85AEFEAD5EFF0D1CDB28FBEDE190E995445E2F98AF54568EFB31C6DA`** before and after. No Argon files were present or imported. Existing portable PostgreSQL was not touched.

### Changed files and behavior

- `src/clearledger/models.py`, `infra/migrations/versions/0002_data_engine_financial_data_engine.py`: additive company-scoped customer key and new payer_aliases, invoices, bank_transactions, receipts, source_imports and audit_events. UUIDs, signed BIGINT paise, INR checks, opening/current balance constraints, company-aware composite FKs, unique source identity and receipt-bank amount agreement. DB triggers reject ordinary edits/deletes/truncation of bank originals, audit events and finalized source imports.
- `src/clearledger/data_contract.py`, `imports.py`: contract 1.0 CSV schemas, bounded UTF-8 parsing, strict money/calendar/timezone checks, useful row/field errors, immutable original bytes and SHA-256, semantic replay checks, per-company advisory locking and all-or-nothing transactions. A failed import saves only rejection provenance/audit; valid earlier business rows are rolled back. Every newly registered incoming bank transaction creates one fully unapplied receipt, with no customer resolution or GL entry.
- `src/clearledger/api.py`, `views.py`, `main.py`, `config.py`: typed tenant-scoped collection/detail reads for customers, aliases, invoices, bank transactions, receipts/payments, import outcomes and audit; four raw-CSV POST imports. Scope comes only from configured ORGANIZATION_ID. Company selection is never taken from CSV or caller headers. GET metadata neither returns nor loads raw source bytes.
- `src/clearledger/cli.py`: explicit idempotent company UUID/name provisioning only, with no financial records or dataset generation. Actual development company configuration was left for the operator; no fictional company was seeded.
- `docs/DATA_CONTRACT.md`: complete versioned input/persistence contract, keys/relationships, required columns, type/size limits, dates/timezones, paise, import ordering, atomicity, duplicate/conflict semantics, API transport/results, provenance and supported scope. README documents exact setup/provision/import commands.
- `.env.example`, `.gitignore`: company configuration guidance; stronger dataset/credential/database/generated-file exclusions. `.env`, venv/caches/local DB/runtime/data, CSV/XLS/XLSX/PDF files and credential paths are ignored; no secrets were added to examples. Dependencies/lockfile are unchanged.
- `tests/test_imports.py`, `tests/test_postgres.py`: added focused parser/API/integration/concurrency/DB guard tests; current-schema migration table expectations and committed upgrade/downgrade stages.

### Design choices and contract summary

- Contract **1.0**, raw UTF-8 CSV, maximum **2 MiB / 10,000 rows**, exact header set; invalid rows reject the entire file. No quarantine/partial acceptance or silent normalization of padded values. Money is integer paise in the signed BIGINT range, positive for invoice originals/bank/receipts and nonnegative for invoice opening balances; no decimal/exponent/sign/float conversion during import. Timestamp inputs require explicit timezone and normalize to UTC while retaining source text/bytes.
- Required CSVs/headers are documented exactly in DATA_CONTRACT: customers (`external_reference,name`); optional payer aliases (`customer_reference,alias,verified_by,verified_at,evidence_reference`); invoices (`customer_reference,invoice_number,issued_date,due_date,original_amount_paise,open_amount_paise,currency`); bank transactions (`source_system,account_ref,external_transaction_id,occurred_at,amount_paise,currency,payer_name,memo`). Receipts are derived, never independently imported.
- The single-company root must be explicitly provisioned after setting ORGANIZATION_ID; unconfigured business endpoints return 503. This avoids automatic seeding. Source files cannot choose tenants or internal IDs. X-Actor-ID and alias verification metadata are locally asserted provenance, not authentication or accounting approval; auth/permissions are still a later concern and no restricted financial adjustment endpoints exist.
- Required external transaction identity is `(company,source_system,account_ref,external_transaction_id)`. No invented fallback identities, fuzzy matching, tax decisions or bank GL recognition. Same-key exact request replay returns the original stored result; fresh request keys report natural-key duplicates; changed content under a reused request key or natural identity conflicts without overwrite. Concurrent imports are serialized per company, with independent DB uniqueness/FK/check protections.
- Originals and audit are preserved in PostgreSQL. Customers retain creation provenance via the source-linked audit event, including legacy customer compatibility; aliases/invoices/bank rows also have direct source run/row/hash fields. Existing invoice opening balances are baseline state, not reconstructed historical allocations.

### Actual verification commands and results

Run from the repository root; network/engine-enabled execution was needed for Windows local sockets and Docker access. All destructive migrations used generated disposable test databases. The development database received only upgrade/check, with no reset/downgrade or data deletion.

```powershell
$env:TEST_DATABASE_URL = & ./.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"
./.venv/Scripts/uv.exe run --frozen pytest -q --require-postgres -s
```

Final observed output:
```text
No new upgrade operations detected.
No new upgrade operations detected.
alembic upgrade head: exit 0
alembic current: 0002_data_engine (head)
alembic check: No new upgrade operations detected.
live HTTP: /health 200 {"status":"ok"}; /ready 200 {"status":"ready"}
83 passed, 1 warning in 12.46s
```

Earlier expanded runs passed 77 tests and then 83 tests. Removed one test-only empty-regex assertion warning; final run has only the pre-existing upstream Starlette/HTTPX deprecation warning. The tests cover valid imports, exact balances/provenance, malformed structure/encoding/header/body limits, float/bool/overflow money rejection, strict dates/timezones and invalid currencies, atomic invalid/conflicting files, duplicate renamed/equivalent-timestamp rows, same/different concurrent idempotency keys, rejected-request replays, alias conflicts, read isolation, cross-company FKs, receipt uniqueness/amount guards, immutable sources/audit (including TRUNCATE), pagination, missing scope, explicit configuration-only provisioning, migration roundtrips/drift and live HTTP health/readiness.

```powershell
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
./.venv/Scripts/python.exe -m alembic check
# Development DB: 0002_data_engine (head); No new upgrade operations detected.
./.venv/Scripts/python.exe scripts/verify_docker.py
# Windows URL matched Docker cluster identity.
# Disposable DB: upgrade head → downgrade base → upgrade head, all exit 0.
# 0002_data_engine (head); No new upgrade operations detected.
# Normal container restart: healthy; committed row persisted; same container.
# Generated disposable verification database removed.
docker compose ps
# clearledger-db-1: healthy; 127.0.0.1:5432->5432/tcp
docker compose exec -T db psql -U clearledger -d clearledger -Atc "SELECT version_num FROM alembic_version; SELECT count(*) FROM pg_database WHERE datname LIKE 'clearledger_test_%';"
# 0002_data_engine; 0 disposable databases remain.
./.venv/Scripts/ruff.exe check .
# All checks passed!
./.venv/Scripts/ruff.exe format --check .
# 46 files already formatted
./.venv/Scripts/uv.exe sync --frozen --offline
# Checked 37 packages in 6ms
./.venv/Scripts/uv.exe lock --check --offline
# Resolved 37 packages in 1ms
./.venv/Scripts/uv.exe pip check
# Checked 38 packages; All installed packages are compatible
git diff --check
# Passed for milestone changes.
git check-ignore .env .venv .uv-cache-clean .local-runtime local-data datasets/example.csv argon-data/example.csv credentials/example.json secrets/example.json
# Every listed path is ignored.
```

Import commands: see the exact raw-CSV curl example in `docs/DATA_CONTRACT.md` and README. Every POST needs `Content-Type: text/csv`, `X-Data-Contract-Version: 1.0`, `X-Actor-ID`, `Idempotency-Key: <UUID>` and `X-Source-Filename: <basename.csv>`. Import customers first, aliases/invoices next, bank credits independently/last; receipts are automatic. No Argon dataset was used for smoke/tests.

### Limits and next steps

- No required check is failing. The Docker development schema is upgraded and the container remains healthy; company setup/imports await operator-supplied ORGANIZATION_ID/name and Argon's compatible files. Those external dataset imports are **unverified**, not generated or fabricated here.
- One existing upstream TestClient deprecation warning remains. No type checker is configured; no typecheck result is claimed. API authentication/roles, edits/corrections, matching, journal posting, agents, workers and frontend remain unimplemented as scoped.
- The database owner can administer/disable triggers; immutability guards protect ordinary application operations, not a hostile DB administrator. Per-company import serialization is a deliberate conservative local-development choice.
- Completion checkpoint hash will be recorded immediately after the reviewed verified feature commit in a separate documentation-only checkpoint, avoiding a self-referential commit hash.
- STOP after milestone 01. Do not start milestone 02 automatically.
