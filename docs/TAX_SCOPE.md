# Indian tax rule scope — conservative specification

This is a simulated finance product and NOT a legal/tax opinion. Indian law, transaction categories, deduction timing, evidence and filing forms can be complicated and change. Do not assert broad rules in code from examples. Use a specialist-reviewed versioned rule registry before any claim of production accuracy.

## V1 supported semantics
- Tax claims are extracted as customer assertions, not automatically approved deductions.
- Tax rules are records with `jurisdiction`, `provision`, `transaction_category`, `effective_from`, `effective_to`, `basis`, `rate`, `threshold`, `date_of_deduction`, `eligibility_preconditions`, `required_evidence`, `source_url`, `verified_by`, `verification_date`, and `version`.
- If the system cannot establish which rule applies, category, threshold, date, supply configuration or evidence, outcome MUST be `NEEDS_TAX_REVIEW`.
- For initial demo, use a synthetic tax claim marked `approved_fixture=true` to test ledger mechanics, without claiming automatic legal determination.
- Only implement a narrow set of reviewed rule cases later, with scenario-level tests for thresholds, effective dates, GST separation conditions, prepayment vs credit, and deductor eligibility.
- Income-tax TDS and CGST Section 51 GST-TDS must be separately modeled with distinct receivable accounts and conditions.
- A tax receivable requires a chosen recognition policy and supporting evidence. Excess claimed withholding must not be quietly classified as invalid customer damage/discount chargeback; direct uncertain handling to review. Do not automatically imply that excess tax withheld is recoverable directly from customer.
- GST credit notes/output tax reversals require their own approval/documentation workflow outside V1.

## Verified references to consult and date-stamp before coding legal rules
- Income Tax Department official documentation and current Income-tax Act provisions (including post-April 2026 provisions as applicable).
- Central GST Act Section 51, Section 34, official CBIC GST guidance on GST TDS and tax credit notes.
- Any source rules must be captured as reviewed references, not interpreted by the LLM during posting.

## Scope decision
Milestone 08 must demonstrate correct **conditional processing and abstention**, not a complete Indian tax engine. Never silently use universal 2% TDS or blanket `base_value * rate` assumptions.

Implemented M08 rules bind exact fixture IDs/amount/dates/recognition policy/evidence;
reviewer, verification date and version come from immutable authenticated policy review.
Rates, thresholds and source_url are explicitly null for this stipulation mechanism.
Fixture flag/source signature alone is insufficient: source/rule checks and separate
maker-checker approval remain mandatory. Unknown/nonfixture/excess/contradictory tax
stays NEEDS_TAX_REVIEW. Income-tax/GST-TDS accounts remain distinct; GST credit notes
and output reversals are unsupported. No legal compliance is claimed. Exact registry:
[ACCOUNTING_SIMULATOR.md](ACCOUNTING_SIMULATOR.md).
