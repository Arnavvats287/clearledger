# PLANS — Milestones, hard exit gates

Complete exactly one milestone per Codex task. `prompts/NN-*.md` contains the detailed implementer prompt. Later phases depend on earlier tests and schema. Mark milestones complete only with observed checks in `STATUS.md`.

| ID | Deliverable | Acceptance gate |
|---|---|---|
| 00 | Backend + database foundation | API responds; PostgreSQL migrates up/down in disposable DB; smoke tests pass; local run documented. |
| 01 | Synthetic finance dataset + import | Seed customers, invoices, bank CSV; replay import produces no duplicates; invalid rows rejected atomically or quarantined. |
| 02 | Customer resolution + exact allocation | Verified IDs, aliases and exact matches; ambiguity abstains; no over-allocation. |
| 03 | Multi-invoice and partial allocation search | Bounded subset search returns multiple candidates; collision detection and tests; no guessing from amount alone. |
| 04 | Immutable document import + isolated structured extraction | Original bytes hash, provenance + spans; late remittance correlates; injections stay untrusted data. |
| 05 | Persistent claims/cases + event engine | Claim lifecycle, monotonic source history, late-evidence replay and re-evaluation without duplicate allocations. |
| 06 | Read-only evidence retrieval + validator | Typed queries for contracts/WMS/promos/tax evidence, source/date/customer validity, missing evidence explicit. |
| 07 | Bounded Director–Investigator LangGraph | Deterministic director, constrained investigator, stop budgets, repeatable evidence citations and abstention; local stub mode works. |
| 08 | Policy, tax scope + accounting simulator | Versioned configurable rules, supported demo cases only; balanced journal; atomic idempotent application; unsupported tax routes to review. |
| 09 | Reviewer approvals + dispute/recovery | Role-checked maker-checker, draft-only evidence requests, reviewer comments, resolution/reopen flows. |
| 10 | Production-quality local UI | Four screens wired to real API, meaningful empty/error/loading states; E2E demo works. |
| 11 | Evaluation + hardening | Frozen scenario generator and ground truth; deterministic vs single-agent vs directed ablation; property, security and e2e tests; report limitations. |

## Dependency and sequencing notes
- Milestone 00 should not add LangGraph or LLM keys; milestone 03 should not add tax rules.
- Import bank transactions and maintain an unapplied balance BEFORE allowing allocation.
- From milestone 04, source documents are append-only; claims/evidence are versioned.
- From milestone 06, Investigator only gets typed allowlisted read-only functions, never raw SQL.
- From milestone 08, simulate a bank receipt ledger or reconciliation trace separate from clearing, avoiding duplicate bank entries.
- Never turn a synthetic approved withholding fixture into a general TDS compliance assertion.

## Evaluation tripwires
Incorrect autonomous customer resolution, duplicate cash application, over-allocation, unbalanced posting, unsupported writeoff, fabricated citation accepted, or unauthorized approval is a BLOCKER. Address before moving on.

## Review gate
After each phase, request: source diff summary, exact verification commands/output, observed new behavior, unknowns, and a demo command. If not verifiable, phase remains incomplete.
