import {
  human,
  presentation,
  record,
  text,
  type Bundle,
  type Invoice,
  type Receipt,
} from "./api";

// Display arithmetic, never an allocation or a payment-intent decision.
// Keep absent inputs unknown; zero is a real financial amount.
export function financialStory(invoices: Invoice[], receipts: Receipt[]) {
  const invoiced = invoices.length
    ? invoices.reduce((n, i) => n + i.original_amount_paise, 0n)
    : null;
  const received = receipts.length
    ? receipts.reduce((n, r) => n + r.amount_paise, 0n)
    : null;
  const difference =
    invoiced !== null && received !== null ? invoiced - received : null;
  return { invoiced, received, difference };
}

export function assessment(b: Bundle) {
  const p = presentation(b);
  const delivery = b.claims.some((c) =>
    ["damage", "short_shipment"].includes(c.category),
  );
  const pending = b.tasks.some((t) => t.status === "PENDING");
  const proofReady = b.tasks.some(
    (t) =>
      t.status === "PENDING" && t.reason === "READY_FOR_REVIEW" && !t.is_stale,
  );
  const synthesis = b.trace.find((t) => t.node === "investigator_synthesize");
  const meta = record(synthesis?.metadata);
  const s = meta.fallback === false ? record(meta.synthesis) : {};
  const missing = Array.isArray(s.missing_evidence_types)
    ? s.missing_evidence_types.filter((x): x is string => typeof x === "string")
    : [];
  const signedPodMissing =
    missing.includes("POD") ||
    b.findings.some((f) => f.unknowns.includes("MISSING_SIGNED_POD"));
  const action = p.stale
    ? "Refresh changed evidence"
    : pending
      ? "Match payment to invoice"
      : p.conflict
        ? delivery
          ? "Resolve conflicting delivery records"
          : "Resolve conflicting evidence"
        : p.supported
          ? "Review supported deduction"
          : signedPodMissing
            ? "Request signed POD"
            : p.missing
              ? "Request supporting evidence"
              : human(p.action);
  const title = p.stale
    ? "Evidence changed"
    : pending
      ? "Payment match needs review"
      : p.conflict
        ? delivery
          ? "Delivery records disagree"
          : "Evidence records disagree"
        : p.supported
          ? "Evidence supports the claim"
          : signedPodMissing
            ? "Signed POD is missing"
            : "Evidence is incomplete";
  const explanation = p.stale
    ? "The previous assessment may no longer apply. Refresh the case before reviewing it."
    : pending
      ? proofReady
        ? "Independent payment proof is available for review. The association is not confirmed yet."
        : "Independent payment proof is incomplete or needs verification. Do not confirm an association from the remittance alone."
      : p.conflict
        ? "Verified source records contain conflicting facts. The discrepancy remains unresolved."
        : p.supported
          ? "Verified source facts support the claimed amount. A human still needs to review the deduction; source support is not financial authorization."
          : "Current evidence does not establish the deduction. Keep the disputed amount open while requesting the missing proof.";
  const origin =
    meta.fallback === true
      ? "Rules-based fallback"
      : b.runs.find((r) => !r.is_stale)?.provider === "fake"
        ? "Demo scenario"
        : synthesis &&
            text(
              record(b.trace.find((t) => t.node === "director_route")?.metadata)
                .provider,
            ) === "gemini"
          ? "AI assessment"
          : b.runs.find((r) => !r.is_stale)?.provider === "gemini"
            ? "AI assessment"
            : "Rules assessment";
  return { ...p, pending, missing, action, title, explanation, origin };
}
