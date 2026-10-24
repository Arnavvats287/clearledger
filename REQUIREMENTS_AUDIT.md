# ClearLedger requirements-alignment audit

**2026-10-25 · audit only · milestones 00–02.** Compared all existing prompts, AGENTS, PROJECT_SPEC, PLANS, STATUS, domain/accounting/security/tax, matching/API/data-contract and evaluation/architecture specifications with code, named tests and Git history. Original prompt text was checked at baseline `a545b42`, not inferred from rewritten prompts.

Application baseline: `8ff6687` (same code as documentation checkpoint `0772dfd`). The empty milestone 03 branch remains at `8ff6687`; this documentation-only audit is on `chore/requirements-audit`. No milestone 03 code, schema, datasets or test changes were made.

Migration numbering is separate from milestone numbering: 0001_foundation belongs to 00, 0002_data_engine to 01, and 0003_exact_matching to 02. The existing 0003 migration is not evidence of advanced-matching implementation.

## Observed verification and checkpoints

| Milestone | Git checkpoint | Recorded verification |
|---|---|---|
| 00 | `a545b428996f33816c0aebc60e6841dd89a72554` | 41 tests; PostgreSQL migrations, health/ready, lint/format; later Docker verification recorded in STATUS |
| 01 | `92b21c729e18859f173e88f473caaeaba72a017d`; status `9dccb7a` | 83 tests; import/isolation/concurrency/integrity, migrations, Docker restart probe, lint/dependencies |
| 02 | `8ff66873e866db025317d40a12588c4918bb2a4c`; status `0772dfd` | 126 tests; immutable exact proposals, stale state, concurrency, strict domain types and complete verification |

Fresh audit execution: `uv run --frozen python scripts/verify.py` (workspace executable `./.venv/Scripts/uv.exe`): **126 passed, 1 existing upstream warning in 24.96s**; lock, dependency compatibility, Ruff lint/format, strict mypy (2 pure financial modules), PostgreSQL up/down/up/drift/integrity and live health/ready checks all passed; no skipped tests. Detailed local log: `local-data/verification/20261024T205239565998Z.log` (UTC filename). These are current local observations; earlier counts are historical, not fresh executions of old checkouts. GitHub Actions has not run remotely.

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
| 01 tests: balances, tenant FKs, invalid rows, duplicates, restart survival | Named tests above, PostgreSQL tests; `verify_docker.py` restarts a committed organization probe | Financial-record restart acceptance has narrower evidence than the milestone suggests: G2 |
| 02.1 Verified mapping/alias/reference resolution and candidate basis | `matching.bank_valid/source_valid/evidence_valid/build_snapshot/register_evidence`; known/unknown/manual/direct reference, wrong-owner/source/span/digest tests | Local record consistency/attestation implemented/verified; external identity/authority not established (G1) |
| 02.2 Pure integer exact matching, explicit ambiguity/unresolved | `matching_domain.decide`; pure decision/Hypothesis tests; same-amount/closed/future/unequal/conflicting-reference API tests | Implemented/verified; explicit invoice intent is a documented conservative restriction, not permission to infer settlement from amount |
| 02.3 Preserve partial/open/unapplied balances, immutable/versioned proposals | `MatchingEvidence/Proposal/Request`, `0003_exact_matching...py`; `test_exact_immutable_idempotent_and_financially_nonmutating`, partial-balance, DB NULL/version/immutability tests | Implemented/verified; no allocation/posting/balance mutations |
| 02.4 Trigger/read APIs, idempotence, stale state, strict isolation | `matching.py`, `matching_api.py`; stale versions/unbumped balances, new evidence, replay, tenant and concurrency tests | Implemented/verified for tested paths; distinct-key simultaneous proposal coverage remains G3 |
| Approved 02 quality additions: complete verification, CI config, practical types | `scripts/verify.py`, `.github/workflows/verify.yml`, strict mypy config | Local checks passed; remote Linux/Actions execution remains unverified (G4) |

## Gaps, blockers and required disposition

| ID | Gap / evidence | Gate and next action (not implemented by this audit) |
|---|---|---|
| G1 | Normative authenticated actor/role authority is absent. X-Actor-ID and imported verified_by are asserted strings; source/hash consistency does not authenticate a verifier. MATCHING/DATA_CONTRACT disclose this. | **Blocker for trusted real-data/shared use or approval/posting**, not proof that auth passed. Users/roles/maker-checker are scheduled for 09, but no milestone may treat that schedule as a waiver of SECURITY/AGENTS gates. Keep local test-only limitations explicit; require authorization before any posting is enabled. |
| G2 | `verify_docker.py` persists only an organization probe across restart; no test captures imported invoice/receipt/source/audit values and digests through an actual container restart. SQL/session persistence and generic volume restart are verified. | **Partial acceptance evidence**, not a demonstrated data-loss bug. Add a disposable financial-import restart check before claiming the complete milestone 01 recovery path verified. Do not weaken/remove the original restart requirement. |
| G3 | `test_matching_and_evidence_concurrency` sends the same proposal key concurrently; different keys are tested sequentially. The company lock and unique snapshot constraint exist, but simultaneous different-key/same-state proposal behavior has no dedicated test. | **Concurrency assurance gap before extending matching**: add focused different-key concurrency/non-mutation assertions in a separately authorized remediation task. Existing tests/constraints must remain. No claim that duplicate proposals actually occurred. |
| G4 | GitHub Actions is configured; remote execution and Linux runtime are unobserved. No Argon dataset or benchmark was imported/evaluated. | Verification limits, not passing CI/benchmark results. Remote execution requires user-authorized external action; do not push automatically. Argon artifacts and future evaluation are prerequisites for benchmark claims. |

No functional failure was observed by the current 126-test suite, but passing it does not close G1–G4. **Do not advance automatically.** Report/triage the open verification gaps before resuming milestone 03; production/posting restrictions remain binding.

## Contradictions, scope changes and alignment performed

- **Approved:** M01 generator/demo seeding and repeat-seed deliverables moved to Argon; Codex retains schemas/importers/application code/minimal isolated fixtures. The existing demo reference was not modified. Evaluation quality/coverage was never waived.
- **Unintended specification regression, corrected:** the M01 rewrite of `docs/EVALUATION.md` dropped original numerical targets from `a545b42`. Restored them as Argon-owned targets: 50 customers, ~2000 invoices, ~500 receipts, ≥250 situations (original developer-size allowance retained), ≥100 documents, ≥30 attack/abuse scenarios, train/dev/test isolation and held-out combinations. No dataset was constructed and no target is claimed met.
- **Approved additions, not scope creep:** M02 persistence, concurrency/staleness, explicit evidence APIs, reusable verification, CI and financial-domain typing were requested. CSV source integrity supports matching; no milestone 04 document/extraction system or milestone 06 general evidence tooling was implemented early. No later product functionality was found.
- **Prompt names/checklists:** original 02 prompt remains required alongside its expanded 02 prompt. The requested 03-advanced-matching filename was missing; added a documentation-only extension that retains every original 03 numbered item, test and worst-case benchmark gate. New outcomes map old semantics: UNIQUE_WITH_EVIDENCE is an evidence-qualified UNIQUE, MULTIPLE_CANDIDATES→AMBIGUOUS, NO_MATCH→UNRESOLVED, BUDGET_EXCEEDED→SEARCH_INCOMPLETE. Mathematical uniqueness alone never supplies intent/authority; incomplete search cannot prove uniqueness.
- **Sequencing tension preserved, not waived:** 08 requires gated posting/approvals while 09 provides the full role/review workflow. PLANS now explicitly requires the authorization gate **before** posting is enabled; no permissionless interim posting or architecture reorder is authorized.
- **Documentation-only divergence:** branching from the requested `8ff6687` excludes status-only commit `0772dfd`; code is identical. STATUS now records the known feature hash directly. No history was lost/reset and neither branch was overwritten.

## Intentionally future / not missing milestone 00–02 features

03: bounded multi-invoice/subset and explicitly instructed partial search, top-K/exhaustiveness, configurable count/size/work/time limits and worst-case-cap benchmark. 04: immutable documents and isolated extraction. 05: cases/claims/events/outbox as needed. 06: generalized read-only evidence retrieval/validator. 07: bounded deterministic Director/optional investigator. 08: conditional tax review and balanced idempotent authorized accounting simulator. 09: user roles/maker-checker/recovery drafts. 10: real API-backed UI/E2E. 11: three-arm evaluation against Argon's frozen ground truth. All original future tests/exit gates remain required; no dataset ownership change waives them. No live tax compliance is claimed.

Audit changes are specifications/status only. Application, architecture, schema, tests and financial data were not rewritten. Stop after this audit; open findings are not silently marked complete.
