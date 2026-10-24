# ClearLedger

A **local, single-company, INR-only AR cash application and deduction investigation system**. Milestone 01 adds a tenant-scoped financial data engine and strict CSV imports to the verified backend/database foundation. Matching and subsequent financial workflows remain for later milestones.

## Milestone 00: local setup

Requirements: Python **3.12**, [uv](https://docs.astral.sh/uv/), and running Docker Desktop with Compose. ClearLedger development uses PostgreSQL in Docker; the backend runs on Windows. Commands below run from this directory in PowerShell; `uv` must be on PATH. In this workspace, uv is also available as `./.venv/Scripts/uv.exe`.

```powershell
uv sync --frozen
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env: choose a local password and update both database URLs to match.
# Check host port availability before starting:
Get-NetTCPConnection -State Listen -LocalPort 5432 -ErrorAction SilentlyContinue
# If occupied, set POSTGRES_PORT=5433 and use 5433 in both Windows URLs.
# Keep the existing process running; do not replace an existing database volume.
docker version
docker compose version
docker compose config --quiet
docker compose up -d --wait db
uv run --frozen alembic upgrade head
uv run --frozen alembic current
uv run --frozen alembic check
uv run --frozen uvicorn clearledger.main:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, `Invoke-RestMethod http://127.0.0.1:8000/health` returns `status: ok`; `/ready` returns `status: ready` after a successful `SELECT 1`, or HTTP 503 with a generic error when the database is unavailable. `/health` never connects to the database. `/docs` exposes the API schema. Readiness confirms connectivity, not migration currency; run the migration checks separately. Startup does not create tables or seed data.

`DATABASE_URL` uses `postgresql+psycopg://...`; SQLite is deliberately unsupported. Settings read `.env`, with environment variables taking precedence. Database sessions use UTC. The milestone 01 tables and constraints are specified in `docs/DATA_CONTRACT.md`. Customers carry an organization foreign key and organization-scoped external reference. Authentication is not implemented; use loopback and local test data only.

The configured development endpoint is **127.0.0.1:5432** (IPv4 localhost); 5432 was free during Docker setup. The generated development password lives only in `.env`, covered by `.gitignore`. `.env.example` contains placeholders. Both `DATABASE_URL` and `TEST_DATABASE_URL` must use the selected **host** port. Prefer `127.0.0.1` explicitly: on this Windows host, `localhost` took about three seconds to connect due to IPv6 fallback, exceeding the live readiness smoke test's timeout.

For an API running **inside the same Compose network**, set its `DATABASE_URL` to `postgresql+psycopg://<user>:<password>@db:5432/<database>`. Use the service hostname `db` and the internal port 5432 even when Windows maps port 5433. The existing Compose file runs only the database; no API container is configured. Authenticated `db:5432` connectivity was verified from within the Compose network.

The named volume is `clearledger_postgres_data`, mounted at `/var/lib/postgresql/data`. Normal `docker compose restart db` and `docker compose stop db` retain data. Do not remove this volume. PostgreSQL initializes credentials from `.env` only when the volume is empty; changing `.env` does not rotate an existing database password. The previous portable PostgreSQL installation and its databases are preserved separately.

## Tests and checks

```powershell
uv run --frozen ruff check .
uv run --frozen ruff format --check .
# Integration tests read the environment explicitly, not .env.
# Load the configured local Docker URL without printing its credentials.
$env:TEST_DATABASE_URL = uv run --frozen python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
uv run --frozen pytest -q --require-postgres
uv lock --check
uv pip check
```

The Compose database role has the required local test privileges. Tests create a uniquely named `clearledger_test_<uuid>` database and drop only that generated database in teardown. They verify migration upgrade → downgrade → upgrade, metadata drift, foreign keys, uniqueness, tenant isolation, actual PostgreSQL readiness and failure, and the Alembic/Uvicorn CLI commands with live HTTP. Never use production credentials. An interrupted test may leave a disposable test database behind.

Without `TEST_DATABASE_URL`, `uv run --frozen pytest -q` runs unit/property tests and explicitly skips PostgreSQL checks. `--require-postgres` makes missing configuration a failure. No static type checker is configured. Money utilities use signed integer paise, finite Decimal rates, plain decimal input strings, and ROUND_HALF_UP; floats/bools are rejected. Rate `0.025` and percentage `2.5` both mean 2.5%, with one final paise rounding.

To rehearse rollback manually, point `DATABASE_URL` at a **disposable** database first, then run `uv run --frozen alembic downgrade base` and `uv run --frozen alembic upgrade head`. Downgrade removes the two foundation tables; do not run it on data you intend to retain. Use `docker compose stop` to stop local PostgreSQL while retaining its volume.

For a repeatable Docker migration/persistence check:

```powershell
uv run --frozen python scripts/verify_docker.py
```

This verifies that the Windows URL reaches the Compose container by comparing PostgreSQL cluster identities, creates a disposable database, runs the Alembic CLI upgrade → downgrade → upgrade plus schema checks, commits a synthetic probe row, and **restarts this project's database container**. It verifies the row survives and the container becomes healthy, then drops only its generated database. It leaves the development database intact; run this when a development database restart is convenient. A stopped/interrupted verification may leave a generated test database behind.

## Known local limitations

Docker Desktop and Compose are now verified on the implementation machine, including normal restart persistence. The earlier portable [EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries) verification remains documented in `STATUS.md`. Some restricted Windows sandboxes block Docker's named pipe and the socket pair used by Python's event loop: Docker/test/server checks need local engine/network access. The current Starlette test client emits an upstream deprecation warning for HTTPX; tests still execute. No static type checker or API container is configured.

The environment is local only. No frontend, matching, agents, workers, tax decisions, authentication, financial posting, or external integrations are implemented. Dependency resolution is committed in `uv.lock`; `.env`, runtime caches, datasets and local financial data are ignored.

## Milestone 01: company configuration and imports

The complete versioned interface is [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md). **Argon owns all demonstration/evaluation dataset research and construction.** No dataset is bundled, generated, downloaded or seeded by this implementation. The old demo reference remains unchanged. Only small isolated application-test fixtures are used by tests.

Apply `uv run --frozen alembic upgrade head` to the development database. Destructive rollback tests belong only in disposable databases. Set `ORGANIZATION_ID=<your company UUID>` in your ignored `.env` (a new UUID may be obtained with `[guid]::NewGuid()`), then explicitly provision the company:

```powershell
uv run --frozen python -m clearledger.cli init-organization --name "<your company name>"
uv run --frozen uvicorn clearledger.main:create_app --factory --host 127.0.0.1 --port 8000
```

The provision command creates only company configuration and is idempotent for the same UUID/name. It does not create a financial dataset. Company scope comes from server settings; business endpoints return 503 until provisioned. Uploads cannot choose another tenant. `X-Actor-ID` records the locally asserted operator, not an authenticated account or approval.

Import **operator/Argon-supplied** UTF-8 CSVs in order: customers, optional payer aliases, invoices, then bank transactions (bank rows can also be imported independently of customers). Each file must match the exact column set in contract version **1.0**. Send raw CSV bytes, not multipart:

```powershell
$key = [guid]::NewGuid().ToString()
curl.exe --fail-with-body -X POST http://127.0.0.1:8000/imports/customers `
  -H "Content-Type: text/csv" -H "X-Data-Contract-Version: 1.0" `
  -H "X-Actor-ID: local-operator" -H "Idempotency-Key: $key" `
  -H "X-Source-Filename: customers.csv" --data-binary "@<path-to-Argon-customers.csv>"
```

Use `/imports/payer-aliases`, `/imports/invoices` and `/imports/bank-transactions` for their respective files, each with a new key. Reuse the original key for a network retry. A different payload under the same key is HTTP 409. Validated records are inserted atomically; any bad/conflicting row rejects the entire file with row/field errors. Exact records from renamed or replayed files are reported as duplicates. Each new positive incoming bank transaction creates one fully unapplied receipt; no allocation or GL journal is created.

Read collection/detail APIs: `/customers`, `/payer-aliases`, `/invoices`, `/bank-transactions`, `/receipts`, `/payments` (receipt alias), `/imports` and `/audit/events`; append `/<UUID>` for a detail. Collections accept `limit` 1–100 and `offset` ≥0. Import results include counts and record IDs. Originals/digests are retained internally; GET import metadata excludes raw bytes. Audit and bank-source records and finalized import runs are protected against ordinary DB edits/deletes. Examples:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/receipts
Invoke-RestMethod http://127.0.0.1:8000/imports/<import-id>
```

Run the full suite with `TEST_DATABASE_URL` loaded from `.env` using the test command above; do not substitute the development DB for a generated test DB in rollback commands. Tests create/drop only disposable databases and cover import validation, concurrency, tenant isolation, receipt uniqueness, DB guards and API behavior. `scripts/verify_docker.py` exercises the current schema's migration roundtrip and normal restart persistence using a disposable probe database; it restarts this project's database container. No Argon dataset was available or used in verification.

## Start here

1. Create/open a new repository named `clearledger` in Codex. Put every file in this starter pack at the repository root, preserving directories.
2. Read `PROJECT_SPEC.md`, `AGENTS.md`, `PLANS.md`, and `docs/DOMAIN_AND_ACCOUNTING.md`.
3. Submit the prompt in `prompts/00-foundation.md` to Codex. Tell Codex to implement **only** milestone 00 and stop.
4. Inspect its diff and the actual test output. Only if the milestone exit criteria pass, proceed to the next prompt.
5. For every subsequent milestone, give Codex the relevant prompt under `prompts/` and ask it to update `STATUS.md` with actual validation results.

Codex CLI users can open a terminal in this directory and run `codex`; the Codex app/IDE can open the same folder. Consult official Codex docs for current installation details: https://developers.openai.com/codex/

## Repo documents

- `AGENTS.md`: standing behavior, architecture, and safety instructions for Codex.
- `PROJECT_SPEC.md`: product requirements and user journeys.
- `PLANS.md`: implementation order and hard milestone gates.
- `STATUS.md`: what has actually been implemented, validated, and deferred.
- `docs/ARCHITECTURE.md`: components, event flow, and Director–Investigator separation.
- `docs/DOMAIN_AND_ACCOUNTING.md`: money, transactions, journal rules, source of truth.
- `docs/SECURITY.md`: trust boundaries, tool policy, permissions and attack cases.
- `docs/API_AND_STATES.md`: proposed interfaces, state machines, events and invariants.
- `docs/EVALUATION.md`: deterministic and AI evaluations, ablations, success metrics.
- `docs/TAX_SCOPE.md`: conservative tax rules, explicit unsupported cases.
- `prompts/`: one implementable task at a time.
- `fixtures/demo-case.json`: illustrative case with expected accounting outcomes.

## Product boundaries

Local development system, anonymized/synthetic data, one company, INR, no real bank or ERP access, no auto-sent correspondence, no production tax compliance claims, and **no live financial posting**. The posting simulator must preserve double entry and provide an audit trail.

## Operating rule

Before each milestone: read specs; make a limited plan. During: test driven implementation and targeted integration checks. After: publish changed files, run commands and observed outputs, unresolved risks, and update `STATUS.md`. **Do not silently continue to the next milestone.**
