# CODEX TASK 11 — Evaluation, adversarial validation and technical report

Read docs/evaluation and current code. Do not change product semantics merely to inflate scores.

## Goal
Provide a reproducible, scientifically honest evaluation of financial correctness, abstention and directed-investigation benefit.

## Implement
1. Consume Argon-provided frozen scenarios and ground truth, with holdout customer/template patterns and adversarial cases. Codex must not generate, download, curate or seed demonstration/evaluation data; only minimal isolated application test fixtures are allowed.
2. Three arms: deterministic, one bounded investigator, Director–Investigator. Same input snapshots and allowed evidence; report sample sizes and confidence/uncertainty.
3. Test metrics: wrong auto-application, duplicate journals, invoice over-allocation, exact evidence pointer validity, unsupported deduction approvals, ambiguous abstention, case state correctness, tool/LLM call count, runtime, and measured token cost where available.
4. Property-based paise/allocations, actual PostgreSQL race tests, prompt injection suite, attempts at cross-company access, forged evidence, signed/expired contracts, stale approvals.
5. End-to-end CASE-204 demo script, architecture diagram, instructions to reproduce, limitations, known regulatory gaps, security review and screenshots of working UI.
6. Report data must come from executed runs. Clearly state if any model/real-service test was skipped for lack of credentials.

## Exit
Provide full commands, observed test results and benchmark artifacts. Document whether directed investigation truly beats the single-investigator baseline; if not, recommend dropping the added complexity. Update status. STOP.
