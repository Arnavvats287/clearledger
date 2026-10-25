# Independent pilot evaluation - Milestone 04C

Executed locally on 2026-10-25 from verified checkpoint `f2f71fe`, on branch `feat/milestone-04c-pilot-evaluation`. **Financial import/matching integration and safety checks pass; document interoperability has material gaps.** This is a small deterministic pilot, not the full milestone 11 benchmark or production-readiness evidence. No application feature, accounting behavior, schema, dependency or financial CSV contract changed.

## Package and method

Input: ignored `local-data/pilot/clearledger_pilot_v1.zip`, SHA-256 `438fbedcce8016fa0aaead3910876b8fb9e2b6f1dd41406db8c0ec5829855927`. All **238 files / 237 manifest entries / 458956 expanded bytes** verified, including exact manifest coverage and CRC/digests. These prove internal consistency, not a trusted external signature. Original ZIP and extracted evaluator copy remained byte-identical after execution. Nothing was regenerated, downloaded or edited.

The supplied validator was inspected (read-only, no generator imports/external operations), pinned by SHA-256 and independently executed with `--root`. It reports PASS: 20 cases, 22 stages, 68 sources, 47 citations and 73 chronology events. Its fixed-seed reproduction check is **NOT TESTED** without a comparison directory; the generator's reported reproduction is not independently claimed. Arithmetic checks on hidden journals are dataset validation, not application posting verification.

The harness first inspected actual interfaces/schema, then migrated **two fresh disposable PostgreSQL databases to 0006_provider_budgets**, one per split. Financial data entered through real HTTP import APIs; only organization provisioning used direct writes. Separate Uvicorn processes received database/company/local-token configuration and original document bytes, never the ZIP, hidden directory, answers, sidecars, scenario labels or scorer objects. Four CSVs and allowlisted original sources were copied to a distinct application-input boundary. Only after both API processes stopped and databases were removed did the answer-only scorer load hidden truth.

This is enforced dataflow separation, not a new OS-principal sandbox. The trusted evaluator can read answers; a compromised host administrator remains outside existing isolation guarantees. The developer inspected answer schemas to implement scoring; this is not claimed to be a prospectively blind study. No model, extraction sidecar, answer key or invoice-allocation truth was used to construct runtime evidence.

Two matching modes are reported separately:

- **Unattested:** imported verified-alias assertions establish local identity where supported; memo text alone never supplies verified intent.
- **Simulated attested:** a separately labeled local operator policy attests exact delimited memo invoice references only where an imported alias maps to the same invoice owner. It creates auditable source-row/span/version evidence through the existing API: 12 dev / 10 eval attestations. This is conditional API evaluation, not naturally discovered verification or external authority. Missing/unknown identity and missing references remain unattested.

All financial CSVs are bulk opening snapshots. Document uploads follow public inventory availability order, and document-list checks exclude not-yet-uploaded future sources. Hidden stage dates are used only by the scorer to check citation availability. This does **not** simulate a temporal ledger, settlement, stage-2 accounting or a case/event engine. Those capabilities remain future work.

## Actual coverage and import results

| Measure | Development | Supplied held-out evaluation |
|---|---:|---:|
| Cases / stages | 11 / 12 | 9 / 10 |
| Customers / payer aliases | 11 / 11 | 9 / 9 |
| Invoices / bank transactions / receipts | 19 / 11 / 11 | 11 / 10 / 10 |
| Valid CSV files / rows imported | 4/4 / 52 | 4/4 / 39 |
| Valid import failures | 0 | 0 |
| Same-key + fresh-key file replays | 8 | 8 |
| Single-row duplicates: zero insertions/new receipts | 11/11 | 10/10 |
| Conflicting bank payloads: atomic HTTP 409 | 11/11 | 10/10 |
| Extra-header requests: HTTP 422 | 4/4 | 4/4 |
| Source documents retained | 38 | 30 |

The four CSV schemas are compatible with DATA_CONTRACT v1.0. Alias verification fields remain synthetic supplied assertions under existing local provenance semantics, not authenticated external proof. The extra distinct-UTR payment remains a separate unapplied receipt; replay never creates another receipt. Generic duplicate/+1-paise conflict probes derive only from visible bank rows in memory. The evaluator independently confirms they cover the provided hidden negative fixture without passing that fixture into the application.

There were **84 primary exact/advanced matching evaluations and 168 matching replays** across both modes. Same-key and different-key repeats return identical immutable proposals. Original customer/alias/invoice/bank/receipt rows, including every balance/status/version, remain unchanged. Rejected imports likewise preserve financial snapshots.

## Matching outcomes

Numerators/denominators are explicit; an empty supported-output denominator is N/A, not perfect precision. Candidate recall measures review hypotheses, not cash application. Exact targets below are hidden expected single-invoice cash allocations equal to the opening invoice and receipt balances.

| Metric | Dev unattested | Eval unattested | Dev simulated attested | Eval simulated attested |
|---|---:|---:|---:|---:|
| Exact full-balance target recall | 0/3 | 0/3 | 3/3 | 3/3 |
| Wrong exact supported proposals / supported | 0/0 (N/A) | 0/0 (N/A) | 0/3 | 0/3 |
| Wrong advanced supported proposals / supported | 0/0 (N/A) | 0/0 (N/A) | 0/9 | 0/8 |
| Expected cash allocation in candidate list | 7/10 | 5/9 | 10/10 | 8/9 |
| Expected cash allocation in candidates or partial analysis | 10/10 | 9/9 | 10/10 | 9/9 |
| Multi-invoice expected candidate recall | 4/4 | 2/2 | 4/4 | 2/2 |
| Required abstentions correct | 1/1 | 1/1 | 1/1 | 1/1 |
| Competing-subset detection | 1/1 | N/A: no such eval case | 1/1 | N/A |
| Independent exhaustive subset oracle | 11/11 | 10/10 | Not applicable to reference-scoped mode | Not applicable |

Zero unattested exact recall is the expected safety gate: the application does not promote literal memo text into verified intent. Mathematical uniqueness also remains review-only. The single attested-mode eval candidate-list miss has no attested memo reference and remains partial analysis, not an invented deduction or supported allocation. No incorrect supported match was observed among **23 supported proposals** across the two algorithms; this small conditional denominator does not establish real-world precision.

| Scenario family, measured at receipt level | Dev receipts | Eval receipts | Result |
|---|---:|---:|---|
| Single invoice / ordinary partial | 4 | 2 | Expected cash found with simulated intent; unattested partials abstain |
| Explicit multi-invoice | 3 | 2 | Expected candidate combinations found; intent only in attested mode |
| Unique subset without references | 1 | 0 | Unique mathematical candidate; no fabricated intent |
| Competing subsets | 1 | 0 | Multiple candidates and abstention, never arbitrary selection |
| Claims requiring future adjudication | 2 | 4 | Cash/partial hypotheses only; tax/claim legitimacy NOT IMPLEMENTED |
| Distinct duplicate payment | 0 | 2, from one case | First conditional proposal; unknown-payer second receipt abstains |

The dataset contains 12 curated and 8 ordinary cases. Tax, discount, damage and injection investigations are included for current cash/proposal safety only. Their expected noncash adjustments, final account balances and approvals are **NOT IMPLEMENTED / NOT EVALUABLE**, not incorrect application predictions.

## Document outcomes and compatibility blockers

| Measure | Dev | Eval |
|---|---:|---:|
| Sources parsed READY | 17/38 | 16/30 |
| HTTP 422 / PARSE_FAILED, original preserved | 21 | 14 |
| Extraction NEEDS_REVIEW, no semantic facts | 38/38 | 30/30 |
| Exact canonical sidecar equality | 13/38 | 10/30 |
| Hidden citation original hashes match | 26/26 | 21/21 |
| Hidden citation offsets directly match application text | 2/26 | 1/21 |
| Hidden citation quote occurs uniquely in application text | 6/26 | 7/21 |
| Citation available by its declared stage | 26/26 | 21/21 |
| Application-generated spans verified / forged quotes rejected | 17/17 each | 16/16 each |
| Remittance invoice-reference recall | 0/11 | 0/12 |
| Same recall on parseable remittances only | 0/7 | 0/8 |
| Receipt-correlation outcomes | 10 UNRESOLVED | 10 UNRESOLVED |

1. **PDF filter incompatibility:** all 35 PDFs use `/ASCII85Decode /FlateDecode`; the published parser contract allows Flate/ASCIIHex only. Originals/hashes and controlled failures persist, but text is unavailable. Security limits were not relaxed and originals were not re-exported. This is a declared format incompatibility, not a silently repaired successful parse.
2. **Email canonical contract mismatch:** all 10 emails have body-only pilot canonical sidecars. ClearLedger includes the subject prefix; after removing that prefix diagnostically the bodies match exactly. The pilot's `clearledger-canon-v1.0` offsets cannot be used unchanged as application `canonical-text-v1` offsets. No answer spans were rebased, fed into APIs or used to inflate scores. Only 3/47 pointers transfer directly.
3. **No deterministic structured remittances:** pilot prose is outside the strict JSON/line grammar. All 68 baseline extraction runs abstain for review, including parse failures. Reference recall is zero; precision and real semantic-provider accuracy are **NOT EVALUABLE**. No fake-provider result is reported as real extraction accuracy.
4. **No exact bank UTRs in remittances:** none of the 20 source remittances contains an imported bank transaction's exact external ID. Current correlation requires source-backed extracted UTRs and explicit attestation; invoice/customer similarities and hidden case associations cannot replace that evidence. No correlation target is evaluable under that contract (0 eligible UTR targets), and no link was manufactured.

For a compatible successor package, Argon would need to publish supported source formats and canonical pointers explicitly aligned to the application, plus actual source UTRs where correlation is intended. Optional deterministic remittance JSON is already documented separately from CSV v1.0. Such a successor must be versioned independently; no original files were changed here. A broader PDF decoder or live semantic provider would require separately reviewed work/authorization, not weaker evaluation gates.

## Security, resource use and verification

No external provider/Gemini key or paid request was used. API processes force provider disabled, external calls false, empty model/key and zero daily budgets; provider-reservation tables remain empty. Explicit external-opt-in probes yield 33 BLOCKED outcomes and 35 no-text NEEDS_REVIEW outcomes, with zero attempts. All extraction envelopes require review and confer no authenticity/accounting authority. The supplied injection investigation never causes tool execution, accounting approval, writeoff or balance mutation. Existing adversarial fake-provider regressions remain in the full gate; real-provider injection accuracy is unverified.

Independent recognizable PAN/GSTIN/IFSC/email projection probes cover all 33 parseable sources: 24 projected, 9 safely abstained, zero recognized identifiers surviving projection. The 35 unparsed sources are not counted as privacy-tested text. No arbitrary real-data anonymization claim is made. Missing document auth fails 401 in each split; four foreign-company receipt/invoice/document/original reads per split fail 404. Hidden/sidecar/path/symlink/manifest controls and scorer failure denominators have minimal isolated unit tests. Unexpected financial mutations: **0**; unsupported financial posting: **not present**.

Standalone pilot measurement, before concurrent verification workloads:

| Measure | Dev | Eval |
|---|---:|---:|
| Timed primary API requests | 600 | 507 |
| End-to-end application phase | 33.855 s | 27.577 s |
| Request p50 / p95 / max | 17.089 / 424.722 / 547.131 ms | 16.672 / 426.404 / 547.391 ms |

The trusted evaluator's peak Python-traced allocation was **21257781 bytes (~20.27 MiB)**. It excludes API/parser process RSS, PostgreSQL memory, allocator overhead and OS caches; total system peak/CPU were not measured. Four additional foreign-scope reads/split and a direct auth probe are outside the primary request timing count. Workloads are small (maximum four invoices per customer); these measurements are not large-pool capacity or real-provider latency/cost benchmarks. Existing search/resource hard limits remain unchanged.

Reproduce from repository root, with the original ZIP at the path above and ignored `.env` containing TEST_DATABASE_URL for a local CREATEDB role:

```powershell
uv run --frozen python scripts/verify_pilot.py
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

The pilot command independently runs the pinned validator, creates/removes only UUID-named `clearledger_pilot_*` databases, uses separate local source storage and saves detailed results under ignored `local-data/pilot-runs/<run-id>/`. No shared development migration/reset/downgrade/restart occurs. Package contents, observations, hidden details and fixture-bearing logs stay out of Git. CI/full regression tests need no pilot ZIP: they use minimal harness fixtures.

Full verification: **337 passed** in 134.92 s (all 301 regressions plus 36 harness tests); lock/dependencies/Ruff lint+format/9 strict typed modules/matching bounds/PostgreSQL migration roundtrip+drift/integrity PASS. Separate owned-container restart: **2 passed** in 8.72 s. Both runs retain the existing Starlette/HTTPX deprecation warning. Development head remains 0006; no pilot databases remain. Logs: `local-data/verification/20261025T013247119424Z.log` and `local-data/verification/isolated-restart-20261025T012516905321Z.log`. See STATUS for the Git checkpoint.

Standalone measured pilot run: `909833d8bc0e41e499b893692adae225`. Final stricter Windows-path recheck: `684fa94997e14a8f829e502de6c1259a`, with identical aggregate outcomes; latest command log `local-data/pilot/verified-integration.log`. The recheck ran alongside verification; performance figures above remain those of the standalone run. Its `summary.json` contains aggregate metrics, `application-output/*/observations.json` contains actual responses, and `evaluator/details.json` contains private per-scenario comparisons. Earlier private attempts exposed an overstrict harness assumption about PDF success and a scorer misunderstanding of primary versus additional receipt keys; both were corrected without modifying product code or weakening existing tests.

Full benchmark scale, prospectively blind evaluation, remote CI/Linux execution, production actor authentication/isolation, human review effort, live model/privacy/provider terms, tax adjudication, cases/approvals/posting and A/B/C investigator ablations remain deferred. Pilot coverage does not close those requirements. STOP after 04C.
