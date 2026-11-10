# ClearLedger portfolio deployment

The public workstation is a synthetic portfolio sandbox. A Render Static Site
calls the separate Render Free FastAPI service over HTTPS. The API uses a
dedicated Neon Free PostgreSQL 16 database in Singapore. Public visitors can
inspect cases, source documents, correlation proof and investigation traces.
Financial imports, review decisions, and finance routes are unavailable through
the public gateway. The optional sandbox Gemini paths are separate from application
investigation and posting.

## Live services

| Service | Public URL | Region |
| --- | --- | --- |
| Workstation | [ClearLedger](https://clearledger-jduu.onrender.com) | Render Static Site CDN |
| API | [API readiness](https://clearledger-api-we3g.onrender.com/ready) | Render Free, Singapore |
| Database | Dedicated Neon Free PostgreSQL 16 | Singapore, `aws-ap-southeast-1` |

The deployed schema is at Alembic revision `0012_correlation`. The
synthetic fixture includes missing, supporting and conflicting evidence
cases plus a payment-correlation review. The API runs
`45c110df6d680d9d909ede30ce91b4866370e236` and the frontend runs
`faed95e5897cafbc6c6e682e2a6462c3772920da`. The required GitHub Actions
runs passed for [the API](https://github.com/Arnavvats287/clearledger/actions/runs/42750161797)
and [the frontend](https://github.com/Arnavvats287/clearledger/actions/runs/42745435562).
Five public Chromium scenarios verified demo entry and sign-out, all seeded
registers and evidence states, source and trace inspection, a real sample
upload, mobile layout, browser-only review, refresh recovery, and retry after
a simulated startup failure. The
browser and focused backend tests used controlled Gemini replies for
visitor-key verification. There were no live Gemini calls in deployment
acceptance. The public bundle scan found no credentials or private paths.
The Neon fingerprint covering finance and seeded case tables matched before
and after the hosted smoke. Public finance, import and review writes were
blocked.

## Build and startup

| Service | Configuration |
| --- | --- |
| API | Render Free, Singapore, GitHub `main`, Python 3.12 |
| API build | `python -m pip install uv==0.13.5 && uv sync --frozen` |
| API startup | `uv run --frozen python scripts/serve_portfolio.py` |
| API health check | Existing `/ready` endpoint through the public gateway |
| Static build | Node 24, root `frontend`, `npm ci && npm run build`, publish `dist` |
| Static routes | The public build uses hash-based routes so case URLs refresh on the static host. |

`render.yaml` records the build definition. These services use a public
repository URL and deploy manually from `main`. Render requires a connected
Git provider for [automatic deploys after CI passes](https://render.com/docs/deploys#automatic-deploys).
Check GitHub Actions before manually deploying application changes.

## Configuration

Set these values through Render. Connection credentials can be provided as
environment secrets or as Render secret files of the same name. Keep the
frontend variable limited to the API's public HTTPS origin.

| Service | Name |
| --- | --- |
| API | `DATABASE_URL`, `PORTFOLIO_MIGRATION_DATABASE_URL`, `PORTFOLIO_ORIGIN`, `PORT`, `PYTHON_VERSION` |
| Static | `VITE_API_BASE_URL`, `NODE_VERSION` |
| Optional included demo | `PUBLIC_DEMO_GEMINI_KEY` (API service only) |

Use direct Neon connections with TLS. The startup wrapper requires the
`clearledger_portfolio` database, verifies the hostname, and enforces
`sslmode=verify-full` and channel binding. The migration connection owns the
schema. The runtime can use a separate login with schema usage, table reads,
and insert permission on `review_demo_sessions` and `review_demo_auth_events` for the
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

Seed from the API region so database round trips fit the existing workflow
limits. For this dedicated synthetic database only, an operator can temporarily
append `--refresh-timeouts` to the startup command if the three seeded evidence
cases timed out. It appends new workflow results through the existing offline
fixture and leaves the earlier results in history. Return to the ordinary
startup command after the refresh.

The public API admits only its enumerated reads and exact document-span
verification. It uses the existing FastAPI application on loopback with a
server-owned local auditor session. The session credential stays on the
server. The gateway runs application reads in PostgreSQL read-only
transactions using the existing evidence read path and company locks. Only
the server-owned auditor login needs the restricted insert grants. The span
check uses the application's source-integrity read and span validator. The
ordinary workstation's authentication and finance boundary remain unchanged.

## Public sandbox

Visitors enter with **Continue as Demo Analyst**. The public identity uses the
existing auditor boundary and cannot grant financial authority. The browser keeps
an opaque two-hour demo session token in tab-scoped storage so refresh works.
Sign-out revokes that token. The seeded read API remains public, and the token
gates sandbox actions. Invoice, receipt, remittance, and case records are read-only.

The public UI loads one authenticated `GET /portfolio/bootstrap` snapshot
for the four registers. Case links prefetch a bounded
`GET /portfolio/cases/{id}` projection on hover or keyboard focus. Both
projections use the existing case views in read-only transactions and return
metadata, with original documents fetched only by explicit source actions.
Portfolio projection admission verifies the server-owned auditor under the
shared case lock, so an overlapping refresh does not block a new session's read.
Successful public GETs are reused in memory by the active demo client.
Document text is keyed by document ID, version, and both source hashes.
Manual refresh replaces data on success and keeps the previous view on error.
Sign-out cancels pending public reads before revoking the session and clears the cache.

The existing review dialogs can simulate evidence-request drafts, review notes,
and correlation decisions in browser memory. Their results are labelled
**Demo simulation** and clear on sign-out or full reload. Canonical review and
financial writes remain blocked at the gateway.

### Public browser navigation measurements

These are single warm Chromium measurements on the hosted site, timed from
the action until the destination content was visible. Counts include only
data GETs to the API. Entry also uses one session POST and one identity GET
in both builds. CDN assets and CORS preflights are outside these counts.

| Flow | Before GETs | After GETs | Before | After |
| --- | ---: | ---: | ---: | ---: |
| Demo entry → Exceptions | 35 | 1 | 15.27 s | 6.53 s |
| Exceptions → Invoices | 3 | 0 | 2.93 s | 66 ms |
| Invoices → Receipts | 3 | 0 | 2.91 s | 63 ms |
| Receipts → Remittances | 2 | 0 | 2.89 s | 65 ms |
| Exceptions → first case open | 11 | 1 | 4.44 s | 3.10 s |
| Case → Exceptions | 35 | 0 | 14.61 s | 52 ms |
| Reopen the same case | 11 | 0 | 4.50 s | 274 ms |

A separate Free API wake probe reached its 65-second deadline before the API
became ready. The warm run began after a successful 390 ms readiness probe.
Earlier live smoke exposed a sign-out cancellation race and overlapping-read
contention. The final smoke passed the targeted regressions on the deployed
revisions above.

The upload endpoint accepts PDF, TXT, JSON, and EML up to 2 MiB after explicit
consent. The existing isolated parser receives the bytes through a pipe and
returns canonical text. Uploaded originals and parser results are never written
to disk or PostgreSQL. There is no URL fetching, OCR service, or financial import
in this endpoint. Unsupported formats and active content are rejected by the
existing parser. Structured references and amounts retain their exact spans.

PostgreSQL stores only token hashes, expiration, and admission counters in the
separate `portfolio_demo` schema. The API startup provisions it idempotently
through the migration credential. The runtime role can write only the sandbox
metadata and its existing auditor authentication events, outside the financial
tables. Limits are 15 uploads, one included generation attempt, and three
visitor-key attempts per session. Global UTC limits are 1,000 new sessions,
300 uploads, 20 included attempts, and 40 visitor-key attempts per day.
Reservations precede the provider call and a failure consumes an attempt.

The included call uses only a bundled synthetic missing-POD case. It is disabled
without `PUBLIC_DEMO_GEMINI_KEY`. To enable it, create a separate Gemini demo
project and put its key in **Render → clearledger-api → Environment** under
that name. Save and deploy. Use only the dedicated demo key. The fixed model is
`gemini-3.5-flash-lite`. Unavailable models and provider failures leave the
deterministic result available. No substitute model or retries are configured.

Visitors may separately enter their own Gemini key and consent to Google
processing. Only a bounded privacy-filtered projection leaves the application.
The credential travels in a request header over HTTPS, is cleared from the input
when submitted, and is passed to a fresh isolated worker. There is no key storage,
logging, caching, or durable trace. Sandbox responses use `Cache-Control: no-store`.
Provider requests use the existing fixed Google transport and strict local
source validation, with an 8,192 input-token cap and a 2,048 output-token cap.
The upload AI path also limits canonical input to 6,000 characters. Google
processing is governed by the [Gemini API terms](https://ai.google.dev/gemini-api/terms).

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
