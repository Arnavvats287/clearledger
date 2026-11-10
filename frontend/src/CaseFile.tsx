import { useCallback, useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import {
  ApiError,
  Client,
  bundle,
  portfolioCase,
  publicPortfolio,
  type Customer,
  type Doc,
  type Invoice,
  type Me,
  type Model,
  type Receipt,
} from "./api";
import { DocumentInspector, type Selection } from "./Documents";
import { ErrorNotice, Loading, useResource } from "./ui";
import { Investigation } from "./Investigation";
import { Correlation } from "./Correlation";
import { History } from "./History";
import type { Loaded } from "./workstation";
import { CaseStory, FinancialStory } from "./CaseStory";
import { assessment } from "./story";

type CaseDetail = Loaded & { sources: Model<"RecordView">[] };

export function CaseFile({ api, me }: { api: Client; me: Me }) {
  const { id = "" } = useParams(),
    [params, setParams] = useSearchParams(),
    [revision, setRevision] = useState(0),
    [selection, setSelection] = useState<Selection>();

  const tab = params.get("tab") || "file";
  const { hash } = useLocation();

  const sourceTrigger = useRef<HTMLElement | null>(null);

  const load = useCallback(async (): Promise<CaseDetail> => {
    void revision;
    if (publicPortfolio) return api.request<CaseDetail>(portfolioCase(id));

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

    const ids = [
      ...new Set(
        b.findings.flatMap((f) => f.citations.map((c) => c.record_id)),
      ),
    ];
    const query = new URLSearchParams({
      expected_case_version: String(c.version),
      expected_context_sha256: c.context_sha256,
      customer_id: c.customer_id || "",
    });
    const sources = c.customer_id
      ? await Promise.all(
          ids
            .slice(0, 20)
            .map((r) =>
              api.request<Model<"RecordView">>(
                `/cases/${c.id}/evidence/records/${r}?${query}`,
              ),
            ),
        )
      : [];
    return { b, invoices, receipts, docs, customer, sources };
  }, [api, id, revision]);

  const state = useResource(load, {
    initial: api.peek<CaseDetail>(portfolioCase(id)),
    retainOnError: publicPortfolio,
  });
  const refresh = () => {
    api.invalidate(portfolioCase(id), [
      `/cases/${id}`,
      ...(state.data?.b.tasks.map(
        (task) => `/review/correlation-tasks/${task.id}`,
      ) ?? []),
      ...(state.data?.docs.map((doc) => `/documents/${doc.id}`) ?? []),
      ...(state.data?.sources.map(
        (source) => `/documents/${source.citation.document_id}`,
      ) ?? []),
    ]);
    setRevision((v) => v + 1);
  };

  useEffect(() => {
    if (tab === "file" && state.data && hash === "#required-action")
      document
        .getElementById("required-action")
        ?.scrollIntoView({ block: "center" });
  }, [tab, hash, state.data]);
  const activeRun = state.data?.b.runs.find((r) => !r.is_stale);
  const waiting =
    !publicPortfolio &&
    activeRun &&
    ["QUEUED", "RUNNING"].includes(activeRun.status);
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

  const wrongCase =
    publicPortfolio && state.data && state.data.b.case.requested_case_id !== id;
  if ((!state.data && state.loading) || (wrongCase && !state.error))
    return (
      <main id="main">
        <Loading label="Opening case file…" />
      </main>
    );

  if (state.error && (!publicPortfolio || !state.data || wrongCase))
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
    p = assessment(b);

  const inspect = (s: Selection) => {
    sourceTrigger.current = document.activeElement as HTMLElement;
    setSelection(s);
    setParams((v) => {
      v.set("document", s.document);
      return v;
    });
  };

  // Open a citation with its original canonical quote, not a privacy-projected excerpt.

  async function inspectVerified(s: Selection) {
    if (!s.record) {
      const cited = b.findings
        .flatMap((f) => f.citations)
        .find((c) => c.document_id === s.document);
      if (cited)
        s = {
          ...s,
          record: cited.record_id,
          expected: {
            version: cited.document_version,
            raw: cited.raw_sha256,
            canonical: cited.canonical_sha256,
          },
        };
    }
    if (s.span) {
      try {
        const raw = publicPortfolio
          ? await api.sourceText(
              s.expected
                ? {
                    id: s.document,
                    version: s.expected.version,
                    content_sha256: s.expected.raw,
                    canonical_sha256: s.expected.canonical,
                  }
                : (data.docs.find((item) => item.id === s.document) ??
                    (await api.request<Doc>(`/documents/${s.document}`))),
            )
          : await api.request<{ pages: string[] }>(
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
      : undefined);
  const technical = () =>
    setParams((v) => {
      v.set("tab", "technical");
      return v;
    });
  return (
    <main
      id="main"
      className="case-page case-v2"
      key={c.id}
      aria-busy={state.loading}
      data-stale={c.is_stale}
      data-view={tab}
    >
      <div className="case-breadcrumb">
        <Link to="/">
          <ArrowLeft size={14} aria-hidden="true" />
          Exceptions
        </Link>
        <span>/</span>
        <span>
          {data.invoices.map((i) => i.invoice_number).join(", ") ||
            "Payment association review"}
        </span>
      </div>
      <header className="case-heading">
        <div>
          <h1 tabIndex={-1}>
            {data.customer?.name || "Customer association unconfirmed"}
          </h1>
          <p>
            {p.pending
              ? "Review the payment match before linking this claim."
              : "Short payment under review · customer-claimed deduction"}
          </p>
          {publicPortfolio && (
            <Link to="/intake#live-ai">Explore the live AI demo →</Link>
          )}
        </div>
        <button onClick={refresh} disabled={state.loading}>
          <RefreshCw size={14} aria-hidden="true" />
          {state.loading ? "Refreshing…" : "Refresh case"}
        </button>
      </header>
      {publicPortfolio && state.error !== undefined && (
        <ErrorNotice error={state.error} retry={refresh} />
      )}
      <FinancialStory key={`${c.id}:${c.is_stale}`} data={data} />
      {c.is_stale && (
        <ErrorNotice
          error={new ApiError(409, "STALE_CORRELATION_CASE")}
          retry={refresh}
        />
      )}
      <nav className="case-tabs" aria-label="Case views">
        {[
          ["file", "Case overview"],
          ["correlation", "Match payment to invoice"],
          ["history", "History"],
          ["technical", "Technical trace"],
        ].map(([key, label]) => (
          <Link
            key={key}
            to={`?tab=${key}`}
            aria-current={
              tab === key || (tab === "investigation" && key === "technical")
                ? "page"
                : undefined
            }
          >
            {label}
            {key === "correlation" && p.pending && (
              <span className="pending-dot" aria-label="Pending review" />
            )}
          </Link>
        ))}
      </nav>
      <div className={`folio-grid ${doc ? "inspecting" : ""}`}>
        <div className="folio-main" key={tab}>
          {tab === "file" && (
            <CaseStory
              api={api}
              data={data}
              me={me}
              refresh={refresh}
              inspect={(s) => void inspectVerified(s)}
              sources={data.sources}
              technical={technical}
            />
          )}
          {["technical", "investigation"].includes(tab) && (
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
        {doc && (
          <aside className="folio-margin">
            <DocumentInspector
              key={`${doc.document}-${doc.record || ""}`}
              api={api}
              selection={doc}
              caseRecord={c}
              knownDocument={
                publicPortfolio
                  ? data.docs.find((item) => item.id === doc.document)
                  : undefined
              }
              close={() => {
                setSelection(undefined);
                setParams((v) => {
                  v.delete("document");
                  return v;
                });
                requestAnimationFrame(() => sourceTrigger.current?.focus());
              }}
            />
          </aside>
        )}
      </div>
    </main>
  );
}
