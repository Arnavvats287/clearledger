# Canonical source grounding — version 1

This is an additive final hardening pass, authorized after the immutable Phase2 v1
baseline. It changes source selection and citation construction, not financial
authority, legal policy, role verification, matching, outbox delivery or accounting.
No database migration, service, vector index, Redis or new graph is introduced.

## Shared representation

`source_spans.py` defines frozen `Source`, `Page`, `Token`, `Span` and `Fallback`
records. A span contains source ID/hash/version/kind, one-based page, exact Unicode
character interval/text, OCR token IDs, optional token-union box and reading order.
IDs bind those immutable inputs with a 128-bit SHA256-derived identifier; original
source hashes remain full SHA256. Different occurrences and different source or
tenant namespaces have different IDs, even when their text is identical.

`Source.resolve` requires the expected hash/version, rejects unknown IDs and
recomputes the pointer against immutable page/token contents. A digest proves
integrity, not authorship, legal authenticity or financial authority. Product
callers still validate originals, tenant, document version, chronology, authenticated
manifests and case scope through the existing document/evidence services.

For extraction, the trusted host supplies company/document identity and original
canonical hash/version. The provider sees the existing length-preserving privacy
projection. Selected offsets resolve against that exact projection, then the
unchanged private restore/source-semantic checks recheck original text. Evidence
catalogs use company/document/record namespaces and only previously authenticated,
current, integrity-checked, privacy-filtered evidence. There is no global ID lookup
that bypasses access control.

## Candidate-first extraction

`source_candidates.py` discovers explicit invoice/document/bill labels, same-line
and adjacent-line values, exact multi-token values and invoice-like patterns.
It preserves punctuation, leading zeroes and internal spaces. Discovery favors
recall; nearby dates/account-like strings can be candidates, not verified IDs.
Each candidate already points to a concrete source occurrence. Selection accepts
only offered IDs or an empty list; the model cannot invent a value or location.

Known non-invoice document headings are rejected by source-only admission. UNKNOWN
is distinct from OUT_OF_SCOPE. The evaluation's single bounded request includes
typed document classification; NON_INVOICE/UNKNOWN cannot emit IDs. Remittance
reference discovery is a separate purpose: an invoice reference in a payment note
does not make the note an invoice, establish payment intent or verify a payer.

The configured product gateway uses `remittance_grounded` and the provider-only
`RemittanceSelection`/`ClaimSelection` schema. Invoice references are candidate IDs;
claim descriptions, amounts, explicit reason codes and UTRs reference supplied
span IDs. The resolver constructs the existing strict `Extraction`/`Span` DTOs.
All original amount/category/label/delimiter/reason-code/source checks still run.
Dispute status is not a reason code. Payer hints remain unverified and optional.

The historical explicit `remittance` adapter and v6 decoder remain available for
legacy fixtures/records; the configured production path uses the grounded mode.
Its cache identity is `grounded-remittance-1`, preventing old free-location results
from masquerading as grounded selections. Existing successful facts are not edited.
Grounding IDs/source hash are retained in extraction metadata. Financial CSV1.0
and the public document span/financial APIs remain unchanged.

## Retrieval and investigation

`source_retrieval.py` performs bounded BM25-style lexical scoring, character-trigram
similarity, strong exact identifier/numeric weighting and adjacent context retrieval.
Relevance is candidate discovery, not proof. Financial values are never computed
using ranking floats; existing paise and source-fact comparisons remain exact.

`investigation_grounding.py` projects existing verified evidence into the same
span representation before synthesis. The live v3 schema asks for span IDs; the
host checks ownership of selected IDs and equality with the cited verified records.
The existing verifier independently controls amounts, required record types,
currentness, contradictions and allowed conclusions. A model cannot turn missing
proof into contradiction or override that verifier. Invalid selections fall back
to existing insufficient-evidence/human-review semantics.

`Synthesis.evidence_span_ids` has an empty legacy decoding default; the configured
live provider schema requires it and cited records require matching spans. Old
immutable traces remain decodable. `ar-investigator-v3` invalidates incompatible
provider caches/configuration reuse. No existing history is rewritten.

Production graph shape is unchanged: Director route → plan → evidence tool →
evidence verify → synthesis → policy → human review/request/escalation. No hidden
chain-of-thought, write capability, second director or automatic approval is added.
Source-grounded support still requires human review and has financial_authority=false.

## OCR and bounds

`source_ocr.py` keeps valid source words and coordinates, records malformed-word
or geometry fallback provenance, and leaves missing geometry as None. Empty or
partially unusable pages remain explicit. A caller may provide an already verified
alternative text layer; the Phase3 preparer tries the existing bounded, isolated
PDF parser when appropriate. Its original PDF digest is recorded separately.
Text-layer recovery never fabricates OCR boxes. With no trustworthy text, abstain.
No source files, OCR originals, parser security filters or old failures are repaired.

Limits include 200 pages, 500,000 source characters, 60,000 OCR words, 10,000 base
spans, bounded identifier discovery and configurable candidate/retrieval limits.
Discovery exhaustion is reported, not proof of completeness. Token indexes avoid
repeated full-page scans. Model token-count admission and existing process/deadline
controls remain. Phase3 caps invoice candidates at64, with exact source resolution
and unchanged per-request input/output ceilings; overflow/missing coordinates are
reported rather than rescued using annotations.

## Verification and limitations

`test_source_grounding.py` covers stability, stale/unknown IDs, duplicate values,
boxes, labels/adjacent lines, multi-token IDs, admission, exact numerics, explicit
conflict versus missing proof, OCR fallback and provenance. Property tests preserve
integer atoms. `test_phase3_grounding.py` exercises the real isolated worker with
mocked transport, selection gates, scorer denominators and isolated SDK startup.
Actual PostgreSQL/API tests in `test_grounded_extraction_api.py` and
`test_grounded_investigation_api.py` verify valid/forged IDs, strict amount checks,
authenticated support, human-review/fallback and financial non-mutation.

Legacy rehearsal responses are updated to include offered IDs; existing assertions
remain. All previous financial/security/evaluation tests are retained. Observed
commands/results belong in STATUS and the Phase3 report, not inferred from this design.

Lexical gates cannot universally prove natural-language legal entailment. External
ContractNLI remains evaluation-only legal reasoning; product factual authority still
requires authenticated typed source predicates. New metrics must disclose policy
abstention, source/coordinate limitations, model failures and held-out target misses.
No production readiness or AR accuracy is inferred from either public dataset.

## Development correction — 2026-11-06

New modules compose these original types without editing frozen Phase3 code.
`source_aliases.py` binds request names to canonical source/hash/version pointers;
unknown/colliding/stale mappings fail closed. `source_presentations.py` gives the
existing isolated remittance/AR provider short IDs and restores canonical IDs before
unchanged strict source/amount/financial validation. AR internal contract remains v3;
the Gemini configuration separately versions presentation, preventing stale cache
reuse without rewriting old traces. Remittance provider/cache identity advances to
grounded-remittance-2-aliases. Public financial/document DTOs and graph shape stay.

`source_semantics.py` supplies legal sentence/clause/list fragments, source section
context and lexical/defined-term retrieval. Source separators remain represented;
coverage metrics are not relaxed to conceal whitespace gaps. Legal evaluation
policy is `external_eval/accuracy_nli.py`: independently typed items and provenance,
actual-request membership, exact numerics and explicit support/conflict relation.
Lexical ranking does not authenticate source or veto legal paraphrases. It does not
replace the product's stronger authenticated relational/financial fact predicates.

`source_invoice_candidates.py` is an opt-in development invoice policy over the
same occurrence types: geometric labels/header candidates, bounded internal pool,
explicit punctuation/adjacent-token joins and compact occurrence aliases. Raw span
text/tokens and exact boxes stay unchanged; transformed candidate values are explicit
source-derived candidates, not a relaxed scorer normalizer or financial import rule.
No coordinates are invented. Invoice development changes are not silently applied
to financial CSVs or production remittance value acceptance. Oracle-only discovery
markers are excluded from all provider tables to keep oracle selection blinded.
Report/limits: FINAL_ACCURACY_DIAGNOSTICS.md.
