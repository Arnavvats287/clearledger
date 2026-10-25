# Post-M09 application evaluation — development snapshot

Executed locally on **2026-10-26 IST** against application checkpoint `b0485f2`
(M09 implementation `5c91290`). This is an API integration/evaluation task, not
Milestone 10 or completion of the full Milestone 11 benchmark.

## Scope and isolation

The operator supplied only the exported `inputs/clearledger-dev` directory from the
independent `clearledger-benchmarks` project and confirmed its export cutoff:
**2026-01-19T12:00:00+05:30**. It contains **385 files / 530,900 bytes**, consisting of
four CSVs and 381 original documents. It is **one manually selected development
snapshot**, not all 420 receipts or their 426 original stages. No evaluation-split,
original-stage schedule or answer key was supplied to this harness.

Only the benchmark's public README, ADAPTERS and PREDICTIONS interface documentation
was inspected. No benchmark Python package, generator, source corpus, inventory,
canonical sidecar, scorer or hidden truth was imported or executed. The input loader
accepts only the four named imports and the exported original-document directories;
other paths, executable files, links, traversal, oversize inputs and input mutations
fail closed. All 385 file hashes were sealed before execution and verified afterward.
CSV receipt/alias timestamps and invoice issue dates were checked against the declared
cutoff: **zero future-record violations**. Document availability cannot independently
be checked without authorized availability metadata; the supplied export's selection
is an operator declaration, not source authentication.

The harness creates/drops only a generated, owned PostgreSQL database, safely migrates
it to existing head **0011_review**, and checks schema drift. It provisions only the
organization and one temporary AR_ANALYST demo user directly; all financial/document
inputs enter through actual HTTP APIs. The normal FastAPI factory runs in a separate
Uvicorn process on loopback with role mode enabled. It receives DB/company/storage
configuration and original upload bytes, **not the benchmark/input-root path or any
evaluation answers**. The normal bounded outbox worker handles committed source events.
The database and API process are removed before predictions are finalized.

This is enforced dataflow separation, not a new OS-user/container sandbox against a
compromised trusted host. The harness itself can read only the explicitly supplied
visible export by design. No production identity adapter, publisher keys, evidence
signatures, payment-intent attestations or finance policies are manufactured. Gemini,
external investigation, tracing and external token budgets remain disabled. Financial
posting is never enabled using demo credentials. Development data is never migrated,
reset or downgraded by this task. Original pilot reports and both ZIPs are unchanged.

## Actual records and API outcomes

Final private run: `local-data/application-evaluations/30f74f6a075a4ba0adc2925323ab7920/`.
Only aggregate measurements are committed; raw observations, identifiers, source text,
credentials and prediction artifacts stay ignored locally.

| Observation | Actual result |
|---|---:|
| CSV files accepted / rows | 4/4; 979 rows |
| Customers / payer aliases | 30 / 81 |
| Invoices / bank transactions / automatically created receipts | 684 / 184 / 184 |
| Same-key plus fresh-key CSV replay probes | 8 HTTP 200; financial record counts unchanged |
| Exact / advanced matching requests | 184 each; each repeated with the same key |
| Original document uploads / unique stored documents | 381 / 381, all HTTP 200 and READY |
| Source original bytes/hash and canonical-pages digest checks | 381/381 each |
| Actual canonical-span probes / forged quotes rejected | 381/381 each |
| Deterministic extraction succeeded / requires review | 6 / 375 |
| JSON literal reference checks | 2/2 invoice refs and 6/6 UTR refs, across six JSON originals |
| Unattested correlation attempts | 5: 4 CANDIDATES, 1 UNRESOLVED; zero LINKED |
| Application cases | 189: 184 receipt cases, 5 document-only cases |
| Native evidence queries | 183/183 HTTP 200; 4,205 returned hits |
| Source-authenticated evidence hits | 0 |
| Materialized deduction claims / investigation requests | 0 / 0 |
| Outbox deliveries | 1,881 delivered in 19 bounded drains; no pending work |
| Unexpected financial changes / journals / allocations / settlements | 0 |
| External provider reservations | 0 |
| Financial read using the demo session | HTTP 503, verified identity unavailable |

All **4,176 measured API calls** returned 3,794 HTTP 200, 381 expected HTTP 422
(deliberately forged spans), and one expected HTTP 503 (finance authority probe).
No unexpected API failures remained in the corrected run. Login/readiness calls are
outside that latency denominator. All balance/status/version/source rows were compared
before and after matching, documents and case work; no financial mutation occurred.

Current unresolved invoice AR is **8,696,422,470 integer paise**; receipt unapplied cash
is **4,600,151,914 integer paise**, both unchanged. These are observed snapshot balances,
not approved settlements or predictions of later stage balances. No bank journal is
invented for unauthenticated raw intake.

## Matching and abstention

| Algorithm outcome | Count |
|---|---:|
| Exact NO_SUPPORTED_MATCH | 176 |
| Exact AMBIGUOUS | 8 |
| Exact supported allocation | 0 |
| Advanced UNIQUE | 112 |
| Advanced AMBIGUOUS | 17 |
| Advanced UNRESOLVED | 39 |
| Advanced SEARCH_INCOMPLETE | 16 |

The baseline creates **zero matching attestations**. Imported aliases remain supplied
local identity assertions; memo text, invoice strings and mathematical uniqueness do
not become verified payment intent. All **184 snapshot predictions abstain from invoice
allocation**. The 112 UNIQUE outcomes are mathematical candidates, not authorized cash
allocations. The 16 incomplete searches report the combination-size limit, never proof
of uniqueness. Captured default bounds are 32 candidates, combination size 8, 100,000
work units, 100 ms and top-K 20; these were not tuned from answers.

No target-based matching accuracy, correct-abstention rate, false-supported-match
precision or allocation recall is claimed. Targets were not available, and precision
with zero supported outputs has an empty denominator. This measures actual conservative
application behavior under unattested inputs, not natural discovery of trusted intent.

**Repeatability limitation:** four receipt-level advanced outcome labels differed
between the initial diagnostic and corrected runs, despite identical visible input
hashes and bounds. Fresh imports generate different invoice UUIDs; the existing matcher
sorts those IDs into meet-in-the-middle halves, and its conservative size-pruning flag
can change with that partition. Two status changes cancel in aggregate counts. Natural
invoice sets were identical for affected receipts. All allocation predictions remained
abstentions and balances remained unchanged. The application was not modified to improve
scores. Runs preserve actual IDs, limits, candidate arrays and provenance; do not assert
bit-identical intermediate outcomes across fresh UUID assignments or clock budgets.

## Extraction, citations and investigation gaps

All 381 originals parse, including 215 PDFs, 52 emails, 108 text files and six structured
JSON remittances. The six JSONs are the only deterministically extracted documents;
the other 375 use REVIEW with zero model attempts. Six successful runs are **not**
evidence of semantic extraction accuracy across the corpus or Gemini accuracy. Their
literal reference lists match their actual JSON source fields. Unstructured extraction
accuracy is **NOT EVALUABLE** without authorized labels and an enabled, reviewed model.

Source consistency is distinct from authenticity and relevance: the 381 positive/
negative span probes use actual API-produced canonical text and independent original/
pages digest checks. They do not authenticate senders, prove deduction legitimacy or
verify benchmark claim citations. The benchmark's canonical TXT SHA and byte-span
contract differ from the application's canonical-pages JSON digest. Neither TXT sidecars
nor an authorized document-version/claim binding are supplied. No offsets/hashes are
invented or silently translated; benchmark citation recall/entailment is **NOT EVALUABLE**.

The export provides no evidence-1.0 signed manifests or reviewed publisher keys. Native
invoice retrieval works, but its 4,205 source-consistent hits remain unauthenticated.
Text saying signed/approved cannot replace source authentication. No records are signed
by the evaluator or converted into fictional approvals.

No deduction claims materialize from the six JSONs (their claims lists are empty), and
the semantic documents require review. Consequently there are **zero M07 investigation
requests**. End-to-end deduction investigation, legitimacy, financial approval, statutory
tax treatment and later settlement are **NOT EVALUABLE / REVIEW REQUIRED** here, not
successful or incorrect predictions. Existing implemented components remain regression
tested; this export does not exercise them meaningfully. No claims are synthesized from
short-payment arithmetic or benchmark answers merely to increase coverage.

## Prediction interface and chronology

The separate benchmark's public `docs/PREDICTIONS.md` is the interface. Outputs are:

- `snapshot-predictions.json`: 184 actual receipt observations using complete natural
  keys `{source_system,account_ref,external_transaction_id}`, the operator's export
  cutoff, customer reference where known, explicit abstention, empty incremental cash
  allocations and `financial_authority=false`. Actual API UUID/source mappings remain
  in private `observations.json`. Not every bank row is assumed to be a primary case anchor.
- `stage-predictions.json`: a deliberately empty native prediction list. Without an
  authorized original-stage schedule, **zero stage bindings are asserted**. The public
  scorer contract allows omitted snapshots to lower coverage. Do not pass the snapshot
  file as if every receipt had an original stage at 19 January: unknown keys can be
  correctly rejected. A separate scorer/operator must bind only independently authorized
  receipt/cutoff requests, using a matching visible export for each time.
- `summary.json`, `input-inventory.json`, per-document progress and API/worker logs:
  exact counts, hashes, harness code digests, timing, outcomes and limitations.

Unsupported monetary/journal/claim/citation capability fields are omitted, so they are
**NOT EVALUABLE**, rather than populated with artificial perfect results. There is no
hidden-answer reader or target feedback loop. Later snapshots cannot be manufactured
from this export. Original-stage chronology, stage accuracy, held-out/blind performance
and full 420-receipt/426-stage coverage remain **NOT EVALUABLE**.

## Performance and reproduction

Final wall time including disposable DB setup, worker processing, cleanup and source
verification: **525.939 seconds**. Across 4,176 measured requests: p50 **33.363 ms**, p95
**455.721 ms**, max **3,506.113 ms** (nearest-rank percentiles). Parent-Python traced peak
allocations: **40,191,007 bytes**; this excludes API/worker/PostgreSQL RSS and is not total
system memory. This is one local Windows run, not a throughput/SLA or provider benchmark.
Application commit, harness SHA-256 values, actual API snapshots and limits are saved.
Use the frozen project environment and captured configuration; non-overridden local
matching settings must match the saved bounds for comparisons.

```powershell
$snapshotInputs = 'C:\Users\Asus\Downloads\benchmark-local\clearledger-benchmarks\inputs\clearledger-dev'
uv run --frozen python scripts/evaluate_application_snapshot.py --inputs $snapshotInputs --as-of '2026-01-19T12:00:00+05:30'
uv run --frozen pytest tests/test_application_evaluation.py --require-postgres
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

Configure only ignored `TEST_DATABASE_URL` with permission to create/drop owned disposable
databases. Each run creates a new ignored output directory; never point at a full corpus,
benchmark project root, answer directory or source generator. The harness modifies no
benchmark/export files and never pushes. It does not launch the independent scorer.

The first diagnostic run used an invalid evidence-query limit of 100 (API maximum 50),
causing 183 HTTP 422 responses. That client defect was fixed to 50; the known-customer
integration fixture now asserts successful evidence retrieval. The corrected full run
above has 183 successful queries. The diagnostic artifacts remain separate under
`2dc90e433b524a1b81b398c52637ec4b`; its counts/timings are not combined with final results.
No API validator, financial rule, source trust gate or dataset was changed.

Verification: eleven focused harness tests passed (10.58s). The complete frozen regression gate passed **621 tests in 1160.76s**, with no skips
(610 retained + 11 new). All dependency, lint/format, typing, matching-bound and PostgreSQL
migration/integrity checks passed. Log: `local-data/verification/20261025T210932104880Z.log`;
checkpoint provenance is recorded in STATUS.md.
The four applicable isolated restart tests passed (48.87s), using only the runner's
labelled temporary PostgreSQL resources; application/migrations are unchanged by this
task. No required check is silently skipped or claimed complete before execution.

A subsequent portability-only fix makes the runner always perform its first login even
on a machine with under 20 minutes of monotonic uptime. A fake-clock regression test
and the real-API fixture pass. The measured snapshot already authenticated successfully;
no application, matching, extraction or data logic changed. Its exact measured host
source is retained privately as `measured-application_eval_host.py`, matching the hash
in summary.json. The current runner adds only the first-login guard; the captured run's
original source digests and measurements were not rewritten. Full verification is run
against the final runner, not counted from the interrupted pre-fix gates.
