# PROJECT_SPEC — ClearLedger V1

## Customer and problem
Customer: finance/AR analysts and controllers at a mid-sized Indian B2B industrial supplies distributor. Bank payments often lack invoice references; customer remittance may arrive later and may list tax withholding, damage, short shipment, promotional allowances, early-pay discounts, or unexplained deductions. Analysts must reconstruct the facts and correctly account for every rupee.

## One-sentence outcome
Given a bank receipt and its available documents, ClearLedger shows which invoices it can safely settle, which amounts remain unsupported, what evidence supports each claim, what the analyst should do next, and a balanced, auditable **simulated** journal proposal.

## Actors
- AR Analyst: imports, investigates, requests customer evidence, submits proposals.
- Controller: approves restricted adjustments and posting proposals; cannot approve own restricted proposal.
- Auditor/Read-only: views source evidence, journal lines and event history without mutations.
- System Worker: runs deterministic matching and bounded investigations under least privilege.

## Workflows required
1. Import customer/invoice data and bank CSV; prevent duplicates, identify payer conservatively.
2. Match uniquely supported receipts to one or multiple invoices; detect collisions, split and partial applications.
3. Ingest remittance email/PDF after or before the receipt and correlate it to the existing record.
4. Represent each claimed deduction independently, with its own amount, type, evidence and unresolved status.
5. Directed investigation uses typed read-only evidence functions over contracts, promotions, signed delivery/proof of delivery, and tax records.
6. Validator checks source identity, hash, span, validity dates, and rule preconditions; does NOT accept an LLM confidence value as posting authorization.
7. Produce and review a journal proposal. Validated amounts may be cleared; unsupported deductions remain open in AR, never silently written off.
8. Create dispute/evidence requests (draft only), track replies, reinvestigate with late evidence; preserve full history.
9. Show an analyst inbox, evidence/case workbench, approvals, and audit/recovery dashboard.
10. Replay/benchmark deterministic and AI-assisted outcomes against synthetic ground truth.

## Core demo: CASE-204
An INR 120,000 invoiced balance is associated with INR 116,500 cash receipt and a later remittance claiming INR 1,000 of separately verified/approved synthetic withholding and INR 2,500 of uncorroborated damage. After validated matching, propose clearing INR 117,500 AR (INR 116,500 receipt + INR 1,000 approved tax receivable); keep INR 2,500 in AR with a dispute. Subsequently attach a customer evidence document and reopen for evaluation. This example is accounting mechanics ONLY; withholding eligibility is stipulated in fixture and not a legal opinion.

## UI screens
- Cash Inbox: imports, applied/unapplied receipt status, customer candidates, queue filters.
- Case Workbench: original sources, timeline, claims, candidate allocations, citations, findings and next action.
- Posting/Approval Queue: proposed journal lines, checks, maker-checker approval, simulated posting.
- Analytics/Audit: unapplied cash, disputed amount, case aging, manual review, evidence integrity, replay.

## Core quality bar
- No incorrect auto-posting across the frozen evaluation set. Zero duplicate simulated posting and over-allocation cases.
- Ambiguous customer or invoice assignments must abstain.
- Every LLM-supported factual finding is backed by a verifiable source pointer or flagged unsupported.
- Reprocessing any webhook/CSV/document event is idempotent.
- Each meaningful action creates a durable audit event.
- End-to-end single-case walkthrough in local Docker Compose environment.

## Explicit NON-goals for V1
No actual bank connection, real customer emails, production ERP posting, live tax filing, credit-note issuance, multi-currency, multi-company UI, invoice generation, collections calling, AP invoice matching, autonomous policy change, self-modifying tax rules, unbounded agent loops, arbitrary SQL tools, mandatory MCP server, or vector store.

## Product hypothesis to evaluate
Directed evidence investigation + persistent case management reduces analyst effort and unsupported financial recommendations compared with deterministic-only and conventional single-investigator baselines. Treat outcome as an experiment, not an assumed success.
