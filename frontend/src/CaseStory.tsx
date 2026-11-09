import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  CircleHelp,
  FileText,
  ShieldCheck,
  AlertTriangle,
  LockKeyhole,
} from "lucide-react";
import { Client, date, human, money, record, type Me, type Model } from "./api";
import type { Loaded } from "./workstation";
import type { Selection } from "./Documents";
import { ReviewAction } from "./ReviewAction";
import { assessment, financialStory } from "./story";

function evidenceValue({ manifest: { fact } }: Model<"RecordView">) {
  if (fact.type === "WMS" || fact.type === "POD")
    return `Delivered: ${fact.delivered.span.quote} · Damaged: ${fact.damaged.span.quote}`;
  if (fact.type === "CONTRACT")
    return `Limit: ${money(BigInt(fact.limit.value))}`;
  if ("amount" in fact)
    return `Recorded amount: ${money(BigInt(fact.amount.value))}`;
  return "";
}

export function FinancialStory({ data }: { data: Loaded }) {
  const f = financialStory(data.invoices, data.receipts);
  return (
    <section
      className="reconciliation-statement"
      aria-label="Invoice, payment and difference"
    >
      <div className="statement-caption">
        Payment reconciliation <span>Linked financial records · INR</span>
      </div>
      <div className="money-equation">
        <div className="flow-invoice">
          <span>Invoiced</span>
          <strong>{money(f.invoiced)}</strong>
          <small>
            {data.invoices.map((i) => i.invoice_number).join(", ") ||
              "Invoice not linked"}
          </small>
          {data.invoices.length > 0 && (
            <small>
              Open AR{" "}
              {money(
                data.invoices.reduce((n, i) => n + i.open_amount_paise, 0n),
              )}
            </small>
          )}
        </div>
        <span className="math-sign" aria-label="minus">
          −
        </span>
        <div className="flow-receipt">
          <span>Received</span>
          <strong>{money(f.received)}</strong>
          <small>
            {data.receipts.length
              ? `Bank receipt · ${money(data.receipts.reduce((n, r) => n + r.unapplied_amount_paise, 0n))} unapplied`
              : "Payment not linked"}
          </small>
        </div>
        <span className="math-sign" aria-label="equals">
          =
        </span>
        <div className="difference">
          <span>
            {f.difference !== null && f.difference < 0n
              ? "Payment exceeds invoice"
              : "Short payment"}
          </span>
          <strong>{money(f.difference)}</strong>
          <small>
            {f.difference === null
              ? "Confirm the association first"
              : "Comparison only · no allocation"}
          </small>
        </div>
      </div>
      <div className="customer-explanation">
        <span>Customer’s explanation</span>
        <p>
          {data.b.claims.length ? (
            <>
              {data.b.claims.map((c) => human(c.category)).join(", ")} deduction{" "}
              <strong>{money(data.b.case.claimed_total_paise)}</strong>
            </>
          ) : (
            "No deduction claim on this case."
          )}
        </p>
        <small>
          {data.b.case.unknown_amount_count
            ? "Some claimed amounts are unknown."
            : data.b.claims.length
              ? "Extracted from the remittance. A claim is not an approved adjustment."
              : "The customer explanation has not been established for this case."}
        </small>
      </div>
      <div className="statement-next">
        <Link
          to="?tab=file#required-action"
          onClick={() =>
            requestAnimationFrame(() =>
              document
                .getElementById("required-action")
                ?.scrollIntoView({ block: "center" }),
            )
          }
        >
          Next: {assessment(data.b).action}{" "}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
        <span>
          Case settlement {money(data.b.case.verified_settled_paise)} · review
          does not authorize posting
        </span>
      </div>
    </section>
  );
}

export function CaseStory({
  api,
  data,
  me,
  refresh,
  inspect,
  sources,
  technical,
}: {
  api: Client;
  data: Loaded;
  me: Me;
  refresh: () => void;
  inspect: (s: Selection) => void;
  sources: Model<"RecordView">[];
  technical: () => void;
}) {
  const a = assessment(data.b);
  const planned = record(
    record(data.b.trace.find((t) => t.node === "investigator_plan")?.metadata)
      .plan,
  ).evidence_types;
  const kinds = [
    ...new Set([
      "REMITTANCE",
      ...a.missing,
      ...(Array.isArray(planned)
        ? planned.filter((x): x is string => typeof x === "string")
        : []),
      ...sources.map((s) => s.kind),
    ]),
  ];
  const labels: Record<string, string> = {
    REMITTANCE: "Customer remittance",
    WMS: "Warehouse evidence",
    POD: "Signed proof of delivery",
    CONTRACT: "Contract",
    PROMOTION: "Promotion evidence",
  };
  const available = (kind: string) =>
    sources.filter(
      (s) => s.kind === kind && s.source_authenticated && s.is_current,
    );
  const citations = data.b.findings.flatMap((f) => f.citations);
  const openSource = (source: Model<"RecordView">) => {
    const c = citations.find((c) => c.record_id === source.id);
    if (c)
      inspect({
        document: c.document_id,
        record: c.record_id,
        span: { page: c.page, start: c.start, end: c.end, quote: c.excerpt },
        expected: {
          version: c.document_version,
          raw: c.raw_sha256,
          canonical: c.canonical_sha256,
        },
      });
  };
  return (
    <div className="case-brief">
      <section
        className={`assessment-brief ${a.conflict ? "conflict" : a.supported ? "supported" : "missing"}`}
        aria-label="ClearLedger assessment"
      >
        <div className="assessment-heading">
          {a.conflict ? (
            <AlertTriangle size={21} aria-hidden="true" />
          ) : a.supported ? (
            <ShieldCheck size={21} aria-hidden="true" />
          ) : (
            <CircleHelp size={21} aria-hidden="true" />
          )}
          <span>
            {a.stale
              ? "Evidence changed"
              : a.pending
                ? "Association review"
                : a.conflict
                  ? "Conflicting evidence"
                  : a.supported
                    ? "Verified support"
                    : "Missing proof"}
          </span>
        </div>
        <h2>{a.title}</h2>
        <p>{a.explanation}</p>
        <div className="assessment-origin">
          <span
            className={`origin-symbol ${["AI assessment", "Demo scenario"].includes(a.origin) ? "model" : "check"}`}
          >
            {["AI assessment", "Demo scenario"].includes(a.origin) ? (
              "◇"
            ) : (
              <Check size={17} aria-hidden="true" />
            )}
          </span>
          <div>
            <strong>{a.origin}</strong>
            <span>
              {a.origin === "Demo scenario"
                ? "Offline model output. Source verification runs independently."
                : a.origin === "AI assessment"
                  ? "The model recommends; source verification and review rules constrain the result."
                  : "Rules determine this result. No AI reasoning is implied."}
            </span>
          </div>
          <button className="text-button" onClick={technical}>
            View technical trace <ArrowRight size={14} aria-hidden="true" />
          </button>
        </div>
      </section>
      <section
        className="action-brief"
        id="required-action"
        aria-label="Required human action"
      >
        <div>
          <span className="human-marker">Human review</span>
          <h2>{a.action}</h2>
          <p>
            {a.conflict
              ? "Ask for clarification of the conflicting delivery records before deciding the claim."
              : a.supported
                ? "Inspect the cited records and record your review. Any financial adjustment requires separate authority."
                : "Request the missing proof, then refresh the investigation when new evidence arrives."}
          </p>
        </div>
        {a.pending ? (
          <p>
            Open <strong>Match payment to invoice</strong> to review the
            independent proof.
          </p>
        ) : (
          <ReviewAction api={api} data={data} me={me} refresh={refresh} />
        )}
      </section>
      <section className="evidence-checklist" aria-label="Sources checked">
        <div className="brief-section-heading">
          <h2>What was checked</h2>
          <span>Source verification</span>
        </div>
        {kinds.flatMap((kind) => {
          const label = labels[kind] || human(kind);
          const rows = available(kind),
            missing =
              a.missing.includes(kind) ||
              (kind === "POD" &&
                data.b.findings.some((f) =>
                  f.unknowns.includes("MISSING_SIGNED_POD"),
                ));
          if (rows.length)
            return rows.map((source) => (
              <div className="evidence-check verified" key={source.id}>
                <ShieldCheck size={18} aria-hidden="true" />
                <div>
                  <strong>{label}</strong>
                  <span className="evidence-value">
                    {evidenceValue(source)}
                  </span>
                  <span>
                    Publisher {source.manifest.source_system} ·{" "}
                    {date(source.manifest.occurred_at)} · v{source.revision}
                  </span>
                  <span
                    className={
                      a.conflict && ["WMS", "POD"].includes(kind)
                        ? "source-conflict"
                        : "source-verified"
                    }
                  >
                    {a.stale
                      ? "Assessment needs refresh"
                      : a.conflict && ["WMS", "POD"].includes(kind)
                        ? "Source verified · conflicting delivery evidence"
                        : "Authenticity and quoted source verified"}
                  </span>
                </div>
                <button onClick={() => openSource(source)}>
                  View evidence <ArrowRight size={14} aria-hidden="true" />
                </button>
              </div>
            ));
          return (
            <div className="evidence-check unconfirmed" key={kind}>
              <CircleHelp size={18} aria-hidden="true" />
              <div>
                <strong>{label}</strong>
                <span>
                  {a.stale
                    ? "Assessment needs refresh"
                    : missing
                      ? "Required proof missing or unverified"
                      : "No verified source shown in this assessment"}
                </span>
              </div>
            </div>
          );
        })}
      </section>
      <section
        className="decision-boundaries"
        aria-label="Review and financial status"
      >
        <div>
          <span>Evidence</span>
          <strong>
            {a.stale
              ? "Changed"
              : a.supported
                ? "Supported"
                : a.conflict
                  ? "Conflicting"
                  : "Incomplete"}
          </strong>
        </div>
        <div>
          <span>Human review</span>
          <strong>{human(data.b.case.state)}</strong>
        </div>
        <div>
          <LockKeyhole size={15} aria-hidden="true" />
          <span>Financial authorization</span>
          <strong>Not granted by this review</strong>
        </div>
        <div>
          <span>Settlement recorded</span>
          <strong>{money(data.b.case.verified_settled_paise)}</strong>
        </div>
        <p>
          No financial adjustment is posted by any action on this screen. Review
          is separate from financial authorization.
        </p>
      </section>
      <section className="brief-documents">
        <h2>Remittance & case documents</h2>
        {data.docs.map((d) => (
          <button
            className="document-row"
            key={d.id}
            onClick={() => inspect({ document: d.id })}
          >
            <FileText size={18} aria-hidden="true" />
            <span>
              <strong>{d.source_name}</strong>
              <small>View the original text and extracted fields</small>
            </span>
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        ))}
      </section>
    </div>
  );
}
