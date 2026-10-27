# ClearLedger frontend — final financial-operations workstation

## Final visual system — frozen after this checkpoint

UX v2's financial story, progressive disclosure, APIs and workflow semantics are
preserved. This final pass changes presentation and interaction feedback only.
Frontend feature/design expansion is now **FROZEN**. Independent evaluation is the
next workstream; it is not started automatically. Fix only concrete blockers under
separate task scope. Original deferred M10 financial gates remain deferred.

### ClearLedger language: paired rails and proof layers

The invoice minus receipt comparison is one connected financial object. The open
paired edge on the difference echoes the ledger mark; it is not a completion bar.
The customer claim is a subordinate strip, visibly distinct from cash received.
The assessment uses a charcoal interpretation field, evidence uses a paper stack,
human action uses a restrained ochre band, and the finance boundary stays quiet and
locked. These are different functional modules, not interchangeable white cards.

`src/visual-system.css` owns final tokens and composition. Geist400/500/600/700 are
really self-hosted; no synthetic bold, external font CDN or new UI dependency.
Scale13/14/16/20/24 with26–38px tabular financial figures. Spacing uses a4px base
with deliberate22px vertical/26px horizontal optical gutters; module/control/state radii10/6/4px. Thin structural edges,
no resting-card shadows, and one restrained elevation on the actual review dialog.
The queue keeps comparable rows, tighter spacing, stable numeric alignment, real
state labels, hover/focus context and a filter-result transition. No giant card queue,
KPI dashboard, decorative chart, gradient, glass or AI animation.

| Meaning | Light theme token | Shape / text / surface |
|---|---|---|
| Financial relationship / selection | Teal #176b61 | Paired ledger edge, full exact amount, explicit comparison-only label |
| AI interpretation / offline model control | Cobalt #315b9b | Diamond; AI generated or Demo model; never verification authority |
| Independently verified source | Forest #21624d | Shield/check, source title and verification status |
| Deterministic rules | Blue-grey #4e6370 | Square/check and Rules check |
| Human action | Ochre #76521e | Open/circular stage mark, contextual decision band, explicit review action |
| Conflict | Red #a43d3d | Disagreement text and status; not an invented resolution |
| Missing proof | Amber #785118 | Question mark and missing/unverified wording |
| Financial permission | Muted graphite | Lock and Not granted by this review; separate recorded settlement |

Colors never carry meaning alone. Dark mode uses neutral ink surfaces and separately
contrasted semantic tokens. The brand idea remains: a receipt is a fact, a deduction
is a claim. It is expressed in the comparison/review boundaries rather than a large
marketing panel inside the case.

### Composition and motion

Desktop shows assessment and proof together, with a separate human-action band.
Tablet/mobile recompose the modules: financial story, assessment, human action,
evidence and finance boundary. The default case content is unchanged. Technical
trace keeps the same monetary context in a compact rail so the execution flow is
inspectable without another document-length preamble.

Persisted graph stages form a connected, horizontally scrollable execution strip.
Model stages have diamonds; rules stages squares; required-human-action has its own
mark. Clicking reveals only persisted structured fields. Offscreen stages remain
keyboard reachable. No fabricated stage, hidden thought, agent chatter or live-work
animation; fake providers remain explicitly Demo scenario / Demo model.

Motion tokens:150ms feedback,220ms content changes,280ms source/financial reveal;
source close160ms. Only actual route/case mounts, tab/filter changes, selected stages,
verified citation selections and completed review results animate. Monetary values
never count up, interpolate or suggest cash application. Full integer-paise values
are shown throughout. Source chips become selected only after the source verifier
accepts their exact span. Quote highlight is keyed to the verified selection.

The source pane remains docked/in-flow rather than becoming a second modal system.
Open/close motion, source header, value chips and expandable provenance make its
source hierarchy clear. Original/canonical hash-copy controls provide feedback only
after the browser clipboard succeeds; denial says Copy unavailable rather than
pretending success. This is a read-only provenance affordance, not a new business
workflow. Native review dialogs keep claim/payment/proof context,
focus on cancellation initially, restore focus and explicitly deny posting authority.
Only the dialog floats; no glass/backdrop blur. A review-note screenshot was captured
with an unsent client-side note, then cancelled; it is not a fabricated audit record.

All motion, including source closing, is bypassed under prefers-reduced-motion.
Focus outlines remain visible, source reveal receives focus, closing returns it,
and keyboard navigation remains usable at every tested width. The financial anchor
was compared before/after source reveal after entrance transforms settled: identical
layout coordinates/dimensions. Intentional opacity/transform feedback is not reported
as an accounting change or model progress.

### Final real-browser acceptance

- 16 unit tests passed, preserving the existing monetary/source/display assertions.
- 10 production Chromium browser tests passed in 1.2m: all 9 prior tests plus four-width
  execution/source/motion/financial-anchor coverage. Real Uvicorn/PostgreSQL APIs,
  strict citations, missing/support/conflict, controller CONFIRM/REJECT, immutable
  history/merge/replay, auditor boundaries, actual drafts, malformed/offline/empty,
  source selection/focus, native review, reduced motion and responsive states.
  Happy paths assert no page/runtime or HTTP>=400 observations. No source/financial
  assertion weakened. Invoice/receipt snapshots and worker fingerprints unchanged.
- ESLint, TypeScript, production build and Prettier passed. No production backend,
  schema/migration, financial rule, new dependency, CSV or benchmark change. Backend
  full-suite/restart checks were not rerun or claimed for a client-only visual pass.
- Taste's actual authenticated browser probes/rules:0FAIL/0WARN at1440×1000 desktop,
  1280×1000 laptop,768×1000 tablet and390×1000 mobile. Source lint0FAIL/4 justified
  warnings: existing price padding, technical monospace, missing-value dash and
  shadow on a real modal (explicitly permitted). Desktop/mobile, source/trace and
  contextual review screenshots were also inspected, beyond the measurements.
- An initial focused run caught3 navigation failures from the delayed close callback
  restoring captured old search parameters. It now uses the latest close callback;
  unmount clears the timer. The fourth failure sampled a deliberate entrance
  transform. The test now awaits actual finite animations before making the SAME
  strict geometry comparison. Repaired4/4 passed, then the full 10 passed.
  Final real-clipboard copy/source/motion case passed separately in8.2s; development
  URL startup/queue/source smoke passed in7.6s, preserving the earlier blank-page fix.

Detailed logs remain ignored `local-data/frontend-final-*.log`. Browser criterion
is absence of observed unexpected clipping/overflow/focus/runtime failures in these
flows, not an unperformed all-device or assistive-technology certification.

### Final media and interview sequence

[58-second actual-API synthetic walkthrough](docs/media/clearledger-workstation.webm)
(57.75s,1280×900,4.47MB, no audio). Login footage is trimmed out; the first frame was
visually checked. Viewing pauses help a human inspect fields and are not reported as
provider latency. The recording includes actual controller confirmation and unchanged
invoice/receipt API snapshots, with zero page/HTTP errors. Offline providers are
visible; this is not new live Gemini accuracy evidence.

Screenshots: [queue](docs/screenshots/exception-queue.png),
[missing](docs/screenshots/missing-evidence-investigation.png),
[support](docs/screenshots/supported-evidence-investigation.png),
[conflict](docs/screenshots/conflict-evidence-investigation.png),
[highlighted source](docs/screenshots/evidence-source-highlighting.png),
[human review](docs/screenshots/human-review.png),
[execution trace](docs/screenshots/technical-ai-trace.png),
[decision history](docs/screenshots/correlation-decision.png),
[laptop](docs/screenshots/laptop-case.png), [tablet](docs/screenshots/tablet-case.png),
[dark mobile](docs/screenshots/mobile-dark-case.png).

Suggested60–90s interview:0–12 queue and50,000−47,000=3,000;12–25 missing proof and
exact remittance quote;25–40 signed support;40–52 conflicting delivery;52–72 inspect
payment proof, deliberate controller decision/history;72–90 execution plan, verifier,
policy and financial boundary. Say explicitly: offline replayable fixtures here;
historical real Gemini acceptance is documented separately. Review does not post.

No reproducible portfolio-blocking defect remains in the tested flows. After this
commit, further visual/feature expansion is frozen. The earlier UX rationale, setup,
security limits and original deferred gates below remain applicable.

## Product direction and scope

A short-payment **reconciliation statement** is the organising idea: invoice minus
receipt equals difference, with the customer's explanation directly beneath it.
Evidence follows, then the assessment/review action. Engineering trace is opt-in.
No backend business behavior, migration, financial authority or benchmark was changed.

Three materially different UX directions were compared before implementation:

| Direction | Strength | Why selected / rejected |
|---|---|---|
| Reconciliation statement — selected | The money, discrepancy and next action can be read together; sources explain the result | Directly answers the AR analyst's first question; works with existing typed APIs |
| Guided decision brief | Stepwise questions make review approachable | Slows repeated scanning; forces navigation to understand one case |
| Evidence desk / spatial source map | Strong source-to-assertion inspection | Asks newcomers to reconstruct the financial story; keyboard/mobile cost; resembles the v1 comprehension problem |

Taste is critique guidance, not a wireframe. Existing achromatic-ledger direction
(seed 1233984799) is retained; no new visual draw or template adoption. The new
signature is **invoice − received = short payment**, not a KPI row or graph diagram.
The same real values drive queue and case. No decorative chart, chatbot or marketing
panel occupies case-workspace space. Current Vercel Web Interface Guidelines were
reviewed for interaction/accessibility quality.

The user explicitly approved changing only the five application-owned UI fixtures
into recognisable, synthetic business examples. Meridian Retail Pvt Ltd,
INV-2026-1042–1046, invoice ₹50,000, receipt ₹47,000 and damage claim ₹3,000 are
persisted through actual APIs, not substituted labels in the browser. Missing,
supported, conflicting and undecided association states retain the same strict
source and review contracts. Independent benchmark/pilot files were not accessed
or modified. This permission does not transfer Argon's dataset ownership.

## Information hierarchy

1. **What happened:** a connected equation with a larger difference figure. The
   customer-claimed damage amount sits beneath the equation, explicitly unapproved.
2. **What to do:** a specific next step and recorded settlement appear immediately
   beside the financial story, even before scrolling to the full review action.
3. **What was checked:** source-authenticated remittance, warehouse and signed POD
   status. Missing proof and conflicting facts are explicit; citations open originals.
4. **What ClearLedger found:** concise result, uncertainty and provenance. A supported
   source predicate is translated into evidence support, never financial permission.
5. **Human review:** draft-only evidence request, review note or deliberate controller
   association decision. Review context stays in the dialog with amount and proof.
6. **On demand:** Technical trace, provider/model, structured plan/synthesis, tools,
   verification/policy, usage/errors, hashes, versions, IDs and precise offsets.

Queue rows explain the short payment, claimed category, evidence problem and next
step. Pending association references are labelled **Proposed**, never presented as
verified customer/payment intent. Unknown linked amounts remain unknown, not zero;
the case financial equation waits for verified associations. Filters/search/pagination
use real records and clearly state loaded-page scope; no invented totals or urgency.

### State and provenance language

| Layer | Visual and wording | Boundary |
|---|---|---|
| Model suggestion | Distinct origin mark and explanatory line; AI assessment only for persisted Gemini output | Recommendation, never evidence authenticity |
| Offline model fixture | Demo scenario, explicitly says no live AI in this demo | Cannot be counted as live model success |
| Source verified | Shield check, evidence row and clickable source | Authenticated/current source; not approval |
| Rules check | Check mark and separate technical verification stage | Deterministic validation; not AI reasoning |
| Human decision | Diamond marker, contextual review and immutable decision history | Association/draft/note only |
| Conflict / missing | Explicit disagreement or missing-proof wording, restrained status color and icon | Abstention; no guessed resolution |
| Financial permission | Lock, separate authorization status and recorded settlement | Not granted by this review; no posting controls |

Evidence, human review, financial authorization and settlement are separate states.
The UI says **not granted by this review**, rather than inventing a production-wide
approval status it has not fetched. No screen action posts an adjustment. Open AR
and unapplied cash remain actual backend values; the equation is comparison only.

## Source and investigation experience

An extracted field/citation reveals an in-flow inspector with exact original-source
text. Highlighting calls the actual span verifier, checks quote/offsets, hashes and
versions, and counts Unicode code points consistently with Python. Quote verified in
source proves location, not legitimacy. Existing citation record IDs may supply
source context; a document with no such record does not gain invented authentication.
Hashes/offsets/version details are in expandable provenance, not default case copy.
Original download remains authenticated. Untrusted source text renders as text.

The source checklist follows persisted plan evidence types, missing-proof facts and
verified source kinds; it does not invent warehouse/POD requirements for rebate or
other claim categories. Default overview says what was checked and the specific action: request signed POD,
review supported deduction or resolve conflicting delivery records. Technical trace
opens the existing persisted Director/plan/tools/verifier/synthesis/policy/human stages.
No hidden chain-of-thought, simulated progress or relabelled fallback as AI. A pending
payment task keeps independent payment proof distinct from deduction findings; its
review dialog does not incorrectly describe zero findings as zero payment proof.

## Motion and accessibility

180–200ms opacity/transform feedback for source reveal, selected persisted stage,
dialog and saved result. No typing, artificial loops, synthetic work or provider-call
animation. `prefers-reduced-motion` removes animations; actual browser coverage verifies
it. Screenshots disable animations to capture completed states, not translucent frames.

Native semantic tables/links/buttons/forms, visible focus, skip link, labelled inputs,
URL tabs/filters, native modal focus trap/cancel/restore and inline failures. Submit
remains enabled for native required-file validation; no request is sent without a file.
Source reveal receives focus; closing returns to its trigger. Tablet/mobile preserve
financial hierarchy without horizontal page overflow; dark mode remains available.
Keyboard, dialog Escape/cancel,390/768/1440 widths and reduced motion were exercised.
Screen-reader/other-browser acceptance remains unverified, not claimed complete.

## Run locally — Windows

Prerequisites: Python 3.12, uv, Node 22.12+ (tested 24.22), Docker PostgreSQL. Configure
ignored `.env` with `TEST_DATABASE_URL` for a local CREATEDB role; follow README Compose
setup. No shared development migration/reset/restart is needed by this UI demo.

Terminal1 from repository root:

```powershell
uv sync --frozen
npm.cmd --prefix frontend ci
uv run --frozen python scripts/serve_frontend_demo.py
```

Wait for Synthetic UI API ready. Terminal2:

```powershell
npm.cmd --prefix frontend run dev
```

Open http://127.0.0.1:5173. Privately read the generated controller password in ignored
`local-data/frontend/access.json`. Analyst/auditor use the same run's password. The
loopback API uses port 8010; API docs `/docs`. Sessions are memory-only; reload requires login.
The Local synthetic session badge remains visible on desktop. No production authority.

The host creates/migrates only a fresh generated disposable DB through 0012, imports
actual records/documents, registers explicit synthetic source trust, processes the
existing outbox and runs the actual LangGraph executor. Provider responses are existing
fake controls, clearly labelled. External AI is disabled before serving; no Gemini key
or real provider configured. This is a repeatable product demo, not live-model evidence.

Ctrl+C cleans its owned database. Equivalent graceful stop from repository root:

```powershell
uv run --frozen python -c "import json; from pathlib import Path; a=json.loads(Path('local-data/frontend/access.json').read_text()); p=Path(a['stop_file']).resolve(); assert p.parent==Path('local-data/frontend').resolve(); p.touch()"
```

Wait for Owned disposable UI database removed. Restart that host for fresh undecided
review tasks; do not reset shared PostgreSQL. Credentials/originals/logs remain ignored.

## Recommended interview demo — 60–90 seconds

| Time | Show | Explain |
|---|---|---|
|0–12s|Queue, open INV-2026-1042|50,000 billed,47,000 received,3,000 claimed damage; no adjustment posted by review|
|12–25s|Missing evidence overview and View evidence|Remittance quote is real; required warehouse/signed POD proof is absent; draft only|
|25–40s|INV-2026-1043 supported case|Verified source facts support ₹3,000; analyst review and financial authorization remain separate|
|40–52s|INV-2026-1044 conflict|Delivery sources disagree; escalate instead of choosing a convenient answer|
|52–72s|Payment match filter, Proposed INV-2026-1045|Inspect independent proof, deliberate controller confirm; history/merged case/refresh; no cash applied|
|72–90s|Technical trace on any case|Actual persisted plan, read-only tools, source verification and policy; this repeatable demo uses offline controls, historical real Gemini proof is separate|

## Actual acceptance — 2026-10-27

Commands from `frontend/`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
npm.cmd run format:check
npx.cmd playwright install chromium
$env:CLEARLEDGER_BROWSER_BUILD='1'
npm.cmd run test:browser
```

Use fresh disposable cases before repeating the full browser suite; controller tests
intentionally decide their tasks. Production preview on4173 proxies the same API8010.
Pinned installed Chromium; no Playwright MCP exposed, library equivalence authorised.

- 16 unit tests passed, preserving all 9 original cases. Seven new display invariants:
  exact/large integer paise, unknown versus zero, excess receipts, specific missing
  proof, fallback provenance, incomplete payment proof and stale-support override.
- 9 production-browser tests passed in 1.0m: all 8 earlier workflows retained with new
  visible labels, plus finance-led intake/native validation/reduced-motion coverage.
  Real queue/case/citation APIs, missing/support/conflict, complete technical stages,
  controller confirm/reject/decision history/merge, auditor boundary, contextual draft,
  financial non-mutation, replay without visual duplication, focus, dark/mobile/tablet,
  explicit empty/malformed/offline fault injection. Happy paths assert no page errors
  or HTTP>=400 responses. No mocked UI success states populate the screenshots.
  After final copy/type refinements, the4 focused queue/story/source regressions
  passed again in 25.4s, including actual primary next-action navigation.
- ESLint, strict TypeScript, Vite build, Prettier and Ruff check/format for the only
  changed Python fixture host passed. No production Python/API/schema change; backend
  suite/restart checks were not rerun or claimed. Each owned host boot runs real
  Alembic upgrade/drift checks. Existing backend regression tests remain untouched.
- Taste source lint:0FAIL,3 explained warnings (price zero-padding; existing technical
  Mono; missing-value dash). Actual authenticated production case using Taste's own
  probes/rules via Playwright:0FAIL/0WARN at1440/768/390 after typography revision.
  Inspector metrics are a floor; desktop/mobile/dialog/source screenshots also reviewed.
- Initial expanded browser run had8PASS/1FAIL due to the newly added test assuming a
  disabled Submit. Corrected to native required-file/no-request validation; final 9 pass.
  JSX edit and minimal unit-fixture typing errors were fixed before acceptance.

Detailed logs: ignored `local-data/frontend-v2-*.log`; authenticated critique report
`local-data/frontend/v2-authenticated-taste.json`. No full backend gate, remote CI,
live Gemini, benchmark rerun or empirical first-time-user timing study is claimed.

### First-time comprehension audit

| Question | Default screen answer / browser assertion |
|---|---|
|What happened?|Invoiced minus received equals short payment, connected in one statement|
|How much?|50,000 −47,000 =3,000 INR, actual integer-paise API values|
|Why?|Customer's damage explanation directly beneath the financial equation|
|What evidence?|Remittance/warehouse/signed-POD checklist, explicit missing/conflicting source status|
|What did AI contribute?|Demo scenario explicitly labelled offline; real provider/plan/synthesis inspectable on demand|
|What was independently checked?|Authenticated/current source status; exact quote checked separately on click|
|What must I do?|Specific next step visible in the statement before 900px, contextual human action below|
|Was anything financially approved/posted?|Claim not equated to approval, authorization not granted by review, actual case settlement0; financial snapshots unchanged|

These are structural/browser/author critiques, not measured 5–10s research with new
finance users. That human usability study remains open. Worst issues fixed after
critique: action too low -> immediate next step; small text -> raised labels and fewer
sizes; dialog lost source context/translucent screenshot -> explicit payment proof,
financial pairing and completed-motion captures. No major static marketing panel.

## Architecture / limits

React/TypeScript/Vite, centralized generated-OpenAPI client, BigInt/lossless JSON;
no BFF/new dependency/framework. Backend owns all authorization, snapshot hashes,
versions, idempotency and domain transitions. Existing task-bound proof read fromv1
is reused unchanged. API generation remains:

```powershell
uv run --frozen python scripts/export_frontend_contract.py
npm.cmd --prefix frontend run contract
```

Queue fan-out/pagination stays bounded/local; no bulk company-wide search or invented
analytics. PDF original downloads; inline inspector is canonical text, not PDF/OCR
annotation. Production SSO/finance authority/deployment hardening remain open. Original
M10 cash-allocation controls, posting queue and Argon CASE-204 journey remain deferred.
Full benchmark failures and sealed evaluation remain unchanged. Fake demo scores are
not live Gemini or benchmark accuracy. No backend feature expansion was undertaken.

Screenshots: [queue](docs/screenshots/exception-queue.png),
[missing](docs/screenshots/missing-evidence-investigation.png),
[supported](docs/screenshots/supported-evidence-investigation.png),
[conflict](docs/screenshots/conflict-evidence-investigation.png),
[source highlighting](docs/screenshots/evidence-source-highlighting.png),
[human review](docs/screenshots/human-review.png),
[technical trace](docs/screenshots/technical-ai-trace.png),
[decision](docs/screenshots/correlation-decision.png),
[mobile](docs/screenshots/mobile-dark-case.png), [tablet](docs/screenshots/tablet-case.png).

## Development blank-page troubleshooting

The27 October dev server was observed serving an empty cached CaseFile module while
source exports and production4173 remained valid. Vite's Windows watcher now waits
200ms for stable writes before invalidating/transformation. If an already open tab
retains a failed startup, refresh it. Restart `npm run dev` if necessary; do not reset
PostgreSQL. `npm run build` then `npm run preview` on4173 is the verified production
preview alternative. Both use the same real API proxy. This repairs development
module loading, not accounting, authentication or case data.
