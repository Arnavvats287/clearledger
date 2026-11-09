# ClearLedger product latency benchmark

Measured on 2026-11-09 at frozen product commit
`94924cf7f17a26d14143ba317123fd4857f7005f`. This is a sequential latency
measurement on existing synthetic AR fixtures.

## Environment and method

- Windows 11 build 26200, Intel Core i5-11400H at 2.70 GHz, 12 logical
  processors, 15.73 GiB OS-visible host RAM. Docker Desktop engine 29.9.2
  reported 12 CPUs and 7.62 GiB for its Linux environment.
- Python 3.12.14, FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.0.55,
  psycopg 3.3.6, LangGraph 1.2.17 and PostgreSQL 16.15. The Starlette ASGI test
  client exercised the real FastAPI routes in process. The parser used the
  normal isolated subprocess. Persistence used a newly migrated disposable
  PostgreSQL database for each repetition.
- Five cases, one excluded warm-up per case, then 20 measured repetitions
  per case. One caller, one invoice, one receipt, one short text remittance,
  and up to two short authenticated synthetic promotion records per repetition.
  Used monotonic `perf_counter_ns`. p50 is the median; p95 is nearest rank
  (`ceil(0.95 × n)`). Stage intervals with repeated calls are summed within
  each case before calculating percentiles.
- Initial customer, invoice, payer alias and bank receipt imports, database
  creation/migrations, baseline/final safety reads and test setup/cleanup were
  outside the stopwatch. The measured window starts with remittance upload and
  ends at the first usable terminal API response for the defined workflow.
  Matching/source registration, outbox work, investigation and reads needed to
  reach that state are included where applicable. The outbox worker is driven
  immediately through its existing code, with no poll interval or queue backlog.
- External AI, external investigation and the extraction provider were disabled.
  No quota sleeps or provider calls occurred. Local deterministic workflow wall
  time and measured end-to-end time are therefore the same within this boundary.

## Workloads and review milestone

| Workload | Measured end point |
| --- | --- |
| Clean extraction | Deterministic extraction returns persisted invoice/UTR and a human-review flag. |
| Exact matching and correlation | A verified synthetic matching reference yields `EXACT_MATCH`. The document links and the persisted case is returned with the invoice, receipt and document. |
| Supported short-payment deduction | A 101-paise residual and extracted rebate, supported by the signed synthetic promotion, produce a current `SUPPORTED / HUMAN_REVIEW` finding. |
| Missing evidence | The same short payment without promotion evidence produces a current `INSUFFICIENT_EVIDENCE / REQUEST_EVIDENCE` finding. |
| Conflicting evidence | Two signed promotions with different amounts produce a current `INSUFFICIENT_EVIDENCE / REQUEST_EVIDENCE` finding with a conflict flag. This is the actual deterministic outcome for this fixture. |

Time to usable review is the first persisted extraction result for the clean
case, the first linked case view for exact correlation, and the first current
finding for each investigation. The stopwatch stops at that milestone in all
five workloads, so the two latency summaries are identical. This excludes any
time for a human to act.

## Measurements

All entries are milliseconds, shown as **p50 / p95 / max**.

| Workload | Timed cases | Local end-to-end and time to usable review |
| --- | ---: | ---: |
| Clean extraction | 20 | 552.825 / 609.013 / 864.262 |
| Exact matching and correlation | 20 | 2,249.944 / 2,676.090 / 2,698.037 |
| Supported short-payment deduction | 20 | 5,859.556 / 6,380.208 / 6,501.775 |
| Missing evidence | 20 | 4,645.125 / 4,989.646 / 5,128.882 |
| Conflicting evidence | 20 | 6,751.745 / 7,256.481 / 7,871.441 |

| Stage | Timed cases | p50 / p95 / max |
| --- | ---: | ---: |
| Main remittance ingest API | 100 | 508.703 / 610.975 / 995.721 |
| Isolated parser, single remittance only (clean workload) | 20 | 454.034 / 512.632 / 519.504 |
| Isolated parser, all documents per case (mixed workloads) | 100 | 488.055 / 1,432.070 / 1,507.171 |
| Deterministic extraction API | 100 | 34.354 / 40.347 / 187.215 |
| Grounded invoice candidate construction, independent local probe | 100 | 0.272 / 0.407 / 0.496 |
| Advanced allocation candidate analysis | 60 | 0.028 / 0.046 / 0.071 |
| Matching API and context reads, exact workload | 20 | 67.131 / 80.322 / 80.383 |
| Exact decision logic, exact workload | 20 | 0.690 / 0.724 / 0.731 |
| Correlation API, all correlated workloads | 80 | 51.661 / 62.071 / 442.600 |
| Correlation service, all correlated workloads | 80 | 41.407 / 49.906 / 433.439 |
| Evidence retrieval | 60 | 234.830 / 272.468 / 305.478 |
| Deterministic extraction source validation | 100 | 0.037 / 0.140 / 152.482 |
| Deterministic evidence verification | 60 | 217.384 / 390.798 / 752.967 |
| PostgreSQL cursor execution + commits, mixed workloads | 100 | 2,654.864 / 3,527.732 / 4,028.049 |
| PostgreSQL DBAPI commits only, mixed workloads | 100 | 246.885 / 479.993 / 834.291 |
| Outbox drains | 80 | 1,580.838 / 2,047.999 / 2,224.724 |
| Investigation worker to durable result | 60 | 2,157.425 / 2,599.425 / 3,167.977 |
| Gemini generation | 0 | Unmeasured |

The stage measurements are inclusive and may overlap. For example, document
ingest includes parser time, and the evidence broker and outbox intervals
include PostgreSQL. Do not add the table rows to calculate end-to-end time.

- **Parsing:** cumulative isolated parser time, including subprocess overhead.
  The supported and conflict workflows parse one and two evidence documents,
  respectively, in addition to the remittance.
- **Candidates:** the advanced matching analysis receives the existing verified
  snapshot and produces allocation candidates. Grounded invoice-ID catalog
  construction is a separate in-process measurement on the existing synthetic
  prose remittance. That catalog is not used by the clean deterministic
  extraction route and its timing is excluded from end-to-end.
- **Matching and correlation:** helper wall time includes the required context
  reads and the API call. The exact decision and correlation service timings
  also isolate their corresponding in-process boundaries.
- **Evidence and validation:** retrieval and verification time cover the real
  investigation broker calls, including their scoped database reads. Remittance
  source validation is timed separately.
- **Persistence and workflow:** PostgreSQL time sums cursor execution and
  DBAPI commits across the application and worker engines, including both
  reads and writes. It excludes result materialization, transaction rollbacks
  and other client-side work. The outbox and investigation worker rows give
  the corresponding wall-time boundaries, including workflow computation.

All 100 timed workflows reached their expected outcome. The probe observed
1,420 HTTP 200 responses and zero API or application errors in those workflows.
External calls were **0 per case**, so no provider failures occurred and no
provider token reports exist. This run supplies no estimate of Gemini latency,
token usage when enabled or provider reliability.

The final local sample file is
`local-data/product-latency-94924cf-v2/samples.jsonl`, SHA-256
`a683fb9ed08128100e16c35a92ab5af64bf7a9253a66ce3ffbff6f81a81e0f02`.
Two probe calibration attempts are excluded from these measurements. They
exposed a fixture mismatch in the standalone candidate probe and a response
counter tied to a different HTTP client class. Only the measurement probe was
corrected.

## Financial safety and interpretation

All 100 timed samples passed financial non-mutation checks. The benchmark
compares complete before/after API snapshots for customers,
invoices, bank transactions, receipts and payer aliases. It also compares full
tenant rows for balances, cash allocations, noncash settlements, ledger
journals and lines, finance approvals, commands and proposals, and provider
reservations. Test-source trust is scoped to the synthetic fixtures. Case
associations, outbox events, evidence records and findings are expected workflow
writes. The measurement exercises no finance approval or posting endpoint.

These are small single-caller synthetic fixtures. Larger inputs, concurrency,
network/TLS, browser rendering, worker polling, live Gemini and production
hardware are outside the measurement. A p95 from 20 samples is a descriptive
statistic for this environment. It does not establish a production SLA. The
private AR benchmark was outside the measurement.

**Defensible latency claim.** On this Windows development machine with
disposable PostgreSQL and external AI disabled, ClearLedger reached a reviewable
state in 0.61 s p95 for a small structured remittance, 2.68 s p95 for the exact
receipt/invoice correlation workflow, and 4.99–7.26 s p95 across the three
deduction workflows, each measured over 20 sequential repetitions.

## Reproduction

Run from the repository root with the frozen dependencies and the existing
local `TEST_DATABASE_URL` role with `CREATEDB` permission. The command loads
only the test connection from `.env` when needed and writes no source text or
credentials to the sample file. Choose a fresh ignored output path on each run.

```powershell
@'
import os
from pathlib import Path
from dotenv import dotenv_values
import pytest

os.environ.setdefault("TEST_DATABASE_URL", dotenv_values(".env").get("TEST_DATABASE_URL") or "")
assert os.environ["TEST_DATABASE_URL"], "Disposable PostgreSQL connection required"
root = Path("local-data/product-latency-reproduction")
root.mkdir(parents=True, exist_ok=False)
os.environ["CLEARLEDGER_PERF_OUTPUT"] = str(root / "samples.jsonl")
os.environ["CLEARLEDGER_PERF_REPEATS"] = "20"
raise SystemExit(pytest.main([
    "tests/benchmark_product_latency.py", "--require-postgres", "-q", "-x",
]))
'@ | uv run --frozen python -
```

Exclude rows with `iteration=0` before aggregation. The committed probe is
opt-in and remains outside normal test discovery.

## Verification

- Measurement run passed all 105 cases, including five excluded warm-ups.
  Sample integrity checks verified exactly one result for every case and
  iteration, HTTP 200 responses and the before/after safety flags.
- Post-run focused verification passed 125 tests covering the portfolio API
  workflow, correlation, grounded investigation, matching, document parsing and
  finance. It used `--require-postgres` and the existing disposable test
  database fixture.
- Repository-wide Ruff lint and format checks passed. The opt-in probe compiled.
  Product source, migrations and dependency locks matched the frozen commit.
