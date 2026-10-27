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
import { Client, human, money, record, type Me, type Model } from "./api";
import type { Loaded } from "./workstation";
import type { Selection } from "./Documents";
import { ReviewAction } from "./ReviewAction";
import { assessment, financialStory } from "./story";

export function FinancialStory({ data }: { data: Loaded }) {
  const f = financialStory(data.invoices, data.receipts);
  return (
    <section
      className="reconciliation-statement"
      aria-label="Invoice, payment and difference"
    >
      <div className="statement-caption">
        What happened <span>Linked financial records · INR</span>
      </div>
      <div className="money-equation">
        <div>
          <span>Invoiced</span>
          <strong>{money(f.invoiced)}</strong>
          <small>
            {data.invoices.map((i) => i.invoice_number).join(", ") ||
              "Invoice not linked"}
          </small>
        </div>
        <span className="math-sign" aria-label="minus">
          −
        </span>
        <div>
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
          <span>What ClearLedger found</span>
        </div>
        <h2>{a.title}</h2>
        <p>{a.explanation}</p>
        <div className="assessment-origin">
          <span
            className={`origin-symbol ${a.origin === "AI assessment" ? "ai" : "check"}`}
          >
            {a.origin === "AI assessment" ? (
              "◇"
            ) : (
              <Check size={17} aria-hidden="true" />
            )}
          </span>
          <div>
            <strong>{a.origin}</strong>
            <span>
              {a.origin === "Demo scenario"
                ? "Offline model fixture; real source verification and workflow. No live AI in this demo."
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
      <section className="evidence-checklist" aria-label="Sources checked">
        <div className="brief-section-heading">
          <h2>What was checked</h2>
          <span>Source verification</span>
        </div>
        {kinds.map((kind) => {
          const label = labels[kind] || human(kind);
          const rows = available(kind),
            missing =
              a.missing.includes(kind) ||
              (kind === "POD" &&
                data.b.findings.some((f) =>
                  f.unknowns.includes("MISSING_SIGNED_POD"),
                ));
          return (
            <div
              className={`evidence-check ${rows.length ? "verified" : "unconfirmed"}`}
              key={kind}
            >
              {rows.length ? (
                <ShieldCheck size={19} aria-hidden="true" />
              ) : (
                <CircleHelp size={19} aria-hidden="true" />
              )}
              <div>
                <strong>{label}</strong>
                <span>
                  {a.stale
                    ? "Assessment needs refresh"
                    : rows.length
                      ? a.conflict && ["WMS", "POD"].includes(kind)
                        ? "Source verified · assessment has conflicting facts"
                        : "Authenticity and quoted source verified"
                      : missing
                        ? "Required proof missing or unverified"
                        : "No verified source shown in this assessment"}
                </span>
              </div>
              {!!rows.length && (
                <button onClick={() => openSource(rows[0])}>
                  View evidence <ArrowRight size={14} aria-hidden="true" />
                </button>
              )}
            </div>
          );
        })}
        <p className="evidence-boundary">
          <Check size={15} aria-hidden="true" />
          Linked invoice and payment:{" "}
          {data.invoices.length && data.receipts.length
            ? "Available in this case"
            : "Association still needs verification"}
          . Source authenticity does not approve a deduction.
        </p>
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
