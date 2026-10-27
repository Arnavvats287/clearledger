import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, LocateFixed, X } from "lucide-react";
import {
  ApiError,
  Client,
  type Case,
  type Doc,
  type Extraction,
  type Model,
  type Span,
  money,
  record,
  short,
  sliceSpan,
  text,
} from "./api";
import {
  Badge,
  Disclosure,
  Empty,
  ErrorNotice,
  Loading,
  Provenance,
  Fields,
  useResource,
} from "./ui";

export type Selection = {
  document: string;
  span?: Span;
  record?: string;
  proofTask?: { id: string; hash: string };
  expected?: { version: number; raw: string; canonical: string };
};

export function DocumentInspector({
  api,
  selection,
  caseRecord,
  close,
}: {
  api: Client;
  selection: Selection;
  caseRecord: Case;
  close: () => void;
}) {
  const [highlight, setHighlight] = useState<Span>(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [doc, canonical, extractions] = await Promise.all([
      api.request<Doc>(`/documents/${selection.document}`),
      api.request<{
        document_version: number;
        raw_sha256: string;
        canonical_sha256: string;
        pages: string[];
      }>(`/documents/${selection.document}/text`),
      api.list<Extraction>(`/documents/${selection.document}/extractions`),
    ]);
    if (
      !Array.isArray(canonical.pages) ||
      canonical.pages.some((p) => typeof p !== "string")
    )
      throw new ApiError(502, "MALFORMED_API_RESPONSE");
    const e = selection.expected;
    if (
      e &&
      (e.version !== canonical.document_version ||
        e.raw !== canonical.raw_sha256 ||
        e.canonical !== canonical.canonical_sha256)
    )
      throw new ApiError(409, "SOURCE_VERSION_CHANGED");
    let source: Model<"RecordView"> | undefined;
    if (selection.record) {
      if (selection.proofTask) {
        const rows = await api.list<Model<"RecordView">>(
          `/review/correlation-tasks/${selection.proofTask.id}/proof?expected_task_sha256=${selection.proofTask.hash}`,
        );
        source = rows.find((r) => r.id === selection.record);
        if (!source) throw new ApiError(404, "CORRELATION_PROOF_UNAVAILABLE");
      } else {
        const params = new URLSearchParams({
          expected_case_version: String(caseRecord.version),
          expected_context_sha256: caseRecord.context_sha256,
          customer_id: caseRecord.customer_id || "",
        });
        if (caseRecord.invoice_ids[0])
          params.set("invoice_id", caseRecord.invoice_ids[0]);
        source = await api.request<Model<"RecordView">>(
          `/cases/${caseRecord.id}/evidence/records/${selection.record}?${params}`,
        );
      }
      if (
        source.citation.document_id !== doc.id ||
        source.citation.document_version !== canonical.document_version ||
        source.citation.raw_sha256 !== canonical.raw_sha256 ||
        source.citation.canonical_sha256 !== canonical.canonical_sha256
      )
        throw new ApiError(409, "SOURCE_VERSION_CHANGED");
    }
    return { doc, canonical, extractions, source };
  }, [api, selection, caseRecord]);
  const state = useResource(load);
  const verify = useCallback(
    async (span: Span) => {
      setBusy(true);
      setError(undefined);
      try {
        const pages = state.data?.canonical.pages;
        if (!pages?.[span.page - 1])
          throw new ApiError(409, "SOURCE_PAGE_UNAVAILABLE");
        sliceSpan(pages[span.page - 1], span);
        const result = await api.request<{ source_consistent: boolean }>(
          `/documents/${selection.document}/verify-span`,
          "POST",
          span,
        );
        if (result.source_consistent !== true)
          throw new ApiError(409, "INVALID_DOCUMENT_EVIDENCE");
        setHighlight(span);
      } catch (e) {
        setHighlight(undefined);
        setError(e);
      } finally {
        setBusy(false);
      }
    },
    [api, selection.document, state.data],
  );
  useEffect(() => {
    if (!state.data) return;
    const span = selection.span || state.data.source?.citation.span;
    if (span) void verify(span);
  }, [state.data, selection.span, verify]);
  async function original() {
    setBusy(true);
    setError(undefined);
    try {
      const blob = await api.original(selection.document),
        url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = state.data?.doc.source_name || "original";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (state.data) {
      panel.current?.focus({ preventScroll: true });
      panel.current?.scrollIntoView({ block: "nearest" });
    }
  }, [state.data]);
  if (state.loading) return <Loading label="Loading immutable source…" />;
  if (state.error) return <ErrorNotice error={state.error} />;
  if (!state.data) return null;
  const { doc, canonical, extractions, source } = state.data;
  const result = record(extractions.at(-1)?.result);
  const refs = Array.isArray(result.invoice_references)
    ? result.invoice_references
    : [];
  const claims = Array.isArray(result.claims) ? result.claims : [];
  return (
    <section
      className="document-inspector"
      ref={panel}
      tabIndex={-1}
      aria-label="Document evidence inspector"
    >
      <header className="document-heading">
        <div>
          <FileText size={18} aria-hidden="true" />
          <h3>{doc.source_name}</h3>
        </div>
        <button onClick={close} aria-label="Close evidence inspector">
          <X size={16} />
        </button>
      </header>
      <div className="document-status">
        {source?.source_authenticated && source.is_current ? (
          <Provenance kind="source" />
        ) : (
          <Badge>Source identity not established in this view</Badge>
        )}
        {source && !source.is_current && <Badge>Source changed</Badge>}
      </div>
      {error !== undefined && <ErrorNotice error={error} />}
      <p className="source-explainer">
        Extracted fields point to the highlighted words. A matching quote proves
        its location, not that the customer’s claim is justified.
      </p>
      <div className="span-actions">
        {refs.map((r, i) => (
          <button
            key={i}
            disabled={busy}
            onClick={() => void verify(record(r).span as Span)}
          >
            <LocateFixed size={14} aria-hidden="true" />
            Invoice {text(record(r).value)}
          </button>
        ))}
        {claims.map((c, i) => (
          <button
            key={i}
            disabled={busy}
            onClick={() =>
              void verify(
                (record(c).amount_span || record(c).description) as Span,
              )
            }
          >
            <LocateFixed size={14} aria-hidden="true" />
            {text(record(c).category)} ·{" "}
            {money(
              typeof record(c).amount_paise === "bigint"
                ? (record(c).amount_paise as bigint)
                : null,
            )}
          </button>
        ))}
      </div>
      {highlight && (
        <p className="span-caption">
          <Provenance kind="check">Quote verified in source</Provenance>
        </p>
      )}
      <div
        className="canonical-pages"
        tabIndex={0}
        aria-label="Canonical source text"
      >
        {canonical.pages.map((page, i) => {
          const parts =
            highlight?.page === i + 1 ? sliceSpan(page, highlight) : null;
          return (
            <article className="paper" key={i}>
              <div className="page-number">Source text · page {i + 1}</div>
              <pre>
                {parts ? (
                  <>
                    {parts[0]}
                    <mark data-testid="source-highlight">{parts[1]}</mark>
                    {parts[2]}
                  </>
                ) : (
                  page || "No extractable text on this page."
                )}
              </pre>
            </article>
          );
        })}
      </div>
      {!canonical.pages.length && (
        <Empty>
          {doc.parse_status === "READY"
            ? "No canonical text."
            : `Parsing needs review: ${doc.parse_status}.`}
        </Empty>
      )}
      {source && (
        <Disclosure title="Authenticated source record">
          <Fields
            value={{
              kind: source.kind,
              source_system: source.manifest.source_system,
              source_record_id: source.manifest.source_record_id,
              signed_at: source.manifest.signed_at,
              recorded_at: source.manifest.recorded_at,
              current: source.is_current,
              source_authenticated: source.source_authenticated,
            }}
          />
        </Disclosure>
      )}
      <Disclosure title="Provenance / technical details">
        <Fields
          value={{
            document_version: doc.version,
            mime: doc.mime,
            selected_span: highlight
              ? {
                  page: highlight.page,
                  start: highlight.start,
                  end: highlight.end,
                }
              : null,
          }}
        />
        <dl className="fields">
          <div>
            <dt>Document</dt>
            <dd className="mono">{short(doc.id)}</dd>
          </div>
          <div>
            <dt>Original SHA-256</dt>
            <dd className="mono wrap">{canonical.raw_sha256}</dd>
          </div>
          <div>
            <dt>Canonical SHA-256</dt>
            <dd className="mono wrap">{canonical.canonical_sha256}</dd>
          </div>
          <div>
            <dt>Source authentication</dt>
            <dd>
              {source?.source_authenticated
                ? "Authenticated source record; still subject to currentness and policy review."
                : "Not established by extraction or span matching."}
            </dd>
          </div>
        </dl>
        <button onClick={() => void original()} disabled={busy}>
          <Download size={14} aria-hidden="true" />
          Download immutable original
        </button>
      </Disclosure>
    </section>
  );
}
