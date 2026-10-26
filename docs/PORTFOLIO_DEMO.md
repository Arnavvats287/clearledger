# Reproducible accountant handoff

This is a local, offline walkthrough of real API routes and the production graph,
backed by disposable PostgreSQL. FastAPI TestClient executes the application stack
in process; this is not a deployed HTTP server, frontend, mocked API or live LLM demo.

## Run

Install the frozen development environment, configure ignored TEST_DATABASE_URL
for a local PostgreSQL role with CREATEDB, and ensure PostgreSQL is running:

```powershell
uv sync --frozen
uv run --frozen python scripts/portfolio_demo.py
```

No Gemini key, external account or benchmark package is needed. The launcher clears
its child key and forces extraction disabled/external AI false and the deterministic
Investigator. It creates only generated test databases, upgrades those to migration
head and cleans them up. It never resets, downgrades, seeds or restarts development.
Detailed Windows setup is in the root README. Never commit .env or real documents.

## Acceptance proof: one continuous case

`test_complete_accountant_review_workflow` first passed independently in **8.70s**,
before README replacement. It proves the requested sequence in one isolated company
and database with explicit expected outputs, using small variants of existing code
fixtures. No realistic dataset is generated. All business inputs go through APIs;
test setup only provisions the organization/local access and explicit test trust root.

| Step | Actual interface / expected result |
|---|---|
| Import | POST /imports/customers, /invoices, /payer-aliases, /bank-transactions; receipt created automatically |
| Financial inputs | Invoice i: 1,101 paise outstanding; receipt t: 1,000 paise unapplied |
| First candidate | POST /receipts/{id}/match-advanced: UNRESOLVED; no selected allocation without verified intent |
| Explicit test intent | POST /receipts/{id}/matching-evidence: source-backed invoice-reference attestation, not inferred from memo equality |
| Candidate reconciliation | match-advanced: UNIQUE; 1,000 paise cash candidate, zero remaining cash, 101 paise residual AR, verified reference pointers |
| Remittance | POST /documents and /extract, allow_external=false: DETERMINISTIC/SUCCEEDED, rebate assertion 101 paise; SHA-256 checked |
| Correlation | POST /documents/{id}/correlate with explicit test UTR attestation: LINKED to the same receipt |
| Persistent case | Real outbox processing; canonical case contains the same receipt, invoice, document and 101-paise claim |
| Source evidence | POST /evidence/records: test-signed PROMOTION, 101 paise; exact source/hash/span/customer/date checks remain active |
| Investigation | POST /cases/{id}/investigations; existing outbox lease and real LangGraph executor; GET run/findings/trace |
| Accountant output | SUPPORTED source predicate; HUMAN_REVIEW; same case AWAITING_REVIEW; one citation to the registered promotion |
| Safety | Actual AR remains 1,101 paise, cash remains unapplied 1,000 paise, verified settlement remains zero |

The residual is a **proposed** remaining balance after cash application, not an
already-posted invoice balance. The supported source predicate is not legal or
financial approval. Accountant action: inspect the cited promotion and 101-paise
claim, then use a separately authorized approval process if appropriate. That
process is not invoked or represented as successful by this demo. No customer
message or financial operation is sent.

Test publisher signatures and UTR/intent attestations are explicitly synthetic
inputs. They do not authenticate a real bank/customer or authorize finance. The
Director and Investigator are deterministic; model-generated reasoning is not claimed.

## Additional verified controls

- Matching abstains before test attestation and creates an exact proposal afterward;
  idempotent replay returns the same result.
- Structured extraction preserves originals, raw/canonical hashes and four source
  spans verified through the real verify-span API.
- Invoice, bank and alias rows link to the actual four import records. Import audit
  events, document events, case history and graph trace are read back through APIs.
- Missing promotion → INSUFFICIENT_EVIDENCE / REQUEST_EVIDENCE, no citation.
- Conflicting promotions → INSUFFICIENT_EVIDENCE / REQUEST_EVIDENCE, two opposing
  citations. Signed support → SUPPORTED / HUMAN_REVIEW, one citation.
- Every scenario compares full financial API snapshots before and after and asserts
  human review plus no financial authority. The finance identity verifier is absent.

These supplemental controls use separate disposable cases; they are not spliced
into the primary workflow. The final command ran **5 tests in 37.35s**, all passed.
Output is in ignored `local-data/portfolio-demo-final.log`; structured synthetic
observations are in `local-data/portfolio-demo/{accountant,ingestion,supported,missing,conflict}.json`.
Timing is one local measurement, not a performance guarantee.

## What remains missing or unverified

There is no broken step in the demonstrated chain **through human review**. There
is also no evidence here of approved settlement, real-customer/source authenticity,
production identities, autonomous narrative reasoning or broad reconciliation
usefulness. Approval/posting are deliberately outside this walkthrough and remain
gated; a reviewed source fact cannot substitute for authority.

The independent development evaluation reports conditional matching recall 0/315
and review-routing score 0/255 despite 255 completed stages, full snapshot coverage
and zero API-error observations. Those results were supplied by the operator/user;
this pass did not access/rescore frozen artifacts. The tiny walkthrough proves
selected capabilities and regression expectations, not benchmark quality.

At the portfolio checkpoint two real Gemini attempts had failed, latest HTTP400.
A separately authorized third attempt later failed at CONTENT_GENERATION /
HTTP_API / HTTP503 / UNAVAILABLE; neither the earlier rejected field nor live LLM
accuracy is established. The offline portfolio demo itself makes no external calls.
DocILE/ContractNLI, sealed blind evaluation and real-customer validation remain
future/unverified work. See README for limitations and the full contracts.
