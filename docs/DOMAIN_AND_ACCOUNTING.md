# Financial domain and invariants (normative)

## Definitions
- **Invoice**: gross amount billed, customer, issued date, outstanding balance, lines and optional taxable/GST components.
- **Bank transaction**: imported immutable evidence of money movement, with UTR/statement identity.
- **Receipt**: recognized amount of cash available to apply against AR, with a unique source bank transaction and currency INR.
- **Allocation**: association between receipt amount and customer invoice that reduces unapplied cash and open AR. It has an idempotency key and status; never exceed either available amount.
- **Claim**: customer-asserted deduction or adjustment. A claim is NOT an accepted credit or settlement merely by appearing in a remittance.
- **Evidence**: source document records, version, hash and exact source span; may support, contradict or be insufficient for a claim.
- **Journal proposal**: balanced accounting lines tied to source versions and authorized policy checks; no ledger mutation until accepted by transactionally validated simulated posting.
- **Case**: durable linked investigation over one or more receipts/invoices/claims; remains open while follow-up is required.

## Money
- Persistence: integer paise everywhere. `Decimal` for arithmetic where rates/percentages are involved; quantify with `ROUND_HALF_UP` at defined business-rule boundaries; conversion to integer paise explicit.
- No IEEE floating point in domain or JSON financial calculations. API should use integer paise and optional display-only string format.
- Rates stored as versioned decimals (e.g. `rate_bps` integer if representing basis points); no global TDS defaults.
- No negative receipt/invoice amounts except explicitly modelled reversals/credit notes; V1 can decline unsupported negative cases.

## Balance equations
For each receipt:
`receipt_original_paise = receipt_unapplied_paise + sum(active_cash_allocations_paise)`

For each invoice:
`invoice_original_open_paise = invoice_current_open_paise + sum(active_cash_allocation_paise) + sum(approved_noncash_settlements_paise)`
(assuming no reversals. With reversals, use signed entries and audit-backed compensations.)

Any posted journal:
`sum(debit_paise) == sum(credit_paise)` and every line's `amount_paise >= 0`.

Receipt allocation and journal simulation must commit atomically and be idempotent under retries. Only one current posting per approved proposal version; stale invoice, receipt, document or approval versions invalidate a proposal.

## Chart of accounts (synthetic demo, not statutory)
- 1010 — Bank
- 1200 — Trade AR
- 1310 — Income-tax TDS Receivable (only when supported/approved)
- 1320 — GST-TDS Receivable (only when supported/approved)
- 2300 — Unapplied Receipts Clearing
- 4100 — Sales Allowances (requires separate policy authorization)
- 2110 — Output GST (only under appropriate compliant tax treatment)

## Book bank receipt once
Upon verified bank import / cash recognition, journal A:
Dr Bank 1010 116,500.00; Cr Unapplied Receipts Clearing 2300 116,500.00.

After evidence-backed proposal and authorization, journal B:
Dr Unapplied Receipts Clearing 2300 116,500.00;
Dr Income-tax TDS Receivable 1310 1,000.00;
Cr Trade AR 1200 117,500.00.

Original open AR 120,000.00 -> current open AR 2,500.00. This 2,500.00 is a **disputed receivable**, not a writeoff and not an additional journal debit in this example. Damage claim = uncorroborated and requires evidence/recovery action. Tax validity of 1,000.00 is **stipulated by synthetic fixture only**, not inferred from this example or asserted as universally correct.

## Why journal balancing is not enough
Before posting also validate: customer identity, bank transaction provenance, referenced invoice ownership, tax/allowance approval, evidence version, transaction dates, invoice balance, receipt remaining, proposal revision, actor authorization, not already posted, valid chart of accounts, and aggregate consistency.

## Real company policy vs sample defaults
- No automatic write-offs in V1, regardless of amount.
- All commercial damage, promotion or short-ship adjustments need documentary support and reviewer approval.
- Validated exact matches may be eligible for automatic simulated cash application only under explicit configuration, verified customer and no ambiguous candidate.
- High-value/hard-to-explain cases go to Controller. Thresholds are configurable fictional demo policy, never an Indian legal obligation.
- TDS and GST-TDS route to specialized rule evaluation and unsupported cases to `NEEDS_TAX_REVIEW`.

Milestone 05 stores customer assertions and review progress separately from immutable UNASSESSED hypothesis records. Evidence annotations and matching proposal links grant no settlement authority. Claimed totals may exceed cash and remain distinct from verified settled paise (zero until an authorized later settlement capability). Source changes invalidate review inputs; current APIs cannot accept/resolve deductions or mark cash settled by operator label. See [CASES.md](CASES.md).
