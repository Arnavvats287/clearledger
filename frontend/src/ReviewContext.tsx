import { money, human } from "./api";
import { assessment } from "./story";
import type { Loaded } from "./workstation";

export function ReviewContext({
  data,
  proof,
}: {
  data: Loaded;
  proof?: { ready: boolean; records: number };
}) {
  const a = assessment(data.b);
  return (
    <div className="review-context">
      <span>{data.customer?.name || "Unconfirmed customer association"}</span>
      <h3>
        {data.b.claims.length
          ? `${data.b.claims.map((c) => human(c.category)).join(", ")} deduction`
          : "Payment and invoice association"}
      </h3>
      {data.b.claims.length > 0 && (
        <strong className="review-amount">
          {money(data.b.case.claimed_total_paise)}
        </strong>
      )}
      <dl>
        <div>
          <dt>Invoice</dt>
          <dd>
            {data.invoices.map((i) => i.invoice_number).join(", ") ||
              "Proposed association — inspect the proof"}
          </dd>
        </div>
        <div>
          <dt>Evidence assessment</dt>
          <dd>{a.title}</dd>
        </div>
        <div>
          <dt>Sources checked</dt>
          <dd>
            {proof
              ? proof.ready
                ? `${proof.records} independent payment-proof record(s) in this review task`
                : "Payment proof is incomplete; confirmation is unavailable"
              : `${data.b.findings.reduce((n, f) => n + f.citations.length, 0)} cited records in the current assessment`}
          </dd>
        </div>
      </dl>
      <p className="decision-warning">
        This action does not post a financial adjustment, approve a deduction or
        apply cash.
      </p>
    </div>
  );
}
