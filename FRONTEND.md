# ClearLedger frontend

## Direction exploration, before implementation

| Direction | Analyst job / composition | Strength | Cost |
|---|---|---|---|
| Reconciliation register | Dense ledger, expandable financial rows | Fast comparison and scanning | Evidence investigation becomes secondary |
| Annotated case folio — chosen | Exception register opens a dossier: money comparison, claim/source spread, structured investigation record | Proof stays beside the assertion and human action; strong financial hierarchy, inspectable decisions | Requires careful responsive collapse |
| Evidence relationship map | Claim at centre, source relationships around it, review on a second plane | Relationship exploration | Spatial navigation adds keyboard/mobile complexity; no graph needed for these bounded cases |

Taste installed project-locally using the user-approved skills command. Read SKILL.md
and the complete app-screen guidance; app draw offered two finance styles, pastel
consumer and achromatic ledger. Chose achromatic ledger, seed1233984799, because
long-session evidence review needs ink and alignment rather than coloured containers.
The user's creative brief supersedes the sheet's sidebar/template composition. No
redraw: use its quiet surfaces, Geist typography, one blue source-selection accent,
and no resting shadows. No invented charts, KPI cards, chat or agent animations.

Signature: the **unsettled financial comparison** stays visibly separate from the
**asserted deduction**, followed by independently verified evidence and a human
decision. Money is never presented as applied merely because a source/AI supports it.

Questions: queue — what needs attention? Case — what is asserted and what proves it?
Evidence — exactly where did this fact come from? Investigation — who proposed what,
what did the deterministic validator establish, and what must the human do next?

Implementation/commands, real-browser results and final critique are recorded below
after verification. This task follows the user's React/Vite preference, and does not
claim the original milestone10 financial posting/CASE-204 journey is complete.

## Proven API blocker, documented before the fix

Actual Playwright browser: pending READY_FOR_REVIEW task -> Inspect authenticated
source -> existing /cases/{id}/evidence/records/{record_id} returned422
INVALID_EVIDENCE_REQUEST because the unassociated case has customer_id=null.
EvidenceReader.scope intentionally also requires a verified case customer and scoped
invoice. Relaxing that boundary would be unsafe. Small additive solution: a read-only
review-task proof read, restricted to its exact immutable document/source IDs, current
task snapshot and existing authenticated reviewer/tenant. General evidence tools,
financial authority and existing customer-scope validation remain unchanged.


## Run the actual workstation (Windows)

Prerequisites: Python3.12/uv, Node22.12+ (tested Node24), Docker PostgreSQL and an
ignored `.env` with `TEST_DATABASE_URL` for a local CREATEDB role. Follow README's
Compose setup first. No changes to the shared development schema/data are needed.

From the repository root, terminal1:

```powershell
uv sync --frozen
npm.cmd --prefix frontend ci
uv run --frozen python scripts/serve_frontend_demo.py
```

Wait for `Synthetic UI API ready`. Terminal2:

```powershell
npm.cmd --prefix frontend run dev
```

Open http://127.0.0.1:5173. Read the randomly generated local credentials in
`local-data/frontend/access.json` privately; controller, analyst and auditor share
this run's password. Never commit/share that file. Sessions are memory-only, so
reload requires signing in again. This is LOCAL_DEMO_ONLY identity, not SSO or
production financial authority. API docs are http://127.0.0.1:8010/docs.

The host migrates a fresh generated disposable PostgreSQL DB through0012, creates
five minimal application test cases, then serves real Uvicorn HTTP and the existing
outbox/graph executor. Synthetic signed sources and fake extraction/Investigator
controls are explicitly labelled **Offline control**. They exercise real persistence,
source validation and graph orchestration; they are not live Gemini results. No
external call, benchmark input or production finance adapter is used. All external
AI flags are disabled before HTTP is served. Automation is confined to this host.

### Walk through

1. Queue: open Test / I-1 (missing). Inspect ₹10.01 open AR, ₹9.00 unapplied receipt,
   ₹1.01 asserted damage and ₹0.00 settlement. Nothing has been applied or approved.
2. Case file: open remittance, click invoice/claim. Highlight uses the server's exact
   canonical offsets and independently verified span. Expand provenance if needed.
3. Investigation: navigate Director, plan, tools, verification, synthesis, policy and
   required human action. Missing WMS/POD -> REQUEST_EVIDENCE. Draft an evidence
   request (never sent); see its immutable human action in Audit.
4. I-2: authenticated supporting WMS/POD -> SUPPORTED / HUMAN_REVIEW, with clickable
   citations. I-3: conflicting sources -> CONFLICTING_EVIDENCE / ESCALATE_CONFLICT.
   The screen separates model control, source verification and deterministic policy.
5. I-4/I-5: pending correlation task. Inspect independent proof and proposed financial
   association. Controller deliberately CONFIRMs I-4 or REJECTs I-5 in a dialog.
   History remains; confirmation follows canonical case merge and automatic refresh.
   Auditor can inspect but cannot make the decision. Refresh does not duplicate work.
6. Import & documents accepts real CSV1.0 and parser inputs. It cannot manufacture
   authenticated evidence or enable external AI. Uploads requiring semantic extraction
   return the actual disabled/review state, not a fake successful result.

After browser acceptance these mutable tasks have already been decided. Stop/restart
this owned host for fresh controls, not the shared development PostgreSQL container.
Ctrl+C in terminal1 disposes/drops only its generated DB. An equivalent graceful stop:

```powershell
uv run --frozen python -c "import json; from pathlib import Path; a=json.loads(Path('local-data/frontend/access.json').read_text()); p=Path(a['stop_file']).resolve(); assert p.parent==Path('local-data/frontend').resolve(); p.touch()"
```

Wait for `Owned disposable UI database removed.` Originals/access output remains
ignored locally. Never use Docker down/volume deletion or reset a development DB.

## Architecture and contracts

React + TypeScript + Vite is the approved smallest local FastAPI UI. No SSR/BFF,
Tailwind/shadcn dependency or new agent service. One typed client in `src/api.ts`
uses generated actual OpenAPI types; regenerate with:

```powershell
uv run --frozen python scripts/export_frontend_contract.py
npm.cmd --prefix frontend run contract
```

`/api` is a same-origin local dev/preview proxy to loopback8010; deployment/auth
hardening is not supplied by Vite preview. ReviewDemo credentials stay in memory;
only light/dark preference is persisted in localStorage. No key is shipped to JS.
BigInt/lossless JSON preserves integer paise (including int64); decimal financial
inputs and unsafe numeric conversions are rejected. Unicode offsets count code
points, matching Python, rather than UTF-16 units. Source text is rendered as React
text, not HTML. Server-supplied task/context hashes and versions are echoed exactly;
the browser does not derive proof, amounts or authority.

Routes: `/` operational exception register; `/cases/:id` case file with URL tabs and
stage selection; `/intake` contract-based imports/document parsing. Case/claim/run/
findings/trace/event/review APIs supply all displayed records. No invented priority,
portfolio total or financial action. Bounded pagination loads financial references;
limits fail explicitly instead of inventing missing balances. Queue loads20 cases
at a time with bounded concurrency. This per-case fan-out suits the current local
API; large-company bulk queue projections remain future performance work.

Review writes re-read server basis, use stable request keys and show stale/permission
errors. Only CONTROLLER gets correlation decisions; backend still enforces authority.
Evidence request is draft-only. There are no approval, settlement or posting buttons.
Task proof uses the additive GET `/review/correlation-tasks/{id}/proof` with exact
`expected_task_sha256`; only authenticated/current records already in that task's
snapshot/document are returned. No generic pre-association evidence search is added.

## Actual verification — 2026-10-27

| Check | Observed result |
|---|---|
| `npm run lint`, `typecheck`, `build`, `format:check` (frontend cwd) | PASS |
| `npm run test` | 9 unit tests PASS: int64/paise, Unicode/span, errors, replay key, pagination |
| `CLEARLEDGER_BROWSER_BUILD=1 npm run test:browser` | 8 actual Chromium/API tests PASS,49.2s, production preview |
| Five new PostgreSQL proof tests | 5 PASS,23.88s |
| Existing correlation/review-access regression tests | 25 PASS in initial focused run; new cross-tenant fixture corrected then all5 new tests rerun |
| Ruff check/format on4 changed Python modules; scoped mypy | PASS;23 typed modules |
| npm dependency audit at install | 0 vulnerabilities |
| Taste source critique | 0 FAIL,3 explained warnings: price zero padding, Mono financial values/IDs, missing-value dashes |
| Taste production inspector,1440/768/390 | 0 FAIL,0 WARN on unauthenticated login surface |

Authenticated workbench acceptance uses Playwright library (MCP unavailable, user
approved equivalent): real links/buttons; exact highlight; missing/support/conflict;
proof/confirm/reject/history/merge; draft audit; repeated refresh; auditor boundary;
keyboard focus/dialog cancel/restore;390 dark and768 layouts; no horizontal page
overflow; empty/malformed/offline states via explicitly labelled fault injection.
Happy paths assert zero page exceptions or HTTP>=400 responses. Browser tests compare
financial API snapshots and the worker checks financial fingerprints per drain.
Screenshots contain only these approved synthetic records. No model quota spent.
Detailed logs are ignored `local-data/frontend-*.log`, not copied into Git.
No full backend suite/restart rerun claimed: no lifecycle/storage/schema change;
this task uses the requested narrow backend regressions and fresh DB migration/drift
checks on each demo boot. Remote CI and other browsers/assistive technologies unverified.

### Final design critique

Rejected first4,378px trace: raw fields made the analyst hunt for an action. Replaced
with seven compact persisted stages, one focused panel and adjacent canonical source.
Moved hashes/numeric observations to disclosures; replaced source UUID-only links
with evidence-type labels. Fixed nonfunctional close/reopen, offscreen skip-link
screenshot artifact and pending-proof authorization dead end before final acceptance.
Desktop hierarchy and390 dark case were visually reviewed after the final browser
run. No decorative charts, resting shadows, agent animation or KPI dashboard.

Screenshots: [queue](docs/screenshots/exception-queue.png),
[missing](docs/screenshots/missing-evidence-investigation.png),
[support](docs/screenshots/supported-evidence-investigation.png),
[conflict](docs/screenshots/conflict-evidence-investigation.png),
[correlation](docs/screenshots/correlation-decision.png),
[mobile dark](docs/screenshots/mobile-dark-case.png).

## Limits / explicitly deferred

This delivers the user-approved evidence-review workstation, not every original
M10 financial screen. Original Cash Inbox candidate-allocation controls, simulator/
posting queue and complete Argon CASE-204 financial journey remain deferred. Review
supports local synthetic identity; no production SSO/finance authority is fabricated.
PDFs download as immutable originals; canonical extracted text is the inline source
viewer (no full PDF annotation canvas/OCR). No live models run for screenshots.
Large queue aggregation, manual screen-reader audit, broader browser coverage and
production hosting/CSP/identity integration remain unverified/future work. Existing
benchmark failures and sealed evaluation are unchanged. No backend feature expansion
beyond the demonstrated task-proof read defect.
