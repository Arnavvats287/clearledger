# ClearLedger requirements-alignment audit

## Milestone 08 accounting traceability - 2026-10-25

Authorized from `c4cd3e3`, branch `feat/milestone-08-policy-ledger`. Original
`prompts/08-policy-ledger.md` is unchanged. Contract: `docs/ACCOUNTING_SIMULATOR.md`.

| Original requirement | Implementation | Verification |
|---|---|---|
| Versioned chart/approval policy; conditional reviewed tax support or review | `finance_contract/models/service/validation` | Exact fixture IDs/amount/date/evidence binding, unknown/unsigned/opposing/date tax abstention, distinct income-tax/GST accounts; no universal rate |
| Bank once, cash/noncash journal application, no damage writeoff | `finance_domain`, `finance_posting` | Unchanged CASE-204 oracle debits/credits and AR 250,000; repeated partial applications book bank once; multi-invoice and independently verified allowance |
| Source/rule/version proposals; balance insufficient | `finance_repository/validation`, immutable snapshots | Strict fractional/bool/overflow/account checks, wrong tenant/missing source, stale balances/policy/evidence/original/approval, matching-intent/source review |
| Required authorization/review/maker-checker gates | `finance_identity/service/api`; unavailable default adapter | Local token/actor spoof and self approval denied, human/service/permission boundary, revocation/expiry/CAS; fixture identities are not SSO |
| Atomic, concurrent, idempotent PostgreSQL posting | 0010 scoped FKs, unique keys, immutable/deferred guards; locks in posting | Real same/different-key concurrent requests, replay, failure rollback, conservation, history and DB tamper rejection |
| Audit evidence/status/persistence | `finance_lifecycle/invalidation`, finance audit/commands | PARTIALLY_SETTLED, proof-backed tax resolution, unsupported damage waiting/open; fresh processes/connections/owned PostgreSQL restart without duplicate effects |

Final full gate: **563 passed in 964.09s (507 retained + 56 new), no skips**; all
static/migration/integrity/performance gates passed. Isolated restart: **3 passed in
32.52s**. Finance-focused 49 tests plus 7 final targeted checks also passed.
Existing static/migration/performance checks are retained; bounded test/CI timeouts were
extended for suite growth, not product limits. Up-only migration preserved every old
table fingerprint (47 tables). Both pilot ZIP hashes are unchanged. Exact logs/results/
checkpoint are in STATUS; no completion is claimed until the final gate passes.

G1 production identity/RBAC/RLS remains **unresolved**: finance defaults denied without
a trusted adapter; fixture identities prove controls, not real users. Broader review/
identity provisioning/correspondence/recovery/closure stays M09. Real tax rules, publisher
PKI/key custody/live-bank validation, live Gemini/privacy, remote CI and full Argon
benchmark/ablation remain unverified. No dataset, paid call, Redis, MCP or later milestone.

## Milestone 07 Director–Investigator traceability - 2026-10-25

Authorized from verified `e9b970b`, branch `feat/milestone-07-directed-investigation`.
Original `prompts/07-directed-investigation.md` is preserved and authoritative.
Contract and operational limitations: `docs/INVESTIGATIONS.md`.
Verified implementation checkpoint: `cc8eae30a14a01b8213d2ff719c8cfc9c21b1a48`;
507 full tests and 2 isolated restart checks passed before commit.

| Original requirement | Implementation | Code/test evidence |
|---|---|---|
| Deterministic Director: case/claims/source kinds/limits -> typed objectives | `investigation_contract`, `investigation_director`, `investigation_service.snapshot` | Strict capability schemas, independent Hypothesis authority/uncertainty properties, tax review and deterministic replay |
| Actual LangGraph plan/investigator/verifier/consistency/next/emit | `investigation_graph`; locked LangGraph 1.2.17, PostgreSQL `investigation_checkpoint` | Native checkpoint/pending-write persistence, committed-result resume and owned-container restart fingerprints |
| Seven read-only scoped capabilities; no arbitrary SQL/posting tool | `investigation_broker`, existing `EvidenceReader` READ ONLY functions | Unknown SQL/file/network/approval tool rejection, cross-tenant access, scope/lease fencing, retained M06 DML-rejection coverage |
| Precise grounded hypotheses, source facts/inference/contradictions/missing data | Typed proposals/findings; independent M06 source verification and deterministic consistency | Signed promotion support, opposing facts, forged quote/hash/offset/record, unsupported classification/unknowns, prompt injection and tax abstention |
| Strict rounds/tools/token/spend/deadline and bounded retries | Persisted `Limits`, reservation/result journal, existing provider gateway/shared quota admission | All bound-exhaustion tests, repeated-tool stop, provider failure/recovery, failed-attempt accounting, unknown remote outcome not repeated |
| Durable run/history/idempotency/concurrency/staleness | Nine scoped tables, additive 0009, append-only/state/version guards, exact outbox lease and run identity | Real concurrent different-key API requests, no duplicate snapshot, immutable histories, stale source versions, source/config basis and resume CAS checks |
| Sanitized trace in event history; selective new-evidence reruns | Step/terminal events and immutable traces; per-claim invalidations/currentness | PII projection/non-leakage, explicit tracing suppression, rerun only affected rebate while preserving unrelated damage history, oversized automatic rerun explicitly reviewed |
| Controlled failure/recovery and reproducible provenance | JSON-only source/run/config/algorithm/objective checkpoints; immutable operation outcomes | Checkpoint capacity -> review, final trace even before first tool, expired-worker rejection, process/fresh connection/container persistence |
| Optional structured LLM adapter; deterministic no-credential execution | Fixed investigation schema in existing isolated Gemini worker; deterministic/fake providers | Disabled adapter never constructs transport, default remittance payload unchanged, fixed task selection, local/shared limits and retained provider controls |

Financial safety is unchanged: hypotheses never set claim SUPPORTED/ACCEPTED/RESOLVED,
settle cash, alter invoice/receipt balances or post journals. Existing financial/API,
matching, security, migration, concurrency and restart assertions are retained. Only
minimal isolated code fixtures were added; no Argon dataset/hidden answers were used.

Final exact-state verification: **507 passed in 757.81s (458 retained + 49 new), no skips**.
All lock/dependency/Ruff/16-module strict typing/bounds/PostgreSQL migration and integrity
gates passed. Final owned-container restart: **2 passed in 16.07s**. Development up-only
0008 -> 0009 preserved every old-table fingerprint (38 tables). Exact commands, private
logs and checkpoint are recorded in STATUS.
Focused integration/recovery results and isolated restart checks are already recorded
in private local logs; the first full run exposed a remittance transport payload
compatibility regression, fixed in code without changing its existing assertion.

Remaining limitations are deferred, not resolved: G1 production authenticated roles/
RLS, reviewed publisher key custody/PKI, remote CI, real Gemini accuracy/privacy/cost,
live model reproducibility and the full Argon benchmark/ablation. Existing pilot email
offset incompatibilities remain. Both pilot ZIP digests are unchanged. No 08 financial
policy/posting, approval workflow, MCP, Redis or dataset construction is implemented.


## Milestone 06 evidence retrieval and verification - 2026-10-25

Authorized from verified `ec7b420`, branch `feat/milestone-06-evidence-verification`.
Original `prompts/06-evidence-search.md` is unchanged and remains authoritative.

| Original requirement | Implementation / contract | Verification traceability |
|---|---|---|
| Contract clauses, promotions, WMS deliveries, POD and tagged tax evidence supplied externally | Strict evidence-1.0 manifests and immutable source revisions; `evidence_contract`, `evidence_models`, `evidence_ingestion`; EVIDENCE.md | Source-family integration tests, statuses/chronology, native invoice/remittance pointers; no dataset construction |
| Typed organization/customer/case-scoped read-only allowlist, no SQL tool | Seven functions in `evidence_reader`; `evidence_api`; fresh PostgreSQL READ ONLY transaction, shared company lock and timeouts | Real PostgreSQL DML rejection, foreign company/customer/claim scope, GET-only credential querying but denied registration, unknown tool/SQL/field injection rejection |
| PostgreSQL filtering/FTS and stable source IDs/versions/offsets/excerpts | Scoped relational indexes, stored GIN vector, bound plain-text queries, immutable reviewer/native pointers | FTS positive/negative/literal SQL probes, pointer hash/version/quote tests, provenance and original payload checks |
| Verifier checks source ID/version/hash/span, owner/date/status/numeric relevance; four outcomes | `evidence_domain`, `evidence_verification`; separate scoped publisher HMAC attestations; exact integer predicates and complete bounded contradiction scan | Correct/expired/unapproved/unsigned clauses, forged spans/hashes/versions, missing signed POD, opposing WMS/POD, unknown conditions, wrong early-pay date, invoice basis/overflow, ambiguous invoice mapping and uncertain extraction |
| Immutable pointer retrieval API, no arbitrary upload SQL searching | Separate privileged reviewer GETs; tool hits contain projected excerpts/safe numeric facts only | Native CSV row/remittance assertion equality, source-file corruption and stale hypotheses, PIIs/role-spoofing/prompt-instruction containment |

Additional hardening: contiguous signed source revisions, same/different-key concurrent
replay and fork conflicts, append-only request/event provenance, transactional existing
outbox delivery/precise case invalidation, case/claim input hashes and bounded per-operation
source/original caches. Empty external contexts preserve previous hashes. No source result
sets a claim state or financial authority. All original 391 tests/assertions are retained;
only the existing restart module is extended with new-table persistence/replay assertions.

**Final verification: 458 passed in 433.09s (391 retained + 67 new), all lock/dependency/Ruff/14-module strict typing/bounds/PostgreSQL migration/integrity gates PASS; no skips. Isolated restart: 2 passed in 12.53s. Development 0007 -> 0008 preserved all old-table row fingerprints (35 tables).** Exact commands/private logs/checkpoint are recorded in STATUS.
The existing restart test fingerprints the three new evidence tables across process/fresh
connection and separately owned PostgreSQL container restart, without touching shared data.

**Trust/limits are explicit, not waived:** source_authenticated means a configured upstream
HMAC attestation, not PDF PKI, an actual legal signature, controller approval or deduction
legitimacy. Bare operator labels/statuses/LLM confidence cannot establish it. Missing keys,
conditions, evidence or complete search abstain; tax remains review-only. Full producer/key
custody, production authenticated roles/RLS/isolation (G1), remote CI, real provider/privacy
review and full Argon benchmark/ablation remain unverified. Both pilot ZIP hashes are
unchanged; hidden answers were not read. No 07 investigation/model framework, 08 financial
policy/posting or 09 approval workflow was implemented. Stop before 07.


## Milestone 05 traceability - 2026-10-25

Authorized from verified `16db2df`, branch `feat/milestone-05-case-management`.
The original `prompts/05-cases-and-events.md` remains the checklist.

| Requirement | Implementation | Code-test evidence |
|---|---|---|
| Cases, receipt/invoice links, claims/states, hypotheses placeholder, versions/events/outbox | `case_models.py`, additive `0007_cases`, `docs/CASES.md` | PostgreSQL migration up/down/up/drift, scoped FKs and immutable-write/history tests |
| Deterministic receipt/remittance lifecycle, individual claims and separate claimed/settled amounts | `case_sources.py`, `case_processing.py`, `case_lifecycle.py` | Before/after receipt, two claims, claimed sum exceeding cash, JSON field reparse, conflicting extraction revisions |
| Typed legal transitions and immutable provenance | `case_domain.py`, `case_schemas.py`, `case_service.py` | Property-based graph/paise oracles; invalid, forbidden, stale and replayed commands; database guards |
| New evidence versions/reopens, precisely invalidates and reevaluates without duplicate cash | lifecycle, immutable case-proposal overlays | Affected claim reopens; unaffected hypothesis preserved; original matching proposals retained; stale balances/originals; financial row equality |
| Background safe retry/event-ID dedupe | `case_events.py`, `case_outbox.py`, `case_worker.py` | Concurrent leases, partial-effect rollback, lease expiry/old token, bounded DEAD history, replay/backfill, restart fingerprints |
| Concurrent, tenant-scoped and authenticated metadata APIs | `case_repository.py`, `case_api.py`, locks/CAS/command keys | Real concurrent sessions same/different keys; GET-only credential; foreign sources/claims/cases; safe errors; injection non-execution |

Focused PostgreSQL/restart run: **35 passed** (`local-data/m05-final-focused-3.log`).
Final full gate: **391 passed in 229.09s**, all lint/format/lock/dependency/11-module strict typing/bounds/migration/integrity checks PASS; isolated-container restart **2 passed in 10.69s**. Development migration 0006 -> 0007 retained every old-table fingerprint. Exact commands, private logs and checkpoint are in STATUS.
All original 347 tests/assertions are retained, including G2/G3 regressions.

All normative states remain represented. Adjudication/settlement destinations require
validated capabilities from 06/08/09 and return 403 today; hypotheses are UNASSESSED,
not rule evidence. Review insufficiency/disputes/tax uncertainty are metadata only.
This enforces the original security/accounting prerequisites, without waiving future
requirements. No posting, balances, tax rule, AI investigator, Redis, MCP, frontend
or dataset work was added. G1 production auth/RBAC/isolation, remote CI, live Gemini
privacy/terms, full Argon benchmark/ablation and ten pilot email offsets remain
unresolved. Local bearer controls do not close G1. Prior pilot results/data unchanged.


## Pilot v1.1 compatibility follow-up - 2026-10-25

Targeted harness-only re-evaluation from `b7ca509`; no application/schema/security/accounting or original acceptance requirement changed. Frozen v1.0 evaluation is unchanged. `scripts/pilot_compat_runtime.py` tests declared public JSON originals and explicit UTR attestations; `pilot_compat_score.py` reads sealed targets only after application shutdown. `pilot_package.py` verifies both known roots and preserved predecessor bytes; the validator adapter normalizes one Windows path expression while preserving every assertion and original package byte.

Observed improvements: 35/35 recompressed PDFs parse with exact application canonical text; all 34 PDF citations align. Legacy pointer compatibility improves 3/47 to 37/47; ten EML pointers remain incompatible, with exact bodies but measured subject-prefix shifts of 55/56 characters. Supplemental results are separate: 25/25 deterministic JSON extractions, 48/48 API-verified spans, no unattested links, 21/21 correctly attested UTR links and 4/4 negative abstentions. No false link or financial mutation. Source-authenticity/approval is not inferred; the new sources are author-controlled extensions, not independent blind benchmark evidence.

The supplied compatibility validator fails natively on Windows due to slash representation; the explicit evaluator path adapter passes after independent manifest verification. This is not silently reported as native success. Full results/logs and verification are in STATUS and `docs/PILOT_V1_1_EVALUATION.md`. EML export, real semantic-provider/privacy accuracy, production authority/isolation and full Argon/remote CI coverage remain open; no milestone 05 work is authorized or started.
## Milestone 04C independent pilot follow-up - 2026-10-25

Approved integration/evaluation only, from `f2f71fe`; no product/schema/accounting/security requirement changed. `scripts/verify_pilot.py`, `pilot_package.py`, `pilot_runtime.py` and answer-only `pilot_score.py` exercise real HTTP APIs on disposable PostgreSQL, with allowlisted inputs and hidden answers loaded only after application shutdown. `tests/test_pilot_harness.py` adds 36 isolated boundary/scoring tests; all 301 regressions remain. Full gate **337 passed**, isolated restart **2 passed**. Commands, private logs and checkpoint: STATUS. Aggregate counts/accuracy/limitations: `docs/PILOT_EVALUATION.md`.

- Import/proposal integration now observed on the provided independent pilot: 8/8 CSV files, 91 input rows, 21 receipts, 20 cases/22 stages, 68 immutable originals; per-row duplicate/conflict probes and replay/idempotency checks pass. No false supported proposals or unexpected financial mutations. Simulated source-backed operator attestations are reported separately, never inferred from hidden truth or presented as natural intent discovery.
- Document compatibility is **partial**: 35 ASCII85 PDFs fail the published filter allowlist, 10 email canonical sidecars omit the application subject prefix, only 3/47 answer offsets transfer unchanged, prose requires semantic review, and no remittance contains an exact imported bank UTR. No files/offsets were rewritten, filter/security gates relaxed or links manufactured. Zero structured-reference recall is reported; real semantic extraction and supported correlation accuracy remain not evaluable on this package/configuration.
- G4's prior blanket absence of Argon application measurements is superseded **only for this pilot**. Full benchmark scale, independently blind evaluation, A/B/C comparisons, real provider/privacy/terms, remote CI/Linux application runs and human-review/accounting outcomes remain unverified/future. G1 authentication/strong production isolation remains deferred; G2/G3 regressions pass. No tax/case/approval/posting features were implemented, and no existing acceptance requirement was waived. STOP after 04C.

## Milestone 04B cost-control follow-up — 2026-10-25

Targeted hardening from verified 04 (`b968ccb6`, status `128a522`); no extraction redesign or financial/schema-contract changes. Original milestone requirements and deferred G1/G4 remain intact.

| Requirement | Existing evidence / missing gap filled | Traceability |
|---|---|---|
| Economical configurable real model | Existing explicit ID/rates; syntax-only check extended to exact provider metadata/capability/limits and full-request token count before generation. No guessed default or fallback. Live ID/economy/entitlement/pricing remains unverified under the no-live-call instruction. | gemini_worker; SDK MockTransport + unavailable/unsupported/limit tests |
| Deterministic first / reuse | Existing deterministic route/natural idempotency retained; validated semantic results now reused across revision/operational-limit changes, with source/semantic revalidation and immutable lineage. Failed results never reused as success. | documents.successful_cached; provider-controls cache/miss/privacy/nonmutation tests |
| Daily requests/input/output budgets | Added independent durable PostgreSQL reservations, UTC admission day, shared advisory lock and fail-closed admission; conservative 3 RPCs + max input/output per attempt, no refund on failures/retries/rollback/restart. | provider_budget, ProviderReservation, 0006; quota/boundary/rollover/rollback/concurrent-last-slot tests |
| Concurrency/rate scope | Existing local semaphore/RPM retained; PostgreSQL shared company/provider trailing-minute RPC admission added. Company serialization preserved. Not account-global or across deployments/companies. | real concurrent sessions; local Gateway regressions; DOCUMENTS configuration table |
| Usage/cost/privacy/retries | Existing sanitized metrics, nullable estimates, bounded retries/no hidden SDK retries/no escalation preserved; optional integer worst-case per-attempt cost ceiling and reservation/model/count metadata added. | domain/provider-controls/security tests; no provider diagnostic/prompt logging |
| Restart durability / offline tests | Original financial restart assertions retained and extended with immutable quota fingerprints/exhaustion after fresh API/DB connection and optional owned-container restart. All providers fake or MockTransport. | test_restart_persistence; scripts/verify_isolated_restart.py; full verify gate |

Exact executed commands, counts, logs and Git checkpoint are recorded in current STATUS. Financial CSV DATA_CONTRACT v1.0 and Argon files remain unchanged. Runtime availability checks are implemented and offline-tested, **not** a claim that a particular live model is available/economical. Provider billing/FX, remote CI/Linux execution, arbitrary real-data anonymization, production authentication/isolation and Argon benchmarks remain deferred/unverified. STOP after 04B.

## Milestone 04 follow-up — 2026-10-25

Original `04-documents-and-extraction.md` requirements/tests/real-import exit remain intact. The approved extension and AGENTS/SECURITY consistently allow a **separate** bounded Gemini transport; parser/extractor retain no DB/tools/policy/arbitrary network. Financial/security gates and Argon ownership are unchanged. See current STATUS for exact commands/logs/checkpoint and [DOCUMENTS](docs/DOCUMENTS.md) for the complete versioned contract.

| Original / approved requirement | Code / test trace | Finding |
|---|---|---|
| 04.1 local immutable bytes/hash/source/type/version/company/audit | LocalOriginals, Document/Event/Operation, 0005; digest/idempotency/concurrent upload/auth/tenant/tamper/immutable-trigger tests | Locally verified; logical immutability, not host-admin-proof WORM |
| 04.2 bounded PDF/plain email, page/spans, optional OCR | document_parse/worker/security; real PDF/email/canonical/decompression/active/encrypted/scanned/MIME tests | Verified; OCR unsupported/NEEDS_OCR, visual layout unverified |
| 04.3 strict refs/UTR/payer/claims/paise/spans/unknowns | document_contract, remittance_parser, independent semantics; money unit/prefix/sign/category/label/Unicode/span tests | Verified; consistency never authenticity/legitimacy/approval |
| 04.4 no-tool isolated extraction/offline fixture parser/optional model | Typed Transport/Gateway, isolated Gemini worker; fake provider/schema/adversarial/retry/rate/concurrency tests; actual SDK over mocked HTTP under real guard | Offline verified, SDK 2.33.0 locked; live paid/provider behavior unverified |
| 04.5 late unique verified receipt reference or candidate review | association_context/correlate; wrong/ambiguous UTR, unknown/conflicting owners, latest extraction/receipt/version/tenant tests | Verified local attestation; no customer/AR/cash/case mutation |
| Approved privacy/security additions | Projection-v1/private offsets, sanitized provider input, Google-only/no-DB/file/tool guard and authenticated document API; PII/leakage/capability/SDK/auth tests | Verified synthetic fixtures; arbitrary real-data anonymization/RCE containment not claimed |
| Original exit: real import smoke/tests/status | Live Uvicorn upload/extraction and restart/fresh read; full gate **273 passed**, separate isolated PG restart **2 passed**, 8 strict typed modules/lock/lint/format/migrations/bounds PASS | All 188 regressions retained; no skipped/weakened assertion |
| Development safety / contract / dataset | Up-only 0004→0005 with all 11 old tables' row fingerprints equal/check; unchanged financial CSV v1.0, separate document JSON | Verified; no shared reset/downgrade/restart or Argon data generation/modification/integration |

G1 remains **open/deferred**: local document bearer protection does not authenticate financial actors or supply production roles, maker-checker, hardened OS isolation or posting authority. G4 remote Actions/full Linux application execution and Argon accuracy remain **unverified**, as do live Gemini, real-data privacy and provider-terms approval. G2/G3 regressions pass. OCR and generalized financial evidence adjudication/case lifecycle are optional/future, not silently claimed implemented. No milestone 05, tax adjudication, agents/LangGraph, Redis/MCP, approvals, frontend or journal posting. STOP after 04.

## Milestone 03 follow-up — 2026-10-25

The original 00–02 audit/hardening below remains historical evidence. The user subsequently authorized milestone 03 from `52be8c9`; its implementation now fulfills the preserved original 03 checklist plus approved advanced extensions. No acceptance requirement was removed or dataset ownership changed. **188 tests pass**, including all 129 regressions; the expanded complete gate also passes lock/dependencies, Ruff format/lint, strict domain mypy, bounded numeric benchmarks and PostgreSQL migrations/integrity. Separate isolated-container restart verification: **2 passed**. See current STATUS for exact commands, local logs, measurements and checkpoint.

| Requirement | Code / acceptance trace | Finding |
|---|---|---|
| 03.1 integer bounded subset matching / filtering | `advanced_domain.subsets`, `matching.build_snapshot(advanced=True)`; `test_independent_exhaustive_oracle`, `test_integer_bigint_and_existing_partial_balances`, `test_closed_future_and_other_customer_not_in_subset_pool` | Verified; meet-in-the-middle, no new dependency |
| 03.2 all combinations up to top-K, collisions and exhaustive proof | `SearchResult`, complementary-sum enumeration; `test_exact_combinations`, `test_competing_subsets_not_arbitrarily_selected`, all limit/clock/first-solution interruption tests | Verified; truncated search never UNIQUE, even after finding one; mathematical uniqueness retains review/no intent |
| 03.3 separately instructed partials | `advanced_matching.analyze/structured_amounts`; explicit partial, strict structured-source, unsupported short-pay and instruction-mode tests | Verified; exact referenced source amounts, residual AR/cash, no inferred discount or settlement |
| 03.4 outcomes/count/time/work/size caps | `Limits`, `Settings.matching_limits`, `0004_advanced_matching`; configuration/hard-ceiling, large pool, timeout and worst-cap tests | Verified; primary outcome crosswalk documented, conservative size pruning/incompleteness explicit |
| 03.5 candidate API / persistent explanation | advanced context/trigger, existing proposal/history API; idempotent/history/non-mutation tests; embedded spans, IDs, versions, source hashes and amount JSON Pointers | Verified; allocations are JSON analysis only, top-level financial amount zero; no application/posting |
| Approved concurrency/staleness/immutability/isolation additions | `create_advanced` reuses company lock, scoped version guards/request mappings and unique snapshots; overlapping different-key sessions, stale input variants, DB immutability/duplicate constraints | Verified with actual PostgreSQL sessions; existing G3 regression unchanged |
| Migration/backward compatibility | `test_upgrade_legacy_history_roundtrip_and_mixed_algorithm_reads`, fresh up/down/up/drift regression and `test_migration_refuses_lossy_history_downgrade` | Verified; existing exact history preserved; lossy newer-outcome downgrade refused, not rewritten |
| Original worst-case-cap benchmark exit | `scripts/benchmark_matching.py` included in `scripts/verify.py`; STATUS measurement table/local JSON | Verified numeric bounded workloads only; Argon realistic benchmarks remain unverified |

Only the disposable PostgreSQL fixture lifetime changes: each test now gets its own database, preventing migration tests from consuming another test's advanced immutable history. No prior test assertions were relaxed or skipped. Data contract **v1.0 CSV schemas are unchanged**; an optional original-memo JSON convention for supplied partials is documented explicitly for Argon, not generated/integrated by Codex. No Argon/demonstration data was changed.

**Deferred findings remain open:** G1 authenticated authority/shared real-data/approval/posting and G4 remote CI/Linux application execution plus Argon dataset/accuracy benchmarks. G2/G3 remain closed and their regressions pass. Milestones 04–11 remain future work; historical references to 03 as unimplemented below describe the original audit date/task, not the current verified implementation. STOP after 03.

**2026-10-25 · milestones 00–02 audit and verification hardening.** Compared all existing prompts, AGENTS, PROJECT_SPEC, PLANS, STATUS, domain/accounting/security/tax, matching/API/data-contract and evaluation/architecture specifications with code, named tests and Git history. Original prompt text was checked at baseline `a545b42`, not inferred from rewritten prompts. The authorized hardening follow-up closes G2/G3 below; G1/G4 remain deferred/unresolved.

Application baseline: `8ff6687` (same code as documentation checkpoint `0772dfd`). The original documentation audit is `6e1ad2d`, status checkpoint `58a9f8f`. Its follow-up branch is `test/milestone-01-02-hardening`. Application behavior/schema/dependencies are unchanged; the follow-up adds verification infrastructure and tests, not milestone 03 functionality or datasets.

Migration numbering is separate from milestone numbering: 0001_foundation belongs to 00, 0002_data_engine to 01, and 0003_exact_matching to 02. The existing 0003 migration is not evidence of advanced-matching implementation.

## Observed verification and checkpoints

| Milestone | Git checkpoint | Recorded verification |
|---|---|---|
| 00 | `a545b428996f33816c0aebc60e6841dd89a72554` | 41 tests; PostgreSQL migrations, health/ready, lint/format; later Docker verification recorded in STATUS |
| 01 | `92b21c729e18859f173e88f473caaeaba72a017d`; status `9dccb7a` | 83 tests; import/isolation/concurrency/integrity, migrations, Docker restart probe, lint/dependencies |
| 02 | `8ff66873e866db025317d40a12588c4918bb2a4c`; status `0772dfd` | 126 tests; immutable exact proposals, stale state, concurrency, strict domain types and complete verification |

Original audit execution: `uv run --frozen python scripts/verify.py` (workspace executable `./.venv/Scripts/uv.exe`): **126 passed, 1 existing upstream warning in 24.96s**; local log `local-data/verification/20261024T205239565998Z.log`. Hardening verification now passes **129 tests, 1 existing warning in 29.27s**, with lock/dependency, Ruff lint/format, strict mypy, PostgreSQL migration/integrity and live API checks. Separate isolated-container restart verification passes **2 tests in 7.51s**. No tests were skipped or weakened. Full logs are local; GitHub Actions has not run remotely.

## Original requirement → implementation/test traceability

“Verified” below means the stated **local synthetic-test scope**, not production authentication, real tax compliance or Argon benchmark accuracy.

| ID / original requirement | Code and test evidence | Finding |
|---|---|---|
| 00.1 Python 3.12, FastAPI, reproducible install | `pyproject.toml`, `.python-version`, `uv.lock`; `scripts/verify.py` lock/dependency checks; STATUS install commands | Implemented/verified |
| 00.2 PostgreSQL Compose, health check, secret-free example | `compose.yaml`, `.env.example`, `.gitignore`; recorded Docker startup/health and `scripts/verify_docker.py` | Implemented; runtime observed historically, not restarted for this audit |
| 00.3 Minimal org/customer schema, reversible Alembic | `0001_foundation.py`, `models.py`; `test_migration_roundtrip_and_persistence`, `test_cli_migration_and_live_server` | Implemented/verified; later migrations are additive, not premature milestone 00 tables |
| 00.4 Liveness and DB readiness | `main.create_app`; `test_health_does_not_connect_to_database`, `test_ready_failure_is_503_and_redacted`, PostgreSQL/live smoke | Implemented/verified, including failure/redaction |
| 00.5 Signed/zero paise conversion, HALF_UP rates, float rejection | `money.py`; `test_conversion`, `test_rate_rounding`, float/bool/nonfinite tests, roundtrip/identity Hypothesis properties | Implemented/verified, including 1.005→101 and negative boundaries |
| 00.6–7 pytest/Ruff and documented local commands | `tests/`, `README.md`, `scripts/verify.py`, STATUS | Implemented/verified; strict financial-domain typing was an approved milestone 02 addition |
| 01.1 Scoped customers/aliases/invoices/bank/receipts/import/audit, paise/INR/versions | `models.py`, `0002_data_engine...py`; `test_valid_imports_provenance_and_scoped_reads`, `test_database_guards` | Implemented/verified for exposed operations; real authorization is G1 below |
| 01.2 Strict typed CSV, errors, atomic rejection, digests/run metadata | `data_contract.py`, `imports.parse_csv/ingest`, DATA_CONTRACT; structure/money/date/currency/limits tests and `test_atomic_errors_and_unknown_customer` | Implemented/verified; whole-file rejection is the permitted atomic policy |
| 01.3 Idempotent bank/receipt registration, renamed duplicates/concurrency | `imports.register_row/ingest`, bank source/receipt uniqueness and composite FKs; duplicate, renamed/conflict, concurrent receipt and same-key tests | Implemented/verified; no GL recognition exists, intentionally reserved for 08 |
| 01.4 Original dataset generator/demo seed/repeated seed | Approved Argon responsibility change; current prompt §4 is DATA_CONTRACT instead; fixture remains unchanged | Explicitly superseded, not an application defect; external dataset use unverified |
| 01.5 Read/query/import APIs, no later financial actions | `api.py`, `views.py`, `cli.py`; scoped-read/transport/provisioning tests | Implemented/verified; read APIs plus CSV POST imports satisfy the later explicit read-only API scope; standalone JSON CRUD was not required |
| 01.6 Creation/duplicate audit, actor/time/source digest | `imports.event`, SourceImport/AuditEvent and immutable triggers; provenance, duplicate and DB-guard tests | Implemented/verified as local provenance; actor label is not authentication (G1) |
| 01 tests: balances, tenant FKs, invalid rows, duplicates, restart survival | Named tests above; `test_financial_import_survives_process_restart_and_fresh_connection` with separate Uvicorn PIDs/fresh DB engines; also run through `verify_isolated_restart.py` | **G2 closed:** all financial/provenance/audit columns and bytes survive real app/isolated PostgreSQL restart; replay creates no duplicate money |
| 02.1 Verified mapping/alias/reference resolution and candidate basis | `matching.bank_valid/source_valid/evidence_valid/build_snapshot/register_evidence`; known/unknown/manual/direct reference, wrong-owner/source/span/digest tests | Local record consistency/attestation implemented/verified; external identity/authority not established (G1) |
| 02.2 Pure integer exact matching, explicit ambiguity/unresolved | `matching_domain.decide`; pure decision/Hypothesis tests; same-amount/closed/future/unequal/conflicting-reference API tests | Implemented/verified; explicit invoice intent is a documented conservative restriction, not permission to infer settlement from amount |
| 02.3 Preserve partial/open/unapplied balances, immutable/versioned proposals | `MatchingEvidence/Proposal/Request`, `0003_exact_matching...py`; `test_exact_immutable_idempotent_and_financially_nonmutating`, partial-balance, DB NULL/version/immutability tests | Implemented/verified; no allocation/posting/balance mutations |
| 02.4 Trigger/read APIs, idempotence, stale state, strict isolation | Existing tests plus `test_different_keys_contend_and_reuse_one_immutable_snapshot` | **G3 closed:** two observed overlapping PostgreSQL sessions with different keys reuse one snapshot/proposal; audit and balances preserved |
| Approved 02 quality additions: complete verification, CI config, practical types | `scripts/verify.py`, `.github/workflows/verify.yml`, strict mypy config | Local checks passed; remote Linux/Actions execution remains unverified (G4) |

## Gaps, blockers and required disposition

| ID | Gap / evidence | Current disposition |
|---|---|---|
| G1 | Normative authenticated actor/role authority is absent. X-Actor-ID and imported verified_by are asserted strings; source/hash consistency does not authenticate a verifier. MATCHING/DATA_CONTRACT disclose this. | **Deferred, not resolved. Blocker for trusted real-data/shared use or approval/posting.** Users/roles/maker-checker remain scheduled for 09; authorization is still mandatory before posting is enabled. |
| G2 | Original proof used only an organization restart probe. | **Verified/closed by hardening:** real API process stop/start, fresh PostgreSQL connections, all customer/invoice/bank/receipt/source/audit columns, original bytes/digests/IDs/timestamps, exact-key and renamed/new-key retries, plus a real separately owned PostgreSQL restart. Shared development container was neither restarted nor destroyed. |
| G3 | Original proposal concurrency test used the same key in both threads. | **Verified/closed by hardening:** barrier-synchronized different-key sessions, different backend PIDs, actual advisory-lock waits observed in pg_stat_activity, READ COMMITTED isolation, one proposal/snapshot and one creation event with two request mappings, unchanged finance/provenance and immutable existing history/DB uniqueness. |
| G4 | GitHub Actions is configured; remote execution and Linux runtime are unobserved. No Argon dataset or benchmark was imported/evaluated. | **Deferred/unverified, not resolved.** Isolated local Linux PostgreSQL is exercised; the full remote Linux/Actions job is not. No automatic push or Argon data generation/import/evaluation occurred. |

G2/G3 are closed by explicit acceptance evidence, not simply a larger test count. No application defect was exposed; the restart fixture needed dead-connection reconnection and the disposable Docker harness needed a stable published port. **Do not advance automatically.** G1/G4 and all production/posting restrictions remain binding; this hardening task stops before milestone 03.

## G2/G3 hardening evidence (2026-10-25)

Verified hardening checkpoint: **`71059c5098d30eb4d7ad4baca47d259a61dbf383`** on `test/milestone-01-02-hardening`. This documentation-only follow-up records its hash; no application changes followed verification.

- `tests/test_restart_persistence.py`: imports through a real Uvicorn process, terminates that process and disposes its verifier pool, reads through a new engine/backend connection and a second Uvicorn PID. Compares every persisted financial/source/audit column and original bytes/digests, then retries the same import keys and a renamed bank file with a new key. No duplicate customer/invoice/bank/receipt is created; original audit records remain identical, with only expected replay/duplicate events appended.
- `tests/test_matching_concurrency.py`: holds the real company lock until two distinct sessions are both observed waiting on it, then releases them. Both different-key requests successfully return the same immutable proposal (documented serialized equivalent semantics), with one audit creation event, two key mappings and no financial mutation. Subsequent retries preserve all records; direct duplicate-snapshot insertion and history updates are rejected by DB constraints/triggers.
- `tests/conftest.py`: `pool_pre_ping=True` reconnects the administrative fixture pool for cleanup after a real PostgreSQL restart. Existing assertions and failure behavior remain intact.
- `scripts/verify_isolated_restart.py`: uses the cached PostgreSQL 16.15 image, a fresh UUID-labelled container/named volume, random throwaway credentials and an explicitly chosen free loopback port. Only owned resources can be restarted/removed. A negative test refuses the shared container name before any Docker call. The shared container's ID, start time and restart count were unchanged; owned-container/volume listings were empty after cleanup.
- Initial isolated runs failed on a stale admin connection and Docker reassigning an empty host-port binding (52249→52262). Both harness issues were corrected, not skipped or asserted away. Application code, migrations, dependencies and matching behavior needed no changes.
- Commands: `uv run --frozen python scripts/verify.py` → **129 passed**, complete required checks PASS; `uv run --frozen python scripts/verify_isolated_restart.py` → **2 passed**, including real PostgreSQL restart. Logs: `local-data/verification/20261024T211312489837Z.log` and `local-data/verification/isolated-restart-20261024T211220500927Z.log` (UTC names). Original focused check: **2 passed in 6.05s**, `local-data/hardening-focused.log`.

## Contradictions, scope changes and alignment performed

- **Approved:** M01 generator/demo seeding and repeat-seed deliverables moved to Argon; Codex retains schemas/importers/application code/minimal isolated fixtures. The existing demo reference was not modified. Evaluation quality/coverage was never waived.
- **Unintended specification regression, corrected:** the M01 rewrite of `docs/EVALUATION.md` dropped original numerical targets from `a545b42`. Restored them as Argon-owned targets: 50 customers, ~2000 invoices, ~500 receipts, ≥250 situations (original developer-size allowance retained), ≥100 documents, ≥30 attack/abuse scenarios, train/dev/test isolation and held-out combinations. No dataset was constructed and no target is claimed met.
- **Approved additions, not scope creep:** M02 persistence, concurrency/staleness, explicit evidence APIs, reusable verification, CI and financial-domain typing were requested. CSV source integrity supports matching; no milestone 04 document/extraction system or milestone 06 general evidence tooling was implemented early. No later product functionality was found.
- **Prompt names/checklists:** original 02 prompt remains required alongside its expanded 02 prompt. The requested 03-advanced-matching filename was missing; added a documentation-only extension that retains every original 03 numbered item, test and worst-case benchmark gate. New outcomes map old semantics: UNIQUE_WITH_EVIDENCE is an evidence-qualified UNIQUE, MULTIPLE_CANDIDATES→AMBIGUOUS, NO_MATCH→UNRESOLVED, BUDGET_EXCEEDED→SEARCH_INCOMPLETE. Mathematical uniqueness alone never supplies intent/authority; incomplete search cannot prove uniqueness.
- **Sequencing tension preserved, not waived:** 08 requires gated posting/approvals while 09 provides the full role/review workflow. PLANS now explicitly requires the authorization gate **before** posting is enabled; no permissionless interim posting or architecture reorder is authorized.
- **Documentation-only divergence:** branching from the requested `8ff6687` excludes status-only commit `0772dfd`; code is identical. STATUS now records the known feature hash directly. No history was lost/reset and neither branch was overwritten.

## Intentionally future / not missing milestone 00–02 features

03: bounded multi-invoice/subset and explicitly instructed partial search, top-K/exhaustiveness, configurable count/size/work/time limits and worst-case-cap benchmark. 04: immutable documents and isolated extraction. 05: cases/claims/events/outbox as needed. 06: generalized read-only evidence retrieval/validator. 07: bounded deterministic Director/optional investigator. 08: conditional tax review and balanced idempotent authorized accounting simulator. 09: user roles/maker-checker/recovery drafts. 10: real API-backed UI/E2E. 11: three-arm evaluation against Argon's frozen ground truth. All original future tests/exit gates remain required; no dataset ownership change waives them. No live tax compliance is claimed.

The original audit changed specifications/status only. This separately authorized hardening adds tests/support infrastructure without changing application architecture/schema/financial behavior. G2/G3 are now evidenced; deferred findings are not silently marked complete. Stop after hardening; milestone 03 remains unimplemented.
