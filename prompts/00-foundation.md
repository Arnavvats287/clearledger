# CODEX TASK 00 — Implement repository and database foundation ONLY

Read `AGENTS.md`, `PROJECT_SPEC.md`, `PLANS.md`, `docs/DOMAIN_AND_ACCOUNTING.md`, `docs/ARCHITECTURE.md`, and `STATUS.md` before editing. This repo currently contains a specification starter pack, not an app.

## Goal
Produce a working Python API development foundation with a real PostgreSQL DB, migrations, tests, formatting and clear local setup. Implement milestone 00 ONLY, then stop.

## Implement
1. Set up an idiomatic Python 3.12 FastAPI backend using a reproducible dependency manager (prefer uv if available). Create a clean install and test command.
2. Docker Compose for PostgreSQL plus a health-check; optionally include an API service if it improves reproducibility. Use `.env.example`; never commit secrets.
3. SQLAlchemy 2, Alembic and the **minimal** organization/customer persistence needed to demonstrate DB connectivity and migration. Do not prematurely create all future tables.
4. `GET /health` (process alive) and `GET /ready` (DB connection confirmed).
5. Pure domain money functions: `paise_from_decimal_string(str)->int`, `decimal_string_from_paise(int)->str`, percentage/rate multiplication with `Decimal` and `ROUND_HALF_UP`, explicitly rejecting float input. Support zero and negative signs as domain utility; specific business entities will constrain signs later.
6. Test infrastructure: pytest and ruff. Test money boundaries including `"1.005"` -> 101 paise using ROUND_HALF_UP, `"0.01"` -> 1, negative conversion, and float rejection. Test ready endpoint against PostgreSQL; test DB migrations on a disposable database.
7. A focused `README` section on setup, migrations, running server, tests, and known local limitations. Keep planning pack files intact.

## Non-goals
No frontend, Redis, LangGraph, LLM, invoice matching, MCP, payments, bank parsing, journal posting, production cloud deployment, authentication implementation, live tax rules, or speculative module scaffolding.

## Completion checklist
- Run exact commands successfully: install, migration upgrade, API health/ready, pytest, lint and if configured typecheck. Paste concise observed output in your completion summary.
- Run migration downgrade/upgrade in a **disposable test DB** or explain precisely why not verified.
- No floating point financial calculations.
- Update `STATUS.md` with files created and checks actually run; do not mark future phases complete.
- STOP after task 00. Do not start task 01.
