# ClearLedger portfolio deployment

The public workstation is a read-only synthetic demo. A Render Static Site
calls the separate Render Free FastAPI service over HTTPS. The API uses a
dedicated Neon Free PostgreSQL 16 database in Singapore. Public visitors can
inspect cases, source documents, correlation proof and investigation traces.
Imports, review decisions, finance routes and external Gemini are unavailable
through the public gateway.

## Build and startup

| Service | Configuration |
| --- | --- |
| API | Render Free, Singapore, GitHub `main`, Python 3.12 |
| API build | `python -m pip install uv==0.13.5 && uv sync --frozen` |
| API startup | `uv run --frozen python scripts/serve_portfolio.py` |
| API health check | Existing `/ready` endpoint through the public gateway |
| Static build | Node 24, root `frontend`, `npm ci && npm run build`, publish `dist` |
| Static routes | The public build uses hash-based routes so case URLs refresh on the static host. |

`render.yaml` records the build definition. Use manual deploys from
`main` until GitHub Actions completes reliably. Render supports switching
both services to `checksPass` once that condition holds.

## Configuration

Set these values through Render. Connection credentials can be provided as
environment secrets or as Render secret files of the same name. Keep the
frontend variable limited to the API's public HTTPS origin.

| Service | Name |
| --- | --- |
| API | `DATABASE_URL`, `PORTFOLIO_MIGRATION_DATABASE_URL`, `PORTFOLIO_ORIGIN`, `PORT`, `PYTHON_VERSION` |
| Static | `VITE_API_BASE_URL`, `NODE_VERSION` |

Use direct Neon connections with TLS. The startup wrapper requires the
`clearledger_portfolio` database, verifies the hostname, and enforces
`sslmode=verify-full` and channel binding. The migration connection owns the
schema. The runtime can use a separate login with schema usage, table reads,
and insert permission on `demo_sessions` and `demo_auth_events` for the
server-owned auditor session. It needs no database-creation or replication
permission. CORS allows the exact static site origin.

## Migrations and synthetic data

The wrapper applies the repository's Alembic head and runs the drift check
under a PostgreSQL advisory lock. On the first boot of the empty dedicated
database, it runs the existing synthetic workstation fixture through the
application APIs. The fixture's model output comes from its in-process
offline controls. The runtime has zero external provider budget.

The bootstrap keeps one completed synthetic organization. If initialization
is interrupted, startup stops on the incomplete seed marker. Do not repoint
this service to a development database. Every restart reconstructs original
synthetic text files from the stored canonical source and checks each SHA-256
against the original hash. This avoids a paid disk and preserves source
highlighting across spin-downs.

The public API admits only its enumerated reads and exact document-span
verification. It uses the existing FastAPI application on loopback with a
server-owned local auditor session. The session credential stays on the
server. The span check uses the application's source-integrity read and span
validator. The ordinary workstation's authentication and finance boundary
remain unchanged.

## Redeployment

Deploy the API first, then build the static site with its public API origin.
If the assigned static URL differs from the intended origin, update only the
API origin setting before the final smoke test. Check the exception queue,
supported/missing/conflicting cases, correlation proof, exact source
highlighting and trace on the public static URL. Check that finance and review
writes are unavailable and financial snapshots are unchanged.

Render Free can take about a minute to wake after inactivity. The public
build shows a startup message and offers a retry if the initial request
fails. The local performance report excludes hosting cold starts.
