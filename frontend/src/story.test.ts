import { describe, expect, it } from "vitest";
import { assessment, financialStory } from "./story";
import type { Bundle, Invoice, Receipt } from "./api";

const invoice = (amount: bigint) =>
  ({ original_amount_paise: amount }) as Invoice;
const receipt = (amount: bigint) => ({ amount_paise: amount }) as Receipt;
function bundle(): Bundle {
  return {
    case: {
      id: "test",
      requested_case_id: "test",
      organization_id: "test",
      version: 1,
      customer_id: null,
      created_at: "2026-01-01T00:00:00Z",
      context_sha256: "0".repeat(64),
      current_context_sha256: "0".repeat(64),
      receipt_ids: [],
      document_ids: [],
      invoice_ids: [],
      claimed_total_paise: null,
      unknown_amount_count: 0,
      requires_human_review: true,
      financial_authority: false,
      verified_settled_paise: 0n,
      state: "AWAITING_EVIDENCE",
      is_stale: false,
      attention_codes: [],
    },
    claims: [],
    tasks: [],
    runs: [],
    findings: [],
    trace: [],
  };
}
describe("financial story is display arithmetic, never payment authority", () => {
  it("shows exact INR discrepancy and preserves zero and missing values", () => {
    expect(financialStory([invoice(5000000n)], [receipt(4700000n)])).toEqual({
      invoiced: 5000000n,
      received: 4700000n,
      difference: 300000n,
    });
    expect(financialStory([invoice(0n)], [receipt(0n)]).difference).toBe(0n);
    expect(financialStory([invoice(5000000n)], []).difference).toBeNull();
    expect(financialStory([], []).invoiced).toBeNull();
  });
  it("never rounds large paise values and reports excess cash honestly", () => {
    expect(
      financialStory([invoice(9007199254740993n)], [receipt(9007199254740992n)])
        .difference,
    ).toBe(1n);
    expect(financialStory([invoice(100n)], [receipt(101n)]).difference).toBe(
      -1n,
    );
  });
  it("does not invent missing POD for a generic unresolved case", () => {
    const a = assessment(bundle());
    expect(a.action).toBe("Request supporting evidence");
    expect(a.title).not.toContain("POD");
    expect(a.origin).toBe("Rules assessment");
  });
  it("uses the persisted missing-proof reason and never labels fallback AI", () => {
    const b = bundle();
    b.findings = [
      {
        unknowns: ["MISSING_SIGNED_POD"],
        state: "INSUFFICIENT_EVIDENCE",
        next_action: "REQUEST_EVIDENCE",
      } as Bundle["findings"][number],
    ];
    b.trace = [
      {
        id: "trace",
        created_at: "2026-01-01T00:00:00Z",
        node: "investigator_synthesize",
        metadata: { fallback: true },
      } as Bundle["trace"][number],
    ];
    expect(assessment(b).action).toBe("Request signed POD");
    expect(assessment(b).origin).toBe("Rules-based fallback");
  });
  it("distinguishes pending proof from complete proof", () => {
    const b = bundle();
    b.tasks = [
      {
        status: "PENDING",
        reason: "AUTHORITATIVE_CORRELATION_REQUIRED",
        is_stale: false,
      } as Bundle["tasks"][number],
    ];
    expect(assessment(b).explanation).toContain("incomplete");
    b.tasks[0].reason = "READY_FOR_REVIEW";
    expect(assessment(b).explanation).toContain("available for review");
  });
  it("changed evidence overrides supported presentation and blocks premature reassurance", () => {
    const b = bundle();
    b.case.is_stale = true;
    b.trace = [
      {
        id: "trace",
        created_at: "2026-01-01T00:00:00Z",
        node: "investigator_synthesize",
        metadata: { fallback: false, synthesis: { state: "SUPPORTED" } },
      } as Bundle["trace"][number],
    ];
    const a = assessment(b);
    expect(a.supported).toBe(false);
    expect(a.title).toBe("Evidence changed");
    expect(a.action).toBe("Refresh changed evidence");
  });
  it("does not invent a delivery conflict for a non-delivery claim", () => {
    const b = bundle();
    b.claims = [{ category: "rebate" } as Bundle["claims"][number]];
    b.trace = [
      {
        id: "trace",
        created_at: "2026-01-01T00:00:00Z",
        node: "investigator_synthesize",
        metadata: {
          fallback: false,
          synthesis: { state: "CONFLICTING_EVIDENCE" },
        },
      },
    ];
    expect(assessment(b).title).toBe("Evidence records disagree");
    expect(assessment(b).action).toBe("Resolve conflicting evidence");
  });
});
