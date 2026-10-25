# Pilot v1.1 compatibility re-evaluation

Executed 2026-10-25 from verified checkpoint `b7ca509` on `test/pilot-v1-1-compatibility`. The [v1.0 report](PILOT_EVALUATION.md) and its source ZIP/results remain unchanged. This report separates the original corpus from the author-controlled supplemental evidence. No application, parser security policy, financial CSV contract, schema, dependency or accounting behavior changed. Milestone 05 has not begun.

## Package, isolation and validation

Successor ZIP: `clearledger_pilot_v1_1_compat.zip`, SHA-256 `26594c6f3ae11916f16aed1577d418e255e18d1e56a9c0ed84361dc85b841f13`. Verified all **271 files / 270 manifest entries / 506582 expanded bytes**, with existing bounded extraction/path/CRC/digest protections. The evaluator's package copy and original ZIP remain byte-identical after application execution. No generator/upgrade script was run, source re-exported, dataset altered or offsets rewritten.

Independent predecessor comparison proves **8 CSVs, 68 canonical sidecars, 2 legacy inventories, business expectations and citation offsets are unchanged**. Exactly 35 PDF byte streams changed, as intended; their source hashes and corresponding 34 PDF citation hashes in the successor agree. Manifest hashes establish consistency, not external authenticity.

The original pinned validator passes. The additional pinned `validate_compat.py` **fails natively on Windows**: its `str(p.relative_to(root))` keys contain backslashes while the manifest uses slashes. The harness retains that failure log. After independently verifying the on-disk manifest, it runs a separately logged evaluator-only adapter replacing exactly that one expression with `.as_posix()`. Every original assertion remains; the packaged validator is unchanged. Adapted validation passes 35 supported-filter/canonical PDFs, 21 positive JSON sources, four negative controls and 25 invoice references. This is **native FAIL / portability-adapted PASS**, not a native success claim or permission to bypass actual integrity failures.

Actual integration used two fresh disposable PostgreSQL databases at migration head 0006 and separate real loopback HTTP API processes. Existing customer/alias/invoice/bank import, duplicate/conflict, exact/advanced matching, tenant/auth, original/hash/span and financial non-mutation probes ran unchanged. Gemini was disabled, credentials/model empty, and daily external budgets zero. Only organization provisioning used direct application writes.

The input boundary now additionally allowlists `COMPATIBILITY_ADDITIONS.json` and declared JSON originals in `compatibility_structured_remittances/`. Hidden targets, canonical/extraction sidecars and package metadata remain outside application inputs. Supplemental processing is uniform and does not branch on hidden labels or positive/negative filenames. Hidden answer files are read only by the evaluator; no target IDs or expected allocations construct runtime attestations. Current local operator labels remain unauthenticated provenance, not external verification or financial approval.

## Original corpus: v1.0 versus v1.1

v1.0 numbers below are the frozen `b7ca509` baseline, not a newly executed baseline. Completed v1.0 API checks were not repeated unnecessarily; predecessor byte comparisons and existing harness regressions protect that boundary.

| Original-corpus measure | v1.0 dev | v1.1 dev | v1.0 eval | v1.1 eval |
|---|---:|---:|---:|---:|
| Financial CSV files / imported rows | 4 / 52 | 4 / 52 | 4 / 39 | 4 / 39 |
| Receipts | 11 | 11 | 10 | 10 |
| PDF READY / canonical-text equal | 0/21 | **21/21** | 0/14 | **14/14** |
| All legacy sources READY | 17/38 | 38/38 | 16/30 | 30/30 |
| Canonical sidecars exactly equal to app text | 13/38 | 34/38 | 10/30 | 24/30 |
| Hidden citation original hashes match | 26/26 | 26/26 | 21/21 | 21/21 |
| Unchanged hidden character offsets match app text | 2/26 | 22/26 | 1/21 | 15/21 |
| Prose extraction requires review | 38/38 | 38/38 | 30/30 | 30/30 |
| Original prose remittance correlation | 10 unresolved | 10 unresolved | 10 unresolved | 10 unresolved |
| Unexpected financial mutations | 0 | 0 | 0 | 0 |

All **35 recompressed PDFs** were actually parsed by the application under the unchanged Flate/ASCIIHex allowlist: **35/35 READY and 35/35 canonical equality**. All **34 cited PDF spans** now match the actual application text at their original offsets. The three text-file citations still match. Total unchanged-pointer compatibility improves **3/47 → 37/47**. Original v1.0 ASCII85 PDFs remain retained as negative compatibility fixtures; no decoder/filter expansion occurred.

Financial results remain the baseline: independent subset oracle 11/11 dev and 10/10 eval; multi-invoice candidate recall 4/4 and 2/2. Exact recall without intent remains 0/3 per split; with separately simulated source-backed memo attestations it is 3/3 per split. Zero false supported matching proposals. Supplemental UTR association does not create matching evidence, resolve payment intent, change customer identity or settle any invoice.

## Remaining email offsets: measured from application output

All ten EML bodies match the old body-only canonical sidecars **exactly**. The actual `/documents/{id}/text` output contains a subject prefix absent from those sidecars:

| Actual observation | Dev | Eval |
|---|---:|---:|
| Emails / exact body matches | 4/4 | 6/6 |
| Direct complete canonical equality | 0/4 | 0/6 |
| Measured body start in app text, Unicode characters | 55 for each | 56 for each |
| Unchanged email citation spans valid directly | 0/4 | 0/6 |
| Measured unique-quote position difference | +55 for each | +56 for each |

The evaluator locates the unique complete body and exact citation quotes in **actual app-produced text**; it does not guess the subject, invent positions or assume bytes equal characters. Private diagnostics record measured character and UTF-8 byte starts. These prefixes happen to be ASCII; future Unicode subjects require measuring both independently. An ambiguous or missing body yields no inferred mapping, covered by unit tests.

The old pointers were not changed, rebased in the package, submitted as corrected evidence, or relabeled compatible. The remaining **10/47 failures are exclusively EML pointers**. Any successor citation export must use the actual versioned application canonical text and explicitly reviewed new pointers. The observed +55/+56 values are diagnostic measurements for these files, not a general offset rule.

## Supplemental JSON: separate evidence and correlation measurements

These 25 sources were authored using previous benchmark knowledge and intentionally extend the available evidence. They are **not** an independent prospective held-out semantic benchmark and must not improve the reported v1.0 baseline retrospectively.

| Supplemental measurement | Dev | Eval | Total |
|---|---:|---:|---:|
| JSON uploads / deterministic SUCCEEDED extraction | 13/13 | 12/12 | **25/25** |
| Source-backed extraction spans verified by API | 26/26 | 22/22 | **48/48** |
| Invoice-reference agreement with sealed source assertions | 13/13 docs | 12/12 docs | 25/25 docs |
| Without attestation: CANDIDATES / UNRESOLVED | 11 / 2 | 10 / 2 | 21 / 4 |
| Without attestation: LINKED | 0 | 0 | **0** |
| Correct links after explicit simulated UTR attestation | 11/11 | 10/10 | **21/21** |
| Negative controls remain UNRESOLVED | 2/2 | 2/2 | **4/4** |
| Incorrect links | 0 | 0 | **0** |
| Attestation not equal to extracted source: HTTP 422 | 13/13 | 12/12 | 25/25 |
| Missing expected version on link: HTTP 409 | 11/11 | 10/10 | 21/21 |
| Stale expected receipt version: HTTP 409 | 11/11 | 10/10 | 21/21 |

Each document's original bytes/digest, deterministic reference values and exact returned source spans were checked against the actual API. Both negative controls per split (unknown UTR and no UTR) abstain even after an explicit attestation attempt. Every final correlation passes same-key and fresh-key replay equality checks (50 replays). Expected-version rejection tests do not alter balances to manufacture staleness. Existing owner/conflict/tenant regressions remain; this supplement adds no new wrong-owner scenario and does not independently establish coverage of all such cases.

Attestations use only extracted UTR literals and publicly imported bank/receipt version lookups, with explicit local operator provenance. A correct UTR identifies the receipt, not authenticity, invoice allocation, legitimate deductions or posting authority. This includes an ambiguous-allocation receipt and a separate unknown-payer duplicate credit: UTR association can be valid while financial matching still abstains. Original invoice/receipt balances, statuses, versions and customer/alias/bank records remain unchanged.

All 93 originals (68 legacy + 25 supplements) are retained. All legacy application-generated page spans and all 48 supplemental extraction citations are source-consistent; fabricated legacy page quotes remain rejected. JSON successes retain `requires_human_review=true`, `financial_authority=false` and unverified authenticity. There are no claimed deduction-amount results: these supplements have empty claims. No Gemini, OCR, semantic-model accuracy, tax adjudication, case lifecycle, approvals or posting is being measured.

## Performance, verification and reproduction

Application-phase run `58f8acde007249dba9975741b793c50f`: dev 799 timed primary requests / 43.554s / p95 427.967ms; eval 683 / 36.360s / p95 428.092ms. Evaluator peak Python-traced allocation: 23009259 bytes (~21.94 MiB), excluding API/parser/PostgreSQL RSS. This larger request set includes supplemental probes; it is not an apples-to-apples speed comparison with v1.0. No large-scale, system CPU/peak or provider benchmark is claimed.

Completed expensive application observations were preserved and reused for final **evaluator-only** citation diagnostics and predecessor comparison, instead of starting duplicate databases/processes. `summary-verified.json` and `evaluator/details-verified.json` are new private outputs; earlier observations/reports remain unchanged. Application code did not change between capture and final scoring. Zero financial mutations, external attempts/reservations/transmissions or recognized-identifier projection leaks were observed; privacy probes can safely abstain and are not proof of real-data anonymity.

Reproduce a fresh complete run from repository root with both original ZIPs present:

```powershell
uv run --frozen python scripts/verify_pilot.py --archive local-data/pilot/clearledger_pilot_v1_1_compat.zip
uv run --frozen python scripts/verify.py
uv run --frozen python scripts/verify_isolated_restart.py
```

TEST_DATABASE_URL must reference a local CREATEDB role via ignored configuration. Only UUID-named disposable databases and owned restart resources are created/removed; shared development data is not upgraded, reset, downgraded or restarted. Version-specific validators remain hash-pinned; changing their executable content requires review. Windows adapter outputs are outside the immutable package directory. Detailed outputs stay under ignored `local-data/pilot-runs/58f8acde007249dba9975741b793c50f/`; API observations, hidden target details, original sources and fixture-bearing logs are excluded from Git.

Verification: **347 passed** in 128.48s (all 337 regressions plus ten compatibility tests); lock/dependencies/Ruff lint+format/nine strict typed modules/matching bounds/PostgreSQL migration roundtrip/drift/integrity PASS. Targeted harness tests: **46 passed**. Isolated owned-container restart: **2 passed** in 8.62s. Both full/restart suites retain the existing Starlette/HTTPX deprecation warning; no tests skipped/weakened. Logs: `local-data/verification/20261025T031638842859Z.log` and `local-data/verification/isolated-restart-20261025T031637899348Z.log`. See STATUS for checkpoint.

The native Windows validator defect and ten EML offsets remain explicit compatibility limitations. Free-form semantic extraction, production authentication/isolation, live provider/privacy/terms, full blind/large-scale Argon evaluation and future accounting/case workflows remain unverified or not implemented. STOP before milestone 05.
