# Build status

- Repo state: **Pilot v1.1 compatibility re-evaluation verified; frozen v1.0 baseline preserved. G2/G3 remain closed; production authentication/isolation, remote CI and full Argon benchmark remain deferred/unverified (G1/G4).**
- Current task: **Pilot v1.1 re-evaluation complete; STOP before milestone 05.**
- Verified checks: **347 full tests passed; lock/dependencies/lint/format/9 strict typed modules/bounds/PostgreSQL migrations/integrity PASS. Isolated restart: 2 passed. v1.1: 35/35 PDFs parse with exact canonical text, 25/25 deterministic supplemental extractions, 21/21 attested UTR links, 4/4 negative abstentions, zero financial mutation/false links. Ten EML offsets remain incompatible. Development data untouched.**
- External integrations: **Optional Gemini adapter implemented, disabled by default; no live/paid Gemini call performed.**
- Open decisions: Ten EML offsets and native Windows compatibility-validator path handling remain unresolved upstream; free-form semantic extraction/live provider/privacy/terms, OCR, production auth/isolation, remote CI and full benchmark remain unverified. Tax adjudication stays in later approved milestones.

## Pilot v1.1 compatibility re-evaluation - 2026-10-25

Resumed on `test/pilot-v1-1-compatibility` from verified `b7ca509`. Resume inspection found a clean tree: interruption had stopped after branch/package inspection; no v1.1 code/tests/application runs existed. Continued the existing harness rather than replacing completed functionality. Original `docs/PILOT_EVALUATION.md`, source ZIP and baseline observations are unchanged. New aggregate comparison: `docs/PILOT_V1_1_EVALUATION.md`. No application modules, parser filters, CSV contract, schema, dependency, financial behavior, dataset construction or later milestone changed.

Changed harness: recognized both known archive roots with existing strict manifest/path/resource checks; separately allowlisted public supplemental JSON; added pinned compatibility validator with explicit Windows path-only adapter; uniform deterministic source/span/correlation/attestation/version/idempotency probes in `pilot_compat_runtime.py`; evaluator-only target and actual-email-text diagnostics in `pilot_compat_score.py`; predecessor preservation comparison. No hidden targets/source-sidecars are passed to APIs/models, no attestations derived from sealed answers, and no financial matches inferred from JSON UTR association.

Successor ZIP SHA-256 `26594c6f3ae11916f16aed1577d418e255e18d1e56a9c0ed84361dc85b841f13`: 271 files/270 manifest entries/506582 bytes verified. Predecessor `438fbedcce8016fa0aaead3910876b8fb9e2b6f1dd41406db8c0ec5829855927` unchanged. Eight CSVs, 68 canonical sidecars, two inventories, original business expectations and citation offsets identical; exactly 35 PDFs changed bytes. The package and extracted evaluator copy remain unmodified. No generator or upgrade script was run.

Original pinned validator PASS. Additional supplied validator FAILS natively on Windows (`str(relative_path)` backslashes vs slash manifest keys), before DB creation on the first attempt. Independent on-disk coverage/hash verification passes; a separately logged evaluator copy changes only that expression to `.as_posix()`, preserving all assertions. Adapter PASS: 35 filter/canonical PDFs, 21 positive JSONs, four negatives, 25 invoice references, 34 updated PDF citation hashes. Both native failure and adapter success are recorded, never silently conflated; packaged executable unchanged. This is a portability discrepancy, not a waived security/integrity check.

Actual disposable PostgreSQL/HTTP run `58f8acde007249dba9975741b793c50f`: dev 21/21 and eval 14/14 PDFs READY/canonical-equal. Legacy 68/68 sources READY; canonical equality improves baseline 23/68 to 58/68. All 47 source citation hashes match successor originals; direct pointer compatibility improves 3/47 to 37/47 (34/34 PDF, 3/3 TXT, 0/10 EML). Every EML body uniquely and exactly matches its old sidecar inside actual API canonical text. Measured prefixes/quote deltas: 55 characters for four dev emails, 56 for six eval; actual byte offsets measured independently. No pointers rewritten, guessed, relabeled or submitted as corrected evidence. The ten email offsets remain open.

Supplemental sources scored separately from legacy corpus: dev 13/13, eval 12/12 deterministic SUCCEEDED; 48/48 returned spans verified by API. Without operator attestations: 21 CANDIDATES, four UNRESOLVED, zero LINKED. Explicitly simulated attestations of extracted UTR literals plus current expected receipt versions: 21/21 correct links; four negative controls remain UNRESOLVED. Wrong source attestation rejects 25/25 (422); missing expected version 21/21 and stale expected version 21/21 reject (409); 50 same-/fresh-key correlation replays equal. No wrong-owner scenario was added; existing owner/tenant/conflict regressions remain. UTR link is only a source association, never payment intent, identity/claim approval or settlement.

All financial CSV imports/replays/conflicts, exact/advanced matching, auth/tenant and non-mutation probes retained. Original 91 financial input rows/21 receipts and every customer/alias/invoice/bank/receipt balance/status/version unchanged after all document operations. External models disabled; zero provider attempts/reservations/transmissions or recognized-identifier projection failures. Sources are untrusted and review-required, not externally authenticated. New JSONs are author-controlled extensions informed by prior truth, not a prospective blind/Gemini accuracy benchmark.

Executed commands/results:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_pilot_harness.py tests/test_pilot_compatibility.py -q --basetemp=local-data/pilot-v11-unit-temp
# Final targeted run: 46 passed in 1.00s (36 existing + 10 new compatibility cases).
./.venv/Scripts/uv.exe run --frozen python scripts/verify_pilot.py --archive local-data/pilot/clearledger_pilot_v1_1_compat.zip
# First attempt stopped at native validator portability error before DB creation.
# Second: logged adapter PASS, disposable application integration/safety PASS.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# 347 passed in 128.48s; all lock/dependency/lint/format/type/bounds/migration/integrity gates PASS.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# 2 passed in 8.62s; only owned labelled test container/volume restarted and removed.
```

Preserved completed application observations and reused them for final evaluator-only `evaluate`, `evaluate_compat`, `compare_successor` and immutable-package checks, rather than repeating the expensive API run after adding diagnostics. New private outputs `summary-verified.json` and `evaluator/details-verified.json` contain those final measurements; original observations/summary remain intact. The full verification gate ran after code/test completion. All 337 regressions retained plus ten new tests; one existing Starlette/HTTPX deprecation warning, no skips or weakened assertions.

Ignored logs: `local-data/pilot/v11-integration-1.log`, `v11-integration-2.log`; `local-data/pilot-runs/58f8acde007249dba9975741b793c50f/` (native/adapter validator logs, original API outputs, evaluator-only results); `local-data/verification/20261025T031638842859Z.log`; `local-data/verification/isolated-restart-20261025T031637899348Z.log`. Standalone application timing: dev 799 requests/43.554s/p95 427.967ms; eval 683/36.360s/p95 428.092ms. Evaluator Python-traced peak 23009259 bytes; API/parser/DB RSS and system CPU not measured. More requests than v1.0, so no speedup comparison is claimed.

Final read-only check confirms development head still `0006_provider_budgets`, zero remaining `clearledger_pilot_*` databases, and both ZIP hashes unchanged. The original v1.0 report, DOCUMENTS/DATA_CONTRACT specifications, product source and lockfile have no diff.

Remaining limitations: native Windows validator portability, ten email citation offsets, original prose requiring semantic extraction, no live model/privacy/provider-terms verification, no production auth/isolation or full blind/large Argon evaluation. No tax adjudication, cases, agents, Redis/MCP, approvals, frontend or journals. STOP before milestone 05.

## Milestone 04C - independent pilot integration and evaluation - 2026-10-25

Verified integration checkpoint: **`2b9dda04a4b9dc3ee14f210a0c916d26296bcd93`**, message `test: integrate independent pilot evaluation`. All required gates passed before commit. Reviewed/staged exactly 10 intended files; whitespace, local-secret and raw/hidden-data exclusion checks passed. No product changes followed verification. This documentation-only follow-up records the hash; no push.

Branch `feat/milestone-04c-pilot-evaluation` starts at verified status `f2f71fe`. Integration/evaluation only: no application modules, schema, dependency, accounting behavior or CSV contract changed. Original independent ZIP is unchanged; no generator was run or dataset constructed/modified. Full aggregate report, definitions, scenario-family outcomes and reproduction: `docs/PILOT_EVALUATION.md`. Audit/plan updated without waiving original requirements or marking milestone 11 complete.

New harness files: `scripts/pilot_package.py` (bounded path/manifest/hash checks and explicit app-input allowlist); `scripts/pilot_runtime.py` (real loopback HTTP services, disposable PostgreSQL, imports/replays/negative probes, exact/advanced matching, source-backed simulated attestations, originals/parsing/extraction/span/correlation/auth/tenant/privacy checks); `scripts/pilot_score.py` (answer-only, independent brute-force subset oracle); `scripts/verify_pilot.py` (validator pin, separate input/storage/evaluation paths, cleanup/private results). Only organization provisioning uses direct application writes; all financial data/evidence/documents use APIs. Scoring loads hidden answers after both API processes stop and disposable databases are removed. Runtime receives no hidden/sidecar values. This is dataflow isolation, not a stronger host/OS security claim.

Package SHA-256 `438fbedcce8016fa0aaead3910876b8fb9e2b6f1dd41406db8c0ec5829855927`; CRC/exact coverage and all 237 manifest-listed digests pass (238 files, 458956 expanded bytes). Independently executed reviewed validator passes 20 cases/22 stages/68 sources/47 pointers/73 events. Fixed-seed comparison is NOT TESTED (no generator/compare run); internal expected-journal checks are not application posting evidence. API/development schema inspected first; both test databases migrate/check to 0006. Final read-only check: development head still 0006, no `clearledger_pilot_*` databases remain.

Measured financial results: dev 11 customers/11 aliases/19 invoices/11 bank rows+receipts; eval 9/9/11/10+10. All 8 CSV files and 91 rows import successfully. Sixteen file replays, 21 duplicate-row probes, 21 +1-paise natural-key conflicts and 8 extra-header requests preserve financial records. Evaluator confirms the visible-input probes cover the supplied hidden negative fixture without exposing it to runtime. Exact/advanced proposal attempts run in unattested and separately labeled simulated-attested modes (84 primary evaluations/168 matching replays). Alias-owner-supported literal memo attestations: 12 dev/10 eval; never generated from hidden allocations or presented as naturally verified intent.

Unattested exact recall 0/3 dev and 0/3 eval is expected without verified intent; no supported claims are made. Independent exhaustive subset oracle: 11/11 dev, 10/10 eval. Multi-invoice candidate recall: 4/4 dev, 2/2 eval. Candidate-plus-partial-analysis expected-cash coverage: 10/10 dev, 9/9 eval; ambiguity and unknown duplicate-payer abstentions correct. Simulated-attested exact recall 3/3 each; advanced cash candidates 10/10 dev, 8/9 eval (remaining target stays partial analysis, missing memo intent). Zero wrong supported outputs among 23 conditional supported proposals. Zero customer/alias/invoice/bank/receipt balance/status/version mutations. These are proposal mechanics, not accounting settlements or proven real-world precision.

Document gaps retained: all 68 originals/hash checks persist; 33 parse READY, 35 PDFs return controlled UNSUPPORTED_PDF_FILTER because they use ASCII85+Flate outside the published allowlist. Ten EML sidecars omit the application's subject prefix. Only 3/47 hidden offsets transfer unchanged (47/47 original hashes match); canonical equality 23/68. All 68 baseline extraction runs require review: prose is outside deterministic grammar, real provider remains disabled, invoice-reference recall 0/23. Twenty remittances lack exact bank UTR literals: all correlation attempts UNRESOLVED, no eligible UTR target or supported correlation accuracy. No filter gates relaxed, spans rebased, mock accuracy substituted or source text promoted to authority. These compatibility gaps block a complete end-to-end document benchmark, not the completion of this diagnostic integration task.

Privacy/security: 33 readable-source probes, 24 project safely and 9 abstain; zero independently recognized PAN/GSTIN/IFSC/email markers survive projection. Unparsed PDFs are not counted as anonymization-tested. Explicit opt-in requests still yield 33 BLOCKED / 35 no-text review outcomes, zero attempts/reservations/transmissions. All envelopes retain human review/no authority. Injection never causes tools/approval/writeoff/posting. Four foreign-scope 404 checks and one auth 401 per split pass. Production auth/isolation and real-provider/real-data privacy remain G1/G4 limitations.

Executed commands/results:

```powershell
./.venv/Scripts/python.exe -I -B local-data/pilot/inspection/clearledger_pilot_v1/validation/validate.py --root local-data/pilot/inspection/clearledger_pilot_v1
# Independent validator PASS; reproduction NOT_TESTED_NO_COMPARE_PATH.
./.venv/Scripts/python.exe -m pytest tests/test_pilot_harness.py -q --basetemp=local-data/pilot-unit-temp
# 36 passed in 0.86s; only minimal isolated fixtures.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_pilot.py
# Integration/safety assertions PASS; measured document failures preserved in report.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# 337 passed in 134.92s; lock/deps/Ruff lint+format/9 strict typed modules/bounds/migrations/integrity PASS.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# 2 passed in 8.72s; only owned disposable container restarted/removed.
```

Both full/restart runs retain one existing Starlette/HTTPX deprecation warning; no skipped/weakened regressions. Local ignored logs: `local-data/pilot/independent-validation.log`, `local-data/pilot/verified-integration.log`, `local-data/verification/20261025T013247119424Z.log`, `local-data/verification/isolated-restart-20261025T012516905321Z.log`. Final detailed pilot run: `local-data/pilot-runs/909833d8bc0e41e499b893692adae225/` (summary, actual responses, evaluator-only per-scenario comparisons); none committed. Earlier private failed attempts corrected harness assumptions about controlled PDF rejection and primary/additional truth keys, without modifying product behavior. A later scorer regression fixes order-independent combination comparison and protects unmapped-receipt denominators. Final review added Windows reserved-device/trailing-dot/space path rejection and eight regression cases; the final gate passes 337 tests. Final strict-boundary pilot recheck `684fa94997e14a8f829e502de6c1259a` has identical outcome aggregates to the standalone measured run (its timings are not substituted for the standalone performance figures).

Standalone pilot timing: dev 600 timed API calls / 33.855s / p95 424.722ms; eval 507 / 27.577s / p95 426.404ms. Evaluator peak Python-traced memory 21257781 bytes; API/parser/PostgreSQL RSS and system CPU/peak not measured. Dataset-specific compatibility work should be a separately versioned Argon successor; no dataset changes are authorized by this task. Full-size/blind/A-B-C evaluation, remote CI/Linux, live Gemini/privacy/terms, tax/claims/case lifecycle, approvals/journals and human-review metrics remain deferred/not implemented. STOP after 04C.

## Milestone 04B - Gemini cost-control/configuration audit - 2026-10-25

Verified implementation checkpoint: **`fe60caac8c905bff67c43a6dbede3a2952e0a87e`**, message `fix: harden milestone 04 Gemini cost controls`. Reviewed exactly 20 intended files; staged whitespace and local-secret/runtime/dataset exclusions passed. All required checks passed before commit; no application changes followed verification. This documentation-only follow-up records the hash. No push.

Branch `feat/milestone-04b-gemini-controls` starts at verified M04 status `128a522` (implementation `b968ccb6`). Targeted hardening preserves deterministic parsing, privacy projection, isolation, strict semantic validation, all financial invariants and all 273 regression tests. No later milestone, financial CSV contract, accounting behavior, dependency or Argon data changed. Configuration/traceability: `docs/DOCUMENTS.md`, `docs/SECURITY.md`, `REQUIREMENTS_AUDIT.md`.

Audit findings and implemented changes:

- Existing model syntax check extended to exact configured-ID `models.get` validation, generation capability/limits and full system/schema/content token preflight before generation. Actual SDK MockTransport tests compare counting/generation payloads under the actual worker guard. No guessed default ID, hidden retry, tools or fallback/escalation.
- New append-only `ProviderReservation` / additive `0006_provider_budgets`: independent committed PostgreSQL admission under a company/provider lock. Each attempt reserves 3 RPCs and maximum input/output tokens; failures/retries/rollback/restarts never refund. Daily UTC admission defaults: 30 RPCs/100000 input/30000 output. Per-attempt defaults: 8192/4096 tokens. Shared trailing-minute admission: 30 RPCs. Zero shared/daily caps disable new attempts. Optional integer-paise per-attempt worst-case cost ceiling requires both reviewed rates. Workers receive no DB capability.
- Shared limits cover cooperating instances in one database/company/provider, not Google account-global use or other deployments/companies/manual calls. Deploy consistent configuration across instances. Existing company serialization remains; Gateway concurrency 1 and 10 attempts/minute remain process-local. These are conservative admission caps, not billing guarantees or actual-wire-time quotas; pending calls can finish later.
- Existing natural-input reuse retained. Validated nonempty semantic successes (including review-required facts without error) now reuse across revision/operational-setting changes. Source/parser/schema/privacy/model/review/output-cap identity must match. Current privacy/external gates, original integrity and source semantics rechecked; new immutable run/event records source extraction ID and zero incremental attempts/tokens/cost. Failed/invalid/blocked outputs never become successful cache entries. No tenant/document crossing.
- Existing sanitized usage/latency/nullable estimated costs and bounded retries retained; added reservation IDs/amounts, model version/limits and preflight count. No prompt/key/private map/exception-body logging. Retry usage remains incomplete/unknown. Rates/FX are operator estimates, not provider billing facts.

Actual commands/results (no live API or paid calls):

```powershell
# TEST_DATABASE_URL loaded privately from ignored .env for the focused run.
./.venv/Scripts/python.exe -m pytest tests/test_provider_controls.py tests/test_document_domain.py tests/test_document_security.py -q --require-postgres
# 80 passed, 1 existing Starlette/HTTPX warning, 26.08s; before final 3 cache-identity cases.
./.venv/Scripts/uv.exe run --frozen python local-data/m04b_upgrade.py
# 0005_documents -> 0006_provider_budgets; drift check PASS; 16 old table row fingerprints equal.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# Lock/dependencies/Ruff lint+format/9 strict typed modules/matching bounds PASS.
# 301 passed, 1 existing Starlette/HTTPX warning, 130.15s; no skips/failures.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# 2 passed, same warning, 8.64s; owned isolated PostgreSQL restart/cleanup PASS.
```

28 new tests cover budget exhaustion/boundaries, real concurrent sessions contending for the final allowance, company isolation, rolling-minute/day rollover, optional cost ceiling, independent rollback durability, fresh API/connection restart, immutable reservation triggers, cache reuse/misses/failed outputs, deterministic bypass, retry reservations, controlled failures/privacy and preflight failure without generation/escalation. Original financial restart assertions remain and now additionally verify quota fingerprints/exhaustion after real owned-container restart. No failing assertion was weakened/skipped. Initial new test policy omitted required DATABASE_URL; corrected to an explicit unused test-only URL. Offline SDK test exposed nonempty counting contents/system-role serialization requirements; fixed with exact payload equality retained.

Ignored logs: `local-data/m04b-focused.log`; `local-data/m04b-development-upgrade.log`, `local-data/m04b-development-schema.json`; `local-data/verification/20261025T003335349764Z.log`; `local-data/verification/isolated-restart-20261025T003518553151Z.log`. All destructive migration checks use UUID disposable databases. Restart touched only owned labelled test resources, cleaned afterward. No shared development/portable database reset/downgrade/restart.

Remaining limitations: **No live model ID/availability/economy, entitlement/counting interoperability/pricing or paid smoke call verified**, as explicitly prohibited. Exact availability checking occurs only on a future separately authorized uncached attempt; operator must select/review the economical model/rates. Conservative reservations can exhaust budgets before actual usage; no refunds, account-global enforcement or billing reconciliation. Existing production authentication/roles/OS isolation (G1), real-data privacy/provider-terms approval, remote CI/full Linux application execution and Argon accuracy (G4) remain deferred/unverified. External AI remains disabled by default. STOP after 04B.

## Milestone 04 — secure document intelligence · 2026-10-25

Verified implementation checkpoint: **`b968ccb6d0af6e192a5a665f021469c7477a7e2e`**, message `feat: implement milestone 04 secure document intelligence`. Reviewed/staged exactly 35 intended files after all required checks passed; staged whitespace, actual local-secret exclusions and uploaded-data/runtime exclusions passed. No unrelated changes or push. This documentation-only follow-up records the hash; no application changes followed final verification.

Branch `feat/milestone-04-document-intelligence` starts at latest verified status checkpoint `0dfaa91` (application `e28c359`), preserving history. The original 04 checklist/tests/real-import exit remain intact. AGENTS/original prompt/security/architecture now explicitly record the user's approved **separate Gemini transport exception**, while parser/extractor has no network/DB/tools/policy. No financial/security requirement was waived. Complete API/format/privacy contracts: `docs/DOCUMENTS.md`; requirement traceability: `REQUIREMENTS_AUDIT.md`.

Implemented authenticated, tenant-scoped PDF/email/text/remittance-JSON ingestion; strict types/MIME/path/size/page/decompression/resource guards; exclusive content-addressed/fsynced originals with SHA-256; canonical pages/hash/parser version; immutable metadata, deduplication, operation keys and audit events. Scans/mixed empty pages require OCR; malformed/unsupported data fails closed. Repeated/concurrent uploads produce one document/event. An actual HTTP import/extraction and separate API process restart/fresh read preserve metadata/originals.

Deterministic exact JSON/line formats run first; semantic extraction is optional. `remittance-extraction-1.0` contains source-backed invoice/UTR/payer refs, generic claimed categories/reason codes, nullable strict integer-paise amounts, spans and uncertainty/unparsed fields. Independent checks enforce page/quote/range/identifier labels/boundaries, claim/category/amount/reason containment, currency units, money boundaries, Unicode and schema validity. Every envelope marks authenticity unverified, financial authority false, layout unverified and human review required. Schema success never legitimizes a claim or authorizes settlement.

Official **google-genai 2.33.0**, **pypdf 6.21.2** installed/locked. Provider/model/key configurable; key is private configuration/stdin, never model text/frontend/command line. External calls require server/provider/key/model/privacy-review configuration, explicit request opt-in **and** approved-synthetic upload attestation; defaults remain off. No Gemini key/live model/paid call was used. Tests exercise fake providers, mocked SDK configuration and the **real SDK over MockTransport under the actual worker guard**, without external HTTP.

Privacy-v1 combines PAN/GSTIN/IFSC/accounts/contact/phone/email/URL detection with an allowlisted financial projection masking unknown words/numbers/symbols. Essential labeled refs/amounts remain; sensitive overlap and unsupported/truncated money fail closed. Reversible offsets/mapping stay private in memory; originals/maps are never sent/logged. Model spans are validated against its exact projection, restored by offsets, then checked against original canonical text. This does not prove arbitrary real data anonymous: unusual formats/ambiguous identifiers may require review. Only approved synthetic external use is supported.

Parser/transport subprocesses inherit no DB credentials/session or policy API. Parser denies network; transport permits only Google host/public TLS addresses. Both deny tools/subprocesses, application/.env/policy reads and filesystem writes after trusted imports. Windows job aggregate memory **512 MiB**, max **2 processes** (venv redirector + interpreter), kill-on-close; POSIX 512 MiB address-space/5 CPU seconds/no file/core output. ≤2 jobs/process, parser wall deadline 10s. Gateway defaults: 10s request timeout (+3s hard parent deadline), 2 attempts, 10 attempts/minute, concurrency 1, 4096 output tokens/100000-byte JSON reply. SDK hidden retries/function calling/tools are disabled. Metrics record usage/latency/attempts and optional integer-paise estimates, null when unknown/incomplete; no prompt logging. These guards are defense in depth, not independent OS-user/container isolation against arbitrary dependency RCE. Synchronous company locking favors consistent idempotency over throughput; limits are per process.

Late remittance correlation stores immutable LINKED/CANDIDATES/UNRESOLVED/SEARCH_INCOMPLETE snapshots. Only a locally attested unique exact UTR, valid bank source, latest successful extraction, current expected receipt version and nonconflicting known invoice/customer evidence can link. Wrong/multiple UTRs, unknown/conflicting owners, stale/invalid evidence or superseded extraction abstain. New state stales historical associations; retries conflict instead of silently accepting changed inputs. No invoice/receipt balances/versions/statuses, financial audit/source records or allocations/journals change.

Migration **0005_documents** adds documents, document_extractions, document_associations, document_operations and document_events, with scoped FKs/indexes/uniqueness and immutable UPDATE/DELETE/TRUNCATE triggers. **Financial CSV v1.0 is unchanged**; document JSON is a separate interface. Argon data/demo files were not generated, downloaded, changed or assumed integrated. Existing demo fixture SHA-256 remains `4a3c91af85aefead5eff0d1cdb28fbede190e995445e2f98af54568efb31c6da`. A random local document token was initialized only in ignored `.env`, without displaying it; external AI remains disabled and no Gemini key was generated. Example configuration contains placeholders only.

Development first upgraded up-only to existing 0004, then additive 0005. Ignored `local-data/m04_upgrade.py` compares every persisted column of all **11 pre-existing application tables** before/after upgrade/check. Result **0004_advanced_matching → 0005_documents**, all row fingerprints equal, no schema drift; final read confirmed 0005. Logs: `local-data/m04-development-upgrade.log`, `local-data/m04-development-schema.json`. No shared/portable database reset, downgrade, destruction or restart. Destructive checks use independent UUID-named disposable DBs; isolated Docker restart removes only its owned labelled resources.

Actual commands/results:

```powershell
./.venv/Scripts/uv.exe add 'pypdf>=6.21.2,<7' 'google-genai>=2.33,<3'
./.venv/Scripts/uv.exe run --frozen alembic upgrade head
./.venv/Scripts/uv.exe run --frozen alembic revision --autogenerate --rev-id 0005_documents -m "secure document intelligence"
./.venv/Scripts/uv.exe run --frozen python local-data/m04_upgrade.py
# Up-only development migration/check PASS; existing records unchanged.
./.venv/Scripts/python.exe -m pytest tests/test_document_domain.py tests/test_document_security.py -q -m 'not postgres'
# Final focused security run: 52 passed, 3 deliberately deselected DB cases, 10.49s.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# FINAL: lock/dependencies/lint/format/types/matching-bounds/tests-migrations PASS.
# 273 passed, 1 existing upstream Starlette/HTTPX warning, 110.92s; no skips/deselections.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# 2 passed, 1 existing warning, 7.74s; owned disposable container only.
```

All **188 regressions retained**, **85 new tests**: real PDF/email/canonical/hash/spans; malformed/active/encrypted/scanned/decompression/MIME/page/size limits; path/auth/tenant/Unicode integrity; actual worker capability denial and SDK mock-HTTP; PII/leakage/adversarial inputs/outputs; independent strict schema/money/label/category validation; provider failures/timeouts/retries/rate/concurrency/usage; duplicate/concurrent uploads/extractions; late/wrong/ambiguous/conflicting/superseded/stale correlation; immutable triggers and financial non-mutation; actual HTTP import and process restart. Complete migration roundtrip/drift/legacy-history/integrity checks pass. Strict mypy expands from 3 to **8 modules**, without ignores/weakening. CI uses the same gate with external models off; no real credentials needed, remote execution unobserved. Gate logs redact both file and environment URL/password/key/token/secret values; a canary regression covers differing secret values under the same key.

Failures corrected without weakening assertions: valid email lazy-runtime reads initially hit the parser guard; runtime-only reads are now allowed while application/policy reads remain denied. Immutability testing needed a real association row to exercise row triggers. Explicit short pytest IDs fix Windows' 32767-character environment limit on the oversized fixture; live-smoke helper use was corrected. A one-process Windows cap blocked the venv redirector; two processes now share one aggregate memory cap. Hypothesis found overlapping `invoice Invoice I-1` labels masking an essential reference; overlap-aware projection fixes it without narrowing the property domain. Platform-aware typing fixed Windows resource annotations without suppressions. Final money review added rejection of partial comma/overprecision amounts and signed paise, including pre-provider privacy abstention. All final tests pass.

Final logs: `local-data/verification/20261024T234937643553Z.log`, `isolated-restart-20261024T233403553520Z.log`, `local-data/m04-final-security-focused.log`. Earlier corrected diagnostics remain local (`m04-domain.log`, `m04-integration.log`, `m04-focused-final.log`, `m04-focused-4.log` and earlier verification logs). Shared container ID/StartedAt/RestartCount matched the pre-isolated-run snapshot. No real Gemini latency/accuracy/billing/provider-terms or real-data privacy approval is claimed.

Remaining limitations: OCR/HTML/attachments/office/archives unsupported; PDF visual layout unverified; atypical/multilingual/privacy/accuracy require human review; no live Gemini call or Argon evaluation. G1 full authenticated actors/roles, hardened production isolation/storage/quotas and trusted shared real-data use remain open. G4 remote Linux/Actions and Argon benchmarks remain unverified; G2/G3 stay closed. No milestone 05 cases/claim lifecycle, agents/LangGraph, Redis/MCP, tax adjudication, approvals, frontend or ledger posting. Git hash is recorded after checkpoint review. **STOP after milestone 04.**

## Milestone 03 — advanced deterministic matching · 2026-10-25

Verified implementation checkpoint: **`e28c359c708a4b9d5e4d58dc4f4eef40e992294a`**, message `feat: implement milestone 03 advanced matching`, branch `feat/milestone-03-advanced-matching`. Staged/reviewed exactly 22 intended files after all required checks passed; staged whitespace, actual local-secret exclusions and dataset/runtime exclusions passed. No unrelated changes or push. This documentation-only follow-up records the hash; no application changes followed final verification.

Started from verified `52be8c9`. The pre-existing `feat/milestone-03-advanced-matching` branch was fast-forwarded from its ancestor `8ff6687`; no branch/history was overwritten or reset. The sections below this milestone entry are historical observations from their named tasks and do not override this current status.

Implemented additive GET `/receipts/{id}/advanced-matching-context` and POST `/receipts/{id}/match-advanced`, retaining exact-v1 endpoints/results/body fingerprints. Reuses existing source/alias/reference verification, company transaction locks, scoped FKs, request mappings, audit events and immutable proposal history. New pure, strictly typed `advanced_domain.subsets` uses integer-paise meet-in-the-middle enumeration with a complementary-sum index, avoiding target-paise-sized DP memory and new dependencies. JSON candidates are proposals only: top-level amount remains zero and invoice selection null; no financial status/version/balance, receipt allocation or journal is mutated.

Behavior includes full referenced groups, full-balance subsets without references, explicit single-invoice partials and source-backed structured multi-invoice partials. Remaining AR and unapplied cash are explicit. Missing/ambiguous partial instructions abstain; no discounts, taxes, write-offs or settlement authorization are inferred. Mathematical uniqueness always requires review and does not acquire verified intent. Structured amounts must come from original memo JSON, with every invoice separately attested, exact key equality, positive strict integer paise, scoped/current versions and aggregate/per-invoice capacity checks. JSON-looking referenced sources require structured mode; amount instructions cannot be silently ignored. Persisted evidence includes original source ID/row/hash, reference spans and per-amount JSON Pointers. `docs/DATA_CONTRACT.md` **v1.0 CSVs remain unchanged**; optional structured memo convention and Argon adaptation are explicit in MATCHING/DATA_CONTRACT. No Argon file or existing demo fixture was changed, generated or downloaded.

Outcomes UNIQUE/AMBIGUOUS/UNRESOLVED/SEARCH_INCOMPLETE implement the approved original-name crosswalk. Complete relevant enumeration is required for mathematical uniqueness. Any candidate/evidence/size/work/time/top-K exhaustion is incomplete, including after finding one solution. A separately reported `ambiguity_proven` can coexist with truncated enumeration. Size pruning is conservative and may abstain even if a small solution exists. All feasible solutions are returned up to top-K; the next solution stops collision enumeration. No arbitrary candidate is selected.

Server-configurable `MATCHING_LIMITS` JSON defaults: **32 candidates, 8 invoices per combination, 100000 work units, 100 ms search time, top-K 20**. Hard ceilings: 40/40/1000000/2000 ms/100. The clock/work budget covers combinatorial search; DB reads, provenance parsing and HTTP overhead are separate. Positive-amount pruning is safe; duplicate amounts retain distinct invoice identities. Runtime timing lives outside input hashes, so concurrent/repeated keys reuse even an incomplete stored result. Changing effective limits or financial/evidence inputs creates a new snapshot; prior proposals remain immutable and are reported stale. Inputs beyond overflow caps are explicitly unproven, never safe to apply.

Migration `0004_advanced_matching` extends only the outcome constraint. Fresh disposable migration up/down/up/drift/integrity tests passed, as did upgrading existing exact-v1 financial/evidence/proposal/request/audit data, downgrading to 0003 and upgrading again with all rows unchanged. A downgrade containing newer outcomes fails atomically, preserving history. **The shared development database has not been migrated by these tests**; use `uv run --frozen alembic upgrade head` before using the advanced endpoint on an existing database. Never downgrade/reset development data for verification.

Actual commands/results:

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_advanced_domain.py -q
# Final focused pure run: 22 passed (independent Hypothesis exhaustive oracle: 150 examples).
$env:TEST_DATABASE_URL = & ./.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
./.venv/Scripts/python.exe -m pytest tests/test_advanced_matching.py::test_upgrade_legacy_history_roundtrip_and_mixed_algorithm_reads -q --require-postgres
# 1 passed in 2.15s; legacy rows/history unchanged, mixed algorithm reads correct.
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# 2 passed in 7.55s; own labelled disposable PostgreSQL restarted and removed only.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# lock/dependencies/lint/format/types/matching-bounds/tests-migrations: PASS.
# FINAL: 188 passed, 1 existing upstream Starlette/HTTPX deprecation warning, 60.80s; no skips.
```

Full gate preserves all 129 prior tests and adds 59, covering independent subset oracles, collisions/duplicate amounts, paise/BIGINT/zero/empty edges, eligibility/identity/company isolation, explicit partials, invalid structured evidence, all bounds, timeout/work interruption after one solution, stale balances/versions/evidence/pools/configuration, key conflicts, immutable timeout replay and observed concurrent different-key sessions. Both advanced sessions were observed waiting simultaneously on the actual PostgreSQL advisory lock, then returned one proposal, two key mappings and one creation audit event with unchanged financial rows/history. Strict mypy now includes the new pure search domain. Existing CI invokes the same expanded verification gate; remote execution is still unverified.

Numeric algorithm microbenchmarks (7 runs per vector; Python 3.12.14, this Windows host, default limits):

| Probe | Result | Median / max ms | Max work |
|---|---|---:|---:|
| 24 powers-of-two inputs, target 255 (oversized values safely pruned) | UNIQUE, exhaustive | 0.0262 / 0.6731 | 63 |
| 24 inputs, size pruning with one discovered subset | SEARCH_INCOMPLETE, size cap | 0.5372 / 0.6317 | 1792 |
| 24 equal values, many collisions | SEARCH_INCOMPLETE, top-K cap, 20 returned | 3.1892 / 4.1873 | 9134 |
| 32 equal values, worst configured work cap | SEARCH_INCOMPLETE, work cap | 65.6568 / 75.9238 | 100000 |
| 33 candidates | SEARCH_INCOMPLETE, count cap | 0.0010 / 0.0043 | 0 |

These are bounded numeric code probes, not realistic datasets or accuracy benchmarks, and do not promise wall time on other hardware. Clock-injection tests independently prove timeout safety. `scripts/verify.py` now runs this benchmark automatically. Local detailed logs: `local-data/verification/20261024T220457664326Z.log`, `matching-benchmark-20261024T220458872503Z.json`, `isolated-restart-20261024T215851706990Z.log`; focused legacy log `local-data/m03-migration-legacy.log`. Earlier diagnostics are retained locally, including full-gate failures `20261024T215534205964Z.log` (format-induced SQL line length, corrected) and `20261024T215610171949Z.log` (183 pass / migration roundtrip sharing another test's newer history). The latter was fixed by giving **each test its own disposable database**, without weakening the history guard or any assertion. Initial focused test queries also needed explicit tenant filters; all negative assertions were retained. All failures were corrected before completion.

Separate Docker restart verification passed; shared container ID/StartedAt/RestartCount matched the pre-check snapshot. Existing portable PostgreSQL and shared financial data remain untouched. Remaining limitations: G1 locally asserted actors are unauthenticated; no trusted real-data/shared use or posting. G4 remote Actions/Linux application runtime and Argon dataset integration/accuracy benchmarks remain deferred. Bounded search may intentionally be incomplete; current source evidence is limited to existing imported structured bank fields, with document ingestion/extraction reserved for 04. No later milestone features or datasets were introduced. Git completion identifier is recorded after checkpoint review. STOP after milestone 03.

## Completion log
| Milestone | Status | Verified commands/results | Notes |
|---|---|---|---|
| 00 | Implemented; local foundation verified | Historical foundation/Docker logs and current regressions below | No production-readiness claim |
| 01 | Local import/restart verification complete | Historical tests retained; new real process/fresh-connection/isolated-container persistence and replay checks | G2 closed; authentication/Argon benchmark claims remain deferred |
| 02 | Local matching verification hardening complete | Different-key overlapping PostgreSQL sessions, non-mutation, immutable history and uniqueness checks; full suite 129 passed | G3 closed; G1/G4 remain deferred/unverified |
| 03 | Implemented; locally verified | 188 full tests; strict types/lint/format/dependencies; migrations/legacy history; bounded benchmark; 2 isolated restart tests | Proposal-only; G1/G4 deferred; see current entry above |
| 04 | Implemented; local synthetic/offline verification complete | 273 full tests + 2 isolated restart tests; 8 strict typed modules; security/migration gate PASS | Gemini off by default; live/OCR/real-data/production/remote/Argon limits explicit |
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
- Completion checkpoint: **`92b21c729e18859f173e88f473caaeaba72a017d`**, message `feat: implement milestone 01 financial data engine`, on `feat/milestone-01-data-engine`. Before committing, reviewed/staged exactly 24 intended files, ran `git diff --cached --check`, and checked staged content against the actual local password and excluded paths. No secrets, dataset files, old fixture changes or unrelated files were staged. All required checks had passed (83 tests, migrations/restart, lint/format/dependencies). This documentation-only follow-up records the completion hash; no product code changed afterward.
- STOP after milestone 01. Do not start milestone 02 automatically.

## Milestone 02 — deterministic exact matching (2026-10-25)

This task explicitly authorized milestone 02 and supersedes the historical milestone 01 stop/current-state notes above. Work began from clean checkpoint `9dccb7a` on new branch **`feat/milestone-02-exact-matching`**; earlier history/branches were preserved. No remote push was attempted.

### Implemented behavior and design decisions

- The requested `prompts/02-exact-matching.md` did not exist; the repository had `02-entity-and-exact-match.md`. Read and retained the original, added the requested canonical filename incorporating the user's expanded requirements, linked both and clarified PLANS that this milestone creates proposals only.
- Added pure `matching_domain.py`, with strict integer validation and deterministic EXACT_MATCH / AMBIGUOUS / NO_SUPPORTED_MATCH plus RESOLVED / AMBIGUOUS / UNRESOLVED identity. Identity derives only from source-checked verified alias records or explicit local customer/reference attestations. Unknown payer, amount-only uniqueness, conflicting owners/intent, closed/zero/future/unequal invoices and unavailable cash abstain. Explicit verified invoice intent can disambiguate equal-amount invoices. No subset/partial search or later milestone was added.
- `matching.py`, `matching_schemas.py` and `matching_api.py` implement bounded, company-scoped evidence verification, match trigger/context/history and proposal reads. Citations must refer to this receipt's original accepted CSV source/row/field and a valid bounded character span. Rehash raw bytes, reparse typed rows and check semantic payloads/timestamps/customer association. A complete invoice number must be delimited, not a prefix/suffix of another identifier. The operator explicitly verifies customer/intent; bank text is never executable instructions or automatic authority.
- Added immutable matching_evidence, matching_proposals and matching_requests, source-linked audit events and company/ownership FKs. Unique request keys and receipt/snapshot identities plus company advisory locks protect replay/concurrent requests. Shared row locks stabilize current inputs; receipt and selected-invoice expected versions are required for exact proposals. Optional expected snapshot hash supports a prior-read precondition.
- Proposal snapshots retain actual receipt/invoice balances/status/currency/versions, customer and source identity, algorithm and evidence basis/validity. Reads compute staleness without changing stored proposals; balance changes **without** a version bump and new evidence are detected. Stale retries conflict. Same key/body/state returns the same proposal without another audit/request write; new keys on unchanged state share the same proposal. Reverification of identical source/target at newer aggregate versions adds history and supersedes only that locator's older verification; different targets still conflict.
- No matching operation changes customer, invoice, bank, receipt balances/statuses/versions, creates an allocation, recognizes bank cash or posts a journal. Already-partial balances can be compared for exact current equality; nothing is applied. Limits of 100 evidence / 1000 candidate invoices fail closed when exceeded.
- Existing CSV import schemas/contract **1.0** remain compatible; no dataset schema change is required from Argon. New matching metadata fields/API are specified in `docs/MATCHING.md`, linked from DATA_CONTRACT/API docs and README. Only tiny isolated application fixtures were added. No datasets or existing fixture contents were generated, downloaded, researched, curated, seeded or modified. Original demo SHA-256 is still `4A3C91AF85AEFEAD5EFF0D1CDB28FBEDE190E995445E2F98AF54568EFB31C6DA`.

### Quality infrastructure

- Cross-platform full command: **`uv run --frozen python scripts/verify.py`** (this workspace also has `./.venv/Scripts/uv.exe`). It loads TEST_DATABASE_URL from environment/ignored .env, requires PostgreSQL/CREATEDB, runs lock/dependency consistency, Ruff lint/format, strict mypy and the entire pytest suite with `--require-postgres`. Full logs are redacted and saved under ignored `local-data/verification/`; concise PASS/FAIL lines are printed. Missing DB configuration or any failed check fails verification; no integration-test fallback.
- Added mypy **1.20.2** to the locked development dependencies; strict checking currently covers `money.py` and `matching_domain.py` (2 source files), with no broad ignores or weakened checks. Existing ORM/API behavior stays covered by regression/integration checks. No runtime agent/framework dependency was added.
- `.github/workflows/verify.yml` runs that same command on Python 3.12 with ephemeral PostgreSQL 16.15, installs the frozen lock and uploads check logs. Permissions are read-only. Its password is a nonsecret, job-local ephemeral CI service value, not development/production credentials. No actual local credentials are in the workflow. Remote GitHub Actions execution is **unverified** because this task does not push or dispatch a workflow.

### Actual commands and observed results

Focused development check (detailed output in ignored `local-data/milestone02-focused.log`):
```powershell
$env:TEST_DATABASE_URL = & ./.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
./.venv/Scripts/python.exe -m pytest tests/test_matching_domain.py tests/test_matching.py -q --require-postgres
# 33 passed, 1 existing upstream warning in 8.64s (before additional boundary tests).
```

Dependency install: `$env:UV_CACHE_DIR="$PWD/.uv-cache-clean"; ./.venv/Scripts/uv.exe sync` resolved 41 packages and installed mypy/mypy-extensions/librt/pathspec; lockfile updated. Network-enabled execution was approved for the downloads. Migration generation compared metadata against a generated disposable DB at 0002, never the development DB.

Final complete command:
```powershell
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
```

Observed concise output: **lock PASS; dependencies PASS; lint PASS; format PASS; types PASS; tests/migrations PASS**. Detailed final log:
`local-data/verification/20261024T203050245983Z.log` (filename uses UTC).

Final results in that log:
```text
Resolved 41 packages in 1ms
Checked 42 packages in 3ms; All installed packages are compatible
All checks passed!
56 files already formatted
Success: no issues found in 2 source files
126 passed, 1 warning in 21.69s
```

The complete suite includes all 83 pre-existing tests plus 43 matching/domain tests. No existing test was deleted/weakened and no test was skipped. Covers exact single invoices/known aliases/direct references/manual mappings, ambiguity/conflicting references and customers, wrong ownership, amount-only abstention, paid/closed/future/partial balances, strict float/bool rejection and integer extremes, stale versions and unbumped balance changes, new/superseding evidence, exact and different-key idempotence, concurrent evidence/proposals, cross-company reads/FKs, bounded search, transport/quote/span/hash validation, immutable records (including TRUNCATE), and unchanged financial records on match/replay/GET. The corruption test bypasses a trigger only inside its disposable DB to verify digest detection; development/source data is not altered. PostgreSQL NULL invoice-version rejection is tested explicitly.

The full suite also executes committed upgrade → downgrade base → upgrade head, table/metadata drift and existing integrity checks on disposable databases, plus the live Uvicorn /health and /ready smoke. No unexecuted check is claimed passed. An earlier full run passed 121 tests before the final identifier-boundary/NULL guard assertions were added; the final run above includes them.

Development migration was then applied additively and logged to ignored `local-data/milestone02-migrations.log`:
```powershell
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
./.venv/Scripts/python.exe -m alembic check
# 0003_exact_matching (head); No new upgrade operations detected.
docker compose ps
# clearledger-db-1 healthy; 127.0.0.1:5432->5432/tcp
docker compose exec -T db psql -U clearledger -d clearledger -Atc "SELECT version_num FROM alembic_version; SELECT count(*) FROM pg_database WHERE datname LIKE 'clearledger_test_%';"
# 0003_exact_matching; 0 disposable databases remain.
git diff --check
# Passed.
git check-ignore .env .mypy_cache local-data/verification/example.log .local-runtime datasets/example.csv
# All listed paths ignored.
```

No development database reset/downgrade or existing portable PostgreSQL modification occurred. Detailed logs remain local rather than being committed/pasted into the chat.

### Files and limitations

Changed: `models.py`/`main.py`, new matching domain/service/schema/API modules, additive 0003 migration, new focused tests, pyproject/uv.lock, scripts/verify.py, GitHub Actions workflow, canonical milestone prompt, PLANS, README, DATA_CONTRACT/API docs and new MATCHING.md. Existing import/money behavior and fixtures remain intact.

Remaining limits: local operator IDs/verification assertions are not authenticated identities or approvals; no proposal execution exists. Staleness is a read-time snapshot observation, and future financial application must independently revalidate/authorize. Candidate budgets abstain conservatively; general evidence revocation/correction is deferred. The DB owner can disable triggers; ordinary app operations cannot. Static typing intentionally covers pure financial modules, not every legacy ORM/API function. Remote Linux/GitHub Actions execution and Argon dataset imports are unverified. The one pre-existing upstream Starlette/HTTPX deprecation warning remains; no required local check is failing.

Milestone 02 feature checkpoint is `8ff66873e866db025317d40a12588c4918bb2a4c`; its later status-only checkpoint `0772dfd` remains on the milestone 02 branch. The audit branch was created from the requested feature checkpoint, so that documentation-only descendant was not initially in its ancestry. No product code differs. Audit qualifications below supersede blanket completion readings of the historical notes. Milestone 03 has not started.

## Specification-alignment audit — 2026-10-25

User paused milestone 03 and requested an audit only. Created `chore/requirements-audit` from `8ff6687`; the untouched `feat/milestone-03-advanced-matching` branch remains at that verified milestone 02 checkpoint. No advanced matching code, schema, test or dataset changes were made; no branch/history was reset or overwritten.

Read AGENTS, PROJECT_SPEC, PLANS, STATUS, every existing milestone prompt and relevant architecture/domain/accounting/security/tax/API/matching/data-contract/evaluation docs. Compared original prompts at `a545b42` with actual code, named tests and feature/status commits. `REQUIREMENTS_AUDIT.md` contains the requirement-to-code/test/checkpoint matrix, approved changes, unintended specification regression, deferred requirements and blockers.

Open findings (not silently closed):
- **G1:** local actor/alias verification labels are unauthenticated assertions, not normative authenticated authority. This blocks trusted real-data/shared use and any approval/posting, regardless of the later role-workflow milestone. Source consistency does not authenticate an external verifier.
- **G2:** restart persistence was demonstrated with an organization/volume probe; imported invoice/receipt/source/audit values and digests have no dedicated container-restart acceptance test. SQL/session persistence is tested; no data-loss failure is alleged. That financial recovery acceptance evidence remains partial.
- **G3:** simultaneous same-key matching is tested and different keys reuse proposals sequentially; no dedicated simultaneous different-key/same-state proposal test exists. Locks/DB uniqueness exist; this is an assurance gap, not an observed duplicate-proposal bug. Report/resolve before extending matching claims.
- **G4:** remote GitHub/Linux CI and Argon dataset/benchmark execution remain unverified. No automatic external action is authorized or performed.

Specification alignment only:
- Restored original evaluation sizes/holdouts omitted during the Argon ownership rewrite, as **Argon-owned** requirements in EVALUATION: 50 customers, ~2000 invoices, ~500 receipts, ≥250 situations (original developer-size allowance retained), ≥100 documents and ≥30 attack/abuse scenarios. No dataset was constructed and no target is claimed achieved.
- Added `prompts/03-advanced-matching.md` as the approved extension/crosswalk to the intact original 03 checklist, preserving top-K/exhaustiveness, explicit remittance-driven partials, all original tests and worst-case-cap benchmark. This is specification work, not milestone 03 implementation. Approved outcome names cannot turn mathematical uniqueness into evidence-backed intent or treat budget exhaustion as proof.
- AGENTS/PLANS now explicitly preserve original prompt requirements/tests/exit gates unless an approved change supersedes them. The expanded 02 prompt explicitly retains the original checklist. Clarified the 08/09 dependency: authorization must exist before posting is enabled; the review-workflow schedule is not a waiver. No architecture rewrite or security exception was introduced.

Actual fresh verification command:
```powershell
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
```
Observed **lock/dependencies/lint/format/types/tests-migrations PASS**; **126 passed, 1 existing upstream Starlette/HTTPX warning in 24.96s**, no skipped tests. Full redacted local log: `local-data/verification/20261024T205239565998Z.log` (UTC filename). Historical old-checkpoint counts were checked from their recorded STATUS evidence, not falsely described as fresh executions of old checkouts. No application tests were weakened/deleted or new product tests added. No development migration/reset/restart or portable PostgreSQL change was performed by this audit.

Audit files only: AGENTS, PLANS, REQUIREMENTS_AUDIT, STATUS, evaluation spec and milestone prompt alignment. Financial/source data and existing fixture contents remain untouched. Audit checkpoint: **`6e1ad2deec2b86524561e383ab78c50e87952113`**, message `docs: audit milestone requirements and preserve acceptance gates`, branch `chore/requirements-audit`. Reviewed exactly 8 intended documentation files, checked staged whitespace/secrets and verified no application/test/schema/dependency diff from `8ff6687`. This documentation-only follow-up records the checkpoint hash; no product changes or push occurred. Stop here; gaps are reported and milestone 03 is not automatically resumed.

## Milestone 01–02 verification hardening — 2026-10-25

The user separately authorized closing audit G2/G3 only. This section supersedes their historical open status above. Branch **`test/milestone-01-02-hardening`** starts from audit/status checkpoint `58a9f8f`; existing feature branches/history are preserved. No milestone 03 code or datasets were implemented. G1 authentication/authority and G4 remote CI/Argon benchmark evidence remain **deferred/unresolved**, not closed by these tests.

### G2: financial import restart persistence — verified

Added `tests/test_restart_persistence.py`. It migrates only a generated disposable DB, creates one isolated company configuration, then imports minimal existing customer/invoice/bank test rows through a **real Uvicorn process**. Saves every persisted column for customers, invoices, bank transactions, receipts, source imports and audit events, including IDs, timestamps, versions, raw bytes/digests and results. Stops that process and disposes the verifier pool; a new DB engine/backend connection and a second Uvicorn PID must reproduce both the SQL rows and API payloads exactly. The configured development database is never reset/restarted.

Retries all three original keys with a renamed file after restart: original outcomes/IDs are reused, financial/provenance rows remain identical, old audit records are unchanged and exactly three replay events append. A fresh-key renamed bank import additionally tests natural identity: zero new bank/receipt, one duplicate, one new ingestion run with expected duplicate/acceptance audit events. Open invoice AR and receipt unapplied cash both remain 100 paise.

Added `scripts/verify_isolated_restart.py` for the optional real PostgreSQL restart proof. It uses the cached PostgreSQL 16.15 image and creates a unique UUID-labelled container plus named volume, random throwaway credentials and a chosen free IPv4 loopback port. The same persistence test then actually restarts only that owned container between application processes. Name/ownership labels must match before restart and cleanup; a negative test proves the shared `clearledger-db-1` name is refused before any Docker call. No Compose stop/restart/down operation is invoked. Generated credentials use a temporary file and are redacted from logs.

The initial real-container run exposed **test infrastructure** issues: the admin fixture reused a dead connection on cleanup, and Docker's empty host-port mapping was reassigned during restart (observed **52249→52262**). Corrected the fixture with `pool_pre_ping=True` (consistent with the existing application engine), and bound the isolated test's chosen host port explicitly. Retained the new assertion that the host binding remains unchanged. Failed runs were reported and cleaned up, not skipped; no application persistence defect was found and no application/schema/dependency changes were needed.

### G3: simultaneous different-key matching — verified

Added `tests/test_matching_concurrency.py`. Two separate SQLAlchemy Sessions obtain distinct PostgreSQL backend PIDs and synchronize through a barrier. A third connection holds the real company advisory lock; an observer checks **both** workers simultaneously waiting on that lock in `pg_stat_activity`, with READ COMMITTED isolation. Only then is the blocker released. This is actual concurrent database contention, not sequential calls or mocked sessions.

Both different-key/same-input requests succeed with the same deterministic proposal ID, snapshot and result. There is exactly one immutable proposal for the snapshot, two distinct idempotency-key mappings, and one proposal-creation audit event. Every financial/provenance row is compared unchanged, existing evidence/audit history is retained byte-for-value, both key replays add no records, direct duplicate snapshot insertion fails the DB unique constraint, and ordinary proposal/request/audit updates fail immutable-record triggers. This documents serialized equivalent success semantics; arbitrary/conflicting proposals are not accepted and no cash application occurs.

### Actual verification and isolation results

```powershell
$env:TEST_DATABASE_URL = & ./.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['TEST_DATABASE_URL'])"
./.venv/Scripts/python.exe -m pytest tests/test_restart_persistence.py tests/test_matching_concurrency.py -q --require-postgres
# Initial focused run: 2 passed, 1 existing warning in 6.05s (before guard-test addition).
./.venv/Scripts/uv.exe run --frozen python scripts/verify_isolated_restart.py
# Final isolated PostgreSQL restart run: 2 passed, 1 existing warning in 7.51s.
# Only this invocation's labelled disposable container/volume removed afterward.
./.venv/Scripts/uv.exe run --frozen python scripts/verify.py
# lock PASS; dependencies PASS; lint PASS; format PASS; types PASS; tests/migrations PASS.
# 129 passed, 1 existing upstream Starlette/HTTPX warning in 29.27s; no skips.
```

Full verification retains all 126 existing tests plus the application restart, shared-container safety guard and different-key concurrency tests. Existing assertions were not weakened/deleted. It includes strict mypy for money/matching, Ruff lint/format, lock/dependency checks, real PostgreSQL migrations up/down/up/drift/integrity, imports/isolation/financial non-mutation and live HTTP regression checks. Optional Docker verification fails explicitly on absent infrastructure/assertion failure; standard full verification always runs the new app-restart/concurrency checks without requiring Docker Engine or silently skipping them.

Detailed ignored local logs (UTC filenames):
- `local-data/hardening-focused.log`
- `local-data/verification/20261024T211312489837Z.log` (complete final suite)
- `local-data/verification/isolated-restart-20261024T211220500927Z.log` (successful real DB restart)
- Earlier failed isolated diagnostics retained locally as `isolated-restart-20261024T210720757263Z.log` and `isolated-restart-20261024T211105083750Z.log`.

Compared the shared development container's ID, StartedAt and RestartCount with the snapshot taken before any isolated run: **unchanged throughout hardening**. After final cleanup, Docker container/volume listings filtered by this verification-purpose label were empty. No shared data, existing portable PostgreSQL installation or Argon/demo fixture was modified. Tests use only minimal existing isolated row inputs; no demonstration/evaluation datasets were generated or downloaded.

Changed files: new two test modules and isolated Docker runner, administrative fixture reconnection/private runner option in conftest, README instructions, REQUIREMENTS_AUDIT disposition and this STATUS. No product matching/import changes, new dependencies or migrations were required. G2/G3 are closed with the specific evidence above; authentication, remote Actions execution and Argon benchmark limitations remain deferred. Verified checkpoint: **`71059c5098d30eb4d7ad4baca47d259a61dbf383`**, message `test: close financial restart and different-key matching verification gaps`, branch `test/milestone-01-02-hardening`. Reviewed/staged exactly 7 intended files; staged whitespace, actual local-password exclusions and unchanged application/schema/dependency/fixture checks passed. All required checks passed before commit (129 full tests plus 2 isolated restart tests). This documentation-only follow-up records the hash; no push occurred. STOP after hardening; do not automatically start milestone 03.
