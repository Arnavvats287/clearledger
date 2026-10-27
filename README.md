# ClearLedger

**Evidence-driven accounts-receivable reconciliation and deduction investigation
for an Indian B2B distributor.** An INR-only workstation that connects receipts,
invoices and source documents, then produces traceable proposals for human review.

This portfolio proves a complete **ingestion → reconciliation candidate → deduction
evidence → LangGraph investigation → actionable review** workflow. It does not claim
production readiness, autonomous settlement or general live-LLM accuracy.

## Open the evidence-review workstation

![ClearLedger case folio: supported evidence, human review and canonical source](docs/screenshots/supported-evidence-investigation.png)

Financial story first: invoice ₹50,000 − receipt ₹47,000 = ₹3,000 short payment.
Real FastAPI/PostgreSQL cases, exact source spans, an on-demand LangGraph record,
controller correlation decisions and immutable history. Open AR, unapplied cash and
asserted deductions stay visibly separate. No financial approval or posting is faked.

After the Windows database setup below, in two terminals from the repository root:

```powershell
# Terminal1: fresh disposable API + existing outbox/graph
uv sync --frozen
npm.cmd --prefix frontend ci
uv run --frozen python scripts/serve_frontend_demo.py

# Terminal2: React workstation
npm.cmd --prefix frontend run dev
```

Open **http://127.0.0.1:5173**. Privately read the generated controller credentials
from ignored `local-data/frontend/access.json`; do not share or commit them.
Use INV-2026-1042 for missing evidence, INV-2026-1043 for support, INV-2026-1044
for conflict, and INV-2026-1045/1046
for deliberate correlation CONFIRM/REJECT. Inspect the ₹3,000 synthetic damage claim and exact
source span; draft an evidence request and read its audit history. Ctrl+C the API
host cleans only its generated disposable database. No development data is reset.

**These reproducible UI states use explicit offline fake-provider controls**, actual
source validation and the actual LangGraph executor. No Gemini calls populate the
screenshots. Previously verified real-model results are recorded separately in
[bounded live acceptance](docs/LIVE_ACCEPTANCE.md); small synthetic success is not
benchmark accuracy. Local reviewer sessions never confer production finance authority.

[Complete frontend setup, API boundaries and browser checks](FRONTEND.md) ·
[Exception queue](docs/screenshots/exception-queue.png) ·
[Missing evidence](docs/screenshots/missing-evidence-investigation.png) ·
[Conflicting evidence](docs/screenshots/conflict-evidence-investigation.png) ·
[Correlation review](docs/screenshots/correlation-decision.png)

## Run one complete accountant workflow

After the Windows setup below:

```powershell
uv run --frozen python scripts/portfolio_demo.py
```

The command uses actual FastAPI routes through **in-process TestClient**, real
PostgreSQL, the existing outbox and the production LangGraph executor. No API
responses are mocked. It creates and cleans disposable databases; it does not
populate or reset your development database. External AI is forced off.

**Observed output excerpt**, reproduced locally with five passing demo scenarios:

```text
PRIMARY WORKFLOW: one invoice / receipt / remittance / case / claim
Invoice=1101 paise; receipt=1000 paise
Candidate: UNRESOLVED -> UNIQUE cash=1000 remaining_AR=101
Source-backed claim=101 paise; receipt correlation=LINKED; verified citation records=1
Review: SUPPORTED / HUMAN_REVIEW / AWAITING_REVIEW
Action: review the 101-paise rebate against cited promotion; no adjustment approved
Actual AR=1101; cash unapplied=1000; verified settlement=0 (paise, unchanged)
```

Every stage uses the **same linked receipt, invoice, document, claim and case**:

| Stage | Explicit expected result checked by the demo |
|---|---|
| CSV ingestion | Invoice outstanding 1,101 paise; bank entry creates a 1,000-paise receipt |
| Conservative reconciliation | UNRESOLVED without verified intent; after explicit test attestation, one 1,000-paise candidate retains 101 paise AR |
| Source-backed deduction | Strict remittance extracts a 101-paise rebate assertion; verified test UTR links it to the same receipt/case |
| Evidence investigation | Test-signed promotion supports the 101-paise source predicate; real LangGraph retrieval/verifier produces a cited finding |
| Accountant handoff | SUPPORTED / HUMAN_REVIEW; case AWAITING_REVIEW; inspect cited promotion before making any adjustment |
| Financial safety | Invoice still 1,101 paise open; receipt still 1,000 paise unapplied; verified settlement 0 |

**Working:** one continuous workflow to human review, supported by explicit
assertions—not a sequence of unrelated screenshots. **Not demonstrated:** an
approved adjustment, settlement or posting. The 101-paise residual is a candidate's
unpaid AR, not an already-applied balance. `SUPPORTED` authenticates a source
predicate within the fixture, not the legitimacy or approval of a deduction.

All data are tiny application-owned synthetic code fixtures. Matching intent/UTR
attestations and publisher signatures are explicitly configured **test trust**;
no customer identity, payment intent or financial authority is inferred from text.

Supplementary actual-API controls demonstrate:

```text
Matching: NO_SUPPORTED_MATCH -> EXACT_MATCH (explicit synthetic test attestation)
Document: DETERMINISTIC SUCCEEDED claim_amount_paise=101
Investigation[supported]: SUPPORTED HUMAN_REVIEW citations=1 tools=3
Investigation[missing]: INSUFFICIENT_EVIDENCE REQUEST_EVIDENCE citations=0 tools=3
Investigation[conflict]: INSUFFICIENT_EVIDENCE REQUEST_EVIDENCE citations=2 tools=3
Human review REQUIRED; financial authority FALSE; financial non-mutation PASS (5 scenarios)
External AI DISABLED; no posting or approvals; no benchmark access
```

Missing/conflicting evidence produces a concrete request-evidence action rather than
a guessed allowance. These are deterministic typed recommendations; no fake output
is presented as live AI reasoning. The primary workflow is asserted in
[tests/test_portfolio_demo.py](tests/test_portfolio_demo.py); per-step evidence and
reproduction details are in [the demo walkthrough](docs/PORTFOLIO_DEMO.md).
Actual synthetic observations are saved under ignored `local-data/portfolio-demo/`.

## Architecture

```mermaid
flowchart LR
    Client["React/TypeScript workstation + API clients"] --> API["FastAPI tenant-scoped services"]
    API --> Financial["CSV imports + matching proposals"]
    API --> Documents["Immutable originals + deterministic extraction"]
    API --> Cases["Cases + durable PostgreSQL outbox"]
    Cases --> Graph["Deterministic Director / LangGraph"]
    Graph --> Tools["Seven scoped read-only evidence capabilities"]
    Tools --> Verify["Hash / span / ownership / chronology checks"]
    Financial --> PG[(PostgreSQL)]
    Documents --> PG
    Documents --> Store["Local content-addressed originals"]
    Verify --> PG
    Graph --> PG
    Documents -. "optional; disabled in demo" .-> Gemini["Optional isolated Gemini3.5 extraction / Investigator"]
```

Domain/services, repositories and APIs remain separate. Integer **paise** is used
throughout, with explicit Decimal boundaries. Proposals use tenant scope,
idempotency, optimistic versions and stale-state checks. Document originals and
audit histories are immutable; evidence failures abstain.

The Investigator has only allowlisted read-only tools; the Director is
deterministic. Source facts, contradictions and missing information remain distinct
from financial authority. The separate accounting simulator requires independent
authorization/maker-checker gates; local actor labels or bearer tokens cannot
satisfy production finance identity. The demo invokes no finance operation.

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL 16.15, SQLAlchemy 2, psycopg, Alembic |
| Investigation | LangGraph + PostgreSQL checkpoints/outbox; deterministic Director/verifier, optional bounded AI Investigator |
| Frontend | React + TypeScript + Vite, generated OpenAPI client, lossless integer paise, Playwright |
| Documents | pypdf, bounded parser processes, SHA-256 and canonical spans |
| Optional model | Official Google GenAI SDK; external calls disabled by default |
| Quality | pytest, Hypothesis, Ruff, scoped mypy checks, GitHub Actions configuration |
| Local runtime | Docker Compose PostgreSQL; backend runs on Windows |

No Redis, MCP server, vector database or live bank/ERP connection is
needed. See [architecture](docs/ARCHITECTURE.md) and [financial invariants](docs/DOMAIN_AND_ACCOUNTING.md).

## Windows setup

Requirements: Python **3.12**, `uv`, running Docker Desktop with Compose, PowerShell;
Node **22.12+** for the UI (tested Node24).
From the repository root:

```powershell
uv sync --frozen
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit ignored `.env`: choose local PostgreSQL credentials; align POSTGRES_USER,
POSTGRES_PASSWORD, POSTGRES_DB, DATABASE_URL and TEST_DATABASE_URL. URL-encode
password characters. TEST_DATABASE_URL needs a local role with CREATEDB; the
walkthrough never migrates or drops the database named in that URL.

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5432 -ErrorAction SilentlyContinue
docker compose config --quiet
docker compose up -d --wait db
uv run --frozen python scripts/portfolio_demo.py
```

If 5432 is occupied, set POSTGRES_PORT=5433 **before starting Compose** and use 5433
in both Windows URLs. Preserve the existing process/database.
Windows URLs use `postgresql+psycopg://<user>:<URL-encoded-password>@127.0.0.1:<host-port>/<database>`.
An API inside the Compose network would use `db:5432`; Compose currently starts
only PostgreSQL. Do not remove the named volume. Editing credentials in .env does
not rotate an already-initialized database password.

The demo privately loads the test URL and clears its child Gemini key. Missing
configuration fails explicitly instead of skipping PostgreSQL. Keep defaults:

```dotenv
EXTRACTION_PROVIDER=disabled
EXTERNAL_AI_ENABLED=false
INVESTIGATION_PROVIDER=deterministic
INVESTIGATION_EXTERNAL_ENABLED=false
```

To explore a separately running local API, configure ORGANIZATION_ID and a random
DOCUMENT_API_TOKEN of at least 32 characters in ignored .env, then:

```powershell
uv run --frozen alembic upgrade head
uv run --frozen alembic check
uv run --frozen python -m clearledger.cli init-organization --name "Local synthetic company"
uv run --frozen uvicorn clearledger.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. `/health` checks process health; `/ready` checks
DB connectivity, not migration currency. This server starts empty: the demo uses
separate disposable databases. Some financial import/read routes remain
unauthenticated; loopback and synthetic data only. Never downgrade/reset development
data or expose the local service as a production system.

## Evaluation: measured results, including failures

The frozen independent **development** results below were supplied by the trusted
operator/user. They were not regenerated, rescored or independently re-audited
during this pass. The sealed/blind evaluation remains separate.

| Measurement | Reported/verified result |
|---|---|
| Development stages completed | **255** |
| Snapshot coverage | **Full** for those development stages |
| API-error observations in that run | **0** |
| Conditional matching recall | **0/315** |
| Review-routing score | **0/255** |
| Isolated deterministic LangGraph fixtures | **4 passed**: supported, missing, unsigned, conflicting evidence |
| Gemini3.1 attempts | **6 failed**; minimal probes503,503,504; earlier HTTP400 remains unexplained |
| Historical Gemini3.5 probe | **7 generation responses**; core fields persisted, optional reason-code error retained in original report |
| Later bounded live acceptance | **18 attempts**, accepted typed plan and missing/support/conflict syntheses; corrected reason-code behavior, automatic correlation/refresh, financial non-mutation |
| Real LLM accuracy | Several approved synthetic functional successes, with failures retained; general/held-out accuracy **not established** |

Full snapshot/API coverage demonstrates integration completion, **not reconciliation
usefulness**. Zero recall and review-routing scores remain failures to improve;
safe abstention does not establish effective matching. These 255 stages do not
establish completion of the full 420-receipt/sealed study. Small workflow fixtures
are not benchmark accuracy. Fake-provider tests are explicitly offline controls.

Details: [synthetic usefulness](docs/AI_USEFULNESS_EVALUATION.md),
[live Gemini results](docs/LIVE_GEMINI_EVALUATION.md),
[chronological adapter](docs/CHRONOLOGICAL_EVALUATION.md),
[original snapshot](docs/POST_M09_APPLICATION_EVALUATION.md),
[pilot v1.0](docs/PILOT_EVALUATION.md), [pilot v1.1](docs/PILOT_V1_1_EVALUATION.md).
Independent datasets, hidden answers and original operator/scoring code are not demo inputs.

## Known limitations and future work

- **Model reliability:** Gemini3.1 HTTP400/503/504 failures remain documented.
  Later Gemini3.5 extraction, typed planning/synthesis and automatic review workflow
  succeeded on approved synthetic fixtures; source-validation/decoding/omission
  failures are retained in [LIVE_ACCEPTANCE.md](docs/LIVE_ACCEPTANCE.md).
  This is functional evidence, not broad reliability. External AI remains default-off;
  the UI demo uses labelled offline controls and spends no quota.
- **Frontend scope:** evidence-review workstation is implemented; original financial
  posting queue, complete cash-allocation controls and Argon CASE-204 UI journey
  remain deferred. Production hosting, assistive-technology and broader browser
  validation remain future work. See [FRONTEND.md](FRONTEND.md).
- **Reconciliation usefulness:** improve source-backed matching and actionable
  review routing, then measure against independent scoring without using answers
  as evidence. The current benchmark scores are not improved by this demo.
- **External evaluation:** DocILE/ContractNLI evaluation is future work, not a
  demonstrated result. Review suitability, licensing and contract mapping first.
- **Sealed blind evaluation:** not claimed complete; preserve hidden-answer isolation.
- **Production identity/security:** trusted user identities, source PKI, stronger
  deployment isolation, backups/storage controls and broader adversarial review
  remain open. Test signatures and tokens never authorize finance.
- **Real-customer validation:** no production bank/ERP integration or real-customer
  acceptance is demonstrated. No Indian tax-compliance claim. OCR and payment-total
  extraction remain unsupported; uncertain sources route to review.

The workflow is complete **to review**, with explicit evidence and residual balances.
Approval/settlement and production deployment remain separate, unverified outcomes.
Live AI usefulness is demonstrated only within the documented synthetic acceptance. No financial rule is changed for a better presentation.

## Checks and contracts

Frontend checks (run from `frontend/`): `npm run lint`, `npm run typecheck`,
`npm run test`, `npm run build`, `npm run format:check`. Actual Chromium acceptance:
`npx playwright install chromium`, then `npm run test:browser` against a **fresh**
synthetic host. Browser decisions mutate their test tasks; stop/recreate the owned
disposable host before a full rerun. Nine browser tests and 16 unit tests passed for UX v2.
The API-only portfolio gate remains `uv run --frozen python scripts/portfolio_demo.py`.
Existing broader gates, when appropriate:

```powershell
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

They were not rerun for this pass. The [CI workflow](.github/workflows/verify.yml)
configures disposable PostgreSQL and offline providers; no remote CI result is
claimed. Actual local commands/results and commit hashes are in [STATUS.md](STATUS.md).

Contracts: [CSV v1.0](docs/DATA_CONTRACT.md) · [matching](docs/MATCHING.md) ·
[documents](docs/DOCUMENTS.md) · [cases](docs/CASES.md) · [evidence](docs/EVIDENCE.md) ·
[investigations](docs/INVESTIGATIONS.md) · [accounting simulator](docs/ACCOUNTING_SIMULATOR.md) ·
[review/recovery](docs/REVIEW_RECOVERY.md) · [security](docs/SECURITY.md) ·
[requirements audit](REQUIREMENTS_AUDIT.md).

Dataset research/construction belongs to the independent dataset owner. No realistic
dataset, secret, customer document or private evaluation artifact is committed here.
