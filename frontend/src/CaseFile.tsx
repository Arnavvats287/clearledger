import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, FileText, RefreshCw } from "lucide-react";
import {
  ApiError,
  Client,
  bundle,
  type Customer,
  type Doc,
  type Invoice,
  type Me,
  type Receipt,
  date,
  human,
  money,
  presentation,
  short,
} from "./api";
import { DocumentInspector, type Selection } from "./Documents";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  Provenance,
  Section,
  useResource,
} from "./ui";
import { Investigation } from "./Investigation";
import { Correlation } from "./Correlation";
import { History } from "./History";
import type { Loaded } from "./workstation";

export function CaseFile({ api, me }: { api: Client; me: Me }) {
  const { id = "" } = useParams(),
    [params, setParams] = useSearchParams(),
    [revision, setRevision] = useState(0),
    [selection, setSelection] = useState<Selection>();

  const tab = params.get("tab") || "file";

  const [hideDefaultDoc, setHideDefaultDoc] = useState(false);

  const sourceTrigger = useRef<HTMLElement | null>(null);

  const load = useCallback(async (): Promise<Loaded> => {
    void revision;

    const c = await api.case(id),
      b = await bundle(api, c);

    const [invoices, receipts, docs, customer] = await Promise.all([
      Promise.all(
        c.invoice_ids.map((i) => api.request<Invoice>(`/invoices/${i}`)),
      ),
      Promise.all(
        c.receipt_ids.map((r) => api.request<Receipt>(`/receipts/${r}`)),
      ),
      Promise.all(
        c.document_ids.map((d) => api.request<Doc>(`/documents/${d}`)),
      ),
      c.customer_id
        ? api.request<Customer>(`/customers/${c.customer_id}`)
        : undefined,
    ]);

    return { b, invoices, receipts, docs, customer };
  }, [api, id, revision]);

  const state = useResource(load),
    refresh = () => setRevision((v) => v + 1);

  const activeRun = state.data?.b.runs.find((r) => !r.is_stale);
  const waiting = activeRun && ["QUEUED", "RUNNING"].includes(activeRun.status);
  const polls = useRef(0);

  useEffect(() => {
    if (!waiting) {
      polls.current = 0;
      return;
    }
    if (polls.current >= 20) return;
    const t = setTimeout(() => {
      polls.current++;
      setRevision((v) => v + 1);
    }, 2500);
    return () => clearTimeout(t);
  }, [waiting, revision]);

  if (state.loading && !state.data)
    return (
      <main id="main">
        <Loading label="Opening case file…" />
      </main>
    );

  if (state.error)
    return (
      <main id="main">
        <Link to="/">Back to register</Link>
        <ErrorNotice error={state.error} retry={refresh} />
      </main>
    );

  if (!state.data) return null;

  const data = state.data,
    { b } = data,
    c = b.case,
    p = presentation(b);

  const inspect = (s: Selection) => {
    sourceTrigger.current = document.activeElement as HTMLElement;
    setHideDefaultDoc(false);
    setSelection(s);
    setParams((v) => {
      v.set("document", s.document);
      return v;
    });
  };

  // Open a citation with its original canonical quote, not a privacy-projected excerpt.

  async function inspectVerified(s: Selection) {
    if (s.span) {
      try {
        const raw = await api.request<{ pages: string[] }>(
          `/documents/${s.document}/text`,
        );
        const points = Array.from(raw.pages[s.span.page - 1] || "");
        s = {
          ...s,
          span: {
            ...s.span,
            quote: points.slice(s.span.start, s.span.end).join(""),
          },
        };
      } catch {
        /* Inspector independently reports source retrieval/integrity failure. */
      }
    }

    inspect(s);
  }

  const doc =
    selection ||
    (params.get("document")
      ? { document: params.get("document")! }
      : !hideDefaultDoc && tab === "file" && data.docs[0]
        ? { document: data.docs[0].id }
        : undefined);

  return (
    <main id="main" className="case-page">
      <div className="case-breadcrumb">
        <Link to="/">
          <ArrowLeft size={14} aria-hidden="true" />
          Exception register
        </Link>
        <span>/</span>
        <span className="mono">{short(c.id)}</span>
        <span>Case v{c.version}</span>
      </div>

      <header className="case-heading">
        <div>
          <h1 tabIndex={-1}>
            {data.customer?.name || "Unassigned remittance"}
          </h1>
          <p>
            {data.invoices.map((i) => i.invoice_number).join(" · ") ||
              "Invoice relationship awaits source proof"}{" "}
            ·{" "}
            {b.claims.map((q) => human(q.category)).join(", ") ||
              "No extracted claims"}
          </p>
        </div>
        <div>
          <Badge
            kind={p.conflict ? "danger" : p.supported ? "positive" : "neutral"}
          >
            {human(p.state)}
          </Badge>
          <button onClick={refresh} disabled={state.loading}>
            <RefreshCw size={14} aria-hidden="true" />
            Refresh case
          </button>
        </div>
      </header>

      <div className="financial-comparison">
        <div>
          <span>Open invoice AR</span>
          <strong>
            {money(
              data.invoices.length
                ? data.invoices.reduce((n, i) => n + i.open_amount_paise, 0n)
                : null,
            )}
          </strong>
          <small>
            {data.invoices.map((i) => i.invoice_number).join(", ") ||
              "Not linked"}
          </small>
        </div>
        <div>
          <span>Unapplied receipt</span>
          <strong>
            {money(
              data.receipts.length
                ? data.receipts.reduce(
                    (n, r) => n + r.unapplied_amount_paise,
                    0n,
                  )
                : null,
            )}
          </strong>
          <small>
            {data.receipts.length
              ? "Cash remains unapplied"
              : "No verified association"}
          </small>
        </div>
        <div className="asserted">
          <span>Deduction asserted</span>
          <strong>{money(c.claimed_total_paise)}</strong>
          <small>
            {c.unknown_amount_count
              ? `${c.unknown_amount_count} unknown amount`
              : "Customer claim · not approved"}
          </small>
        </div>
        <div>
          <span>Verified settlement</span>
          <strong>{money(c.verified_settled_paise)}</strong>
          <small>Source-backed is not settled</small>
        </div>
      </div>

      <div className="next-action">
        <div>
          <span className="next-symbol" aria-hidden="true">
            ↳
          </span>
          <div>
            <strong>{human(p.action)}</strong>
            <p>
              {p.conflict
                ? "Verified delivery records disagree. A human must resolve the conflict."
                : p.supported
                  ? "Source predicates support this claim. Review the sources before any separate financial decision."
                  : "Keep the claim unresolved until the required proof and relationship are verified."}
            </p>
          </div>
        </div>
        <Provenance kind="authority" />
      </div>

      {c.is_stale && (
        <ErrorNotice
          error={new ApiError(409, "STALE_CORRELATION_CASE")}
          retry={refresh}
        />
      )}

      <nav className="case-tabs" aria-label="Case views">
        {[
          ["file", "Case file"],
          ["investigation", "Investigation"],
          ["correlation", "Correlation review"],
          ["history", "Audit trail"],
        ].map(([key, label]) => (
          <Link
            key={key}
            to={`?tab=${key}`}
            aria-current={tab === key ? "page" : undefined}
          >
            {label}
            {key === "correlation" &&
              b.tasks.some((t) => t.status === "PENDING") && (
                <span className="pending-dot" aria-label="Pending review" />
              )}
          </Link>
        ))}
      </nav>

      <div className={`folio-grid ${doc ? "inspecting" : ""}`}>
        <div className="folio-main">
          {tab === "file" && (
            <>
              <Section
                title="The asserted discrepancy"
                meta={<Badge>{b.claims.length} claims</Badge>}
              >
                {b.claims.map((q) => (
                  <article className="claim-row" key={q.id}>
                    <div>
                      <Provenance kind="check">Extracted assertion</Provenance>
                      <h3>{human(q.category)}</h3>
                      <p>
                        {human(q.state)} ·{" "}
                        {q.source_current ? "Current source" : "Source changed"}
                      </p>
                    </div>
                    <strong className="num">{money(q.amount_paise)}</strong>
                    <button
                      onClick={() => inspect({ document: q.document_id })}
                    >
                      <FileText size={15} aria-hidden="true" />
                      Inspect remittance
                    </button>
                  </article>
                ))}
                {!b.claims.length && (
                  <Empty>
                    No claim extracted. A bank receipt alone does not establish
                    a deduction.
                  </Empty>
                )}
              </Section>
              <Section
                title="Original documents"
                meta={<span>{data.docs.length} immutable originals</span>}
              >
                {data.docs.map((d) => (
                  <button
                    className="document-row"
                    key={d.id}
                    onClick={() => inspect({ document: d.id })}
                  >
                    <FileText size={19} aria-hidden="true" />
                    <span>
                      <strong>{d.source_name}</strong>
                      <small>
                        {d.mime} · {d.parse_status} · v{d.version}
                      </small>
                    </span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </button>
                ))}
                {!data.docs.length && (
                  <Empty>No source documents linked.</Empty>
                )}
              </Section>
              <Section
                title="Financial relationship"
                meta={<Provenance kind="check" />}
              >
                {data.invoices.map((i) => (
                  <div className="relationship-row" key={i.id}>
                    <span>
                      Invoice {i.invoice_number}
                      <small>{human(i.status)}</small>
                    </span>
                    <strong>
                      {money(i.original_amount_paise)}
                      <small>Original invoice</small>
                    </strong>
                    <strong>
                      {money(i.open_amount_paise)}
                      <small>Still open</small>
                    </strong>
                  </div>
                ))}
                {data.receipts.map((r) => (
                  <div className="relationship-row" key={r.id}>
                    <span>
                      Receipt <span className="mono">{short(r.id)}</span>
                      <small>{human(r.status)}</small>
                    </span>
                    <strong>
                      {money(r.amount_paise)}
                      <small>Received</small>
                    </strong>
                    <strong>
                      {money(r.unapplied_amount_paise)}
                      <small>Unapplied</small>
                    </strong>
                  </div>
                ))}
                {!data.receipts.length && (
                  <Empty>
                    Receipt/customer association has not been verified. Open
                    correlation review for source requirements.
                  </Empty>
                )}
              </Section>
            </>
          )}

          {tab === "investigation" && (
            <Investigation
              api={api}
              data={data}
              me={me}
              refresh={refresh}
              inspect={(s) => void inspectVerified(s)}
            />
          )}

          {tab === "correlation" && (
            <Correlation
              api={api}
              data={data}
              me={me}
              refresh={refresh}
              inspect={inspect}
            />
          )}

          {tab === "history" && <History api={api} data={data} />}
        </div>
        <aside className="folio-margin">
          {doc ? (
            <DocumentInspector
              key={`${doc.document}-${doc.record || ""}`}
              api={api}
              selection={doc}
              caseRecord={c}
              close={() => {
                setHideDefaultDoc(true);
                setSelection(undefined);
                setParams((v) => {
                  v.delete("document");
                  return v;
                });
                requestAnimationFrame(() => sourceTrigger.current?.focus());
              }}
            />
          ) : (
            <>
              <div className="margin-note">
                <span className="folio-index" aria-hidden="true">
                  §
                </span>
                <h2>Proof before permission.</h2>
                <p>
                  Every source has a location.
                  <br />
                  Every finding has a basis.
                  <br />
                  Every decision has an author.
                </p>
                <dl className="key-list">
                  <div>
                    <Provenance kind="source" />
                    <dd>Authenticated source facts</dd>
                  </div>
                  <div>
                    <Provenance kind="check" />
                    <dd>Rules, integrity & currentness</dd>
                  </div>
                  <div>
                    <Provenance kind="ai" />
                    <dd>Proposals, never authority</dd>
                  </div>
                  <div>
                    <Provenance kind="human" />
                    <dd>Recorded review decisions</dd>
                  </div>
                </dl>
              </div>
              <div className="margin-detail">
                <span>Canonical case</span>
                <code>{c.id}</code>
                <span>Workflow</span>
                <strong>{human(c.state)}</strong>
                <span>Opened</span>
                <strong>{date(c.created_at)}</strong>
              </div>
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
