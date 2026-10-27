import { useCallback, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Upload } from "lucide-react";
import {
  Client,
  type Doc,
  type Model,
  date,
  human,
  record,
  short,
} from "./api";
import {
  Badge,
  Empty,
  ErrorNotice,
  Fields,
  Loading,
  Section,
  useResource,
} from "./ui";

export function Intake({ api, readOnly }: { api: Client; readOnly: boolean }) {
  const [kind, setKind] = useState("invoices"),
    [file, setFile] = useState<File>(),
    [synthetic, setSynthetic] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [result, setResult] = useState<unknown>(),
    [revision, setRevision] = useState(0);
  const admission = useRef<{ fingerprint: string; key: string } | undefined>(
    undefined,
  );
  const load = useCallback(async () => {
    void revision;
    return {
      imports: await api.list<Model<"ImportView">>("/imports?limit=20"),
      documents: await api.list<Doc>("/documents?limit=20"),
    };
  }, [api, revision]);
  const state = useResource(load);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    const fp = `${kind}:${file.name}:${file.size}:${file.lastModified}:${synthetic}`;
    if (admission.current?.fingerprint !== fp)
      admission.current = { fingerprint: fp, key: crypto.randomUUID() };
    try {
      let response: unknown;
      if (kind === "documents") {
        const mime =
          file.type ||
          (
            {
              txt: "text/plain",
              pdf: "application/pdf",
              json: "application/json",
              eml: "message/rfc822",
            } as Record<string, string>
          )[file.name.split(".").at(-1) || ""] ||
          "application/octet-stream";
        response = await api.raw(
          "/documents",
          file,
          {
            "Content-Type": mime,
            "X-Source-Filename": file.name,
            "X-Synthetic-Data": synthetic ? "true" : "false",
          },
          admission.current!.key,
        );
        const d = record(response);
        response = await api.request(
          `/documents/${d.id}/extract`,
          "POST",
          { expected_document_version: d.version, allow_external: false },
          admission.current!.key,
        );
      } else
        response = await api.raw(
          `/imports/${kind}`,
          file,
          {
            "Content-Type": "text/csv",
            "X-Source-Filename": file.name,
            "X-Data-Contract-Version": "1.0",
          },
          admission.current!.key,
        );
      setResult(response);
      setRevision((v) => v + 1);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="intake-page">
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>Import & documents</h1>
          <p>
            Imports remain traceable and never overwrite the original source.
          </p>
        </div>
        <Link to="/">
          Return to exception register{" "}
          <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </div>
      <div className="intake-grid">
        <Section title="Bring your records together">
          <form onSubmit={(e) => void submit(e)}>
            <label>
              What are you importing?
              <select
                name="record-type"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setFile(undefined);
                }}
              >
                <option value="customers">Customer master</option>
                <option value="payer-aliases">
                  Advanced: verified payer aliases
                </option>
                <option value="invoices">Invoices</option>
                <option value="bank-transactions">
                  Bank statement / receipts
                </option>
                <option value="documents">
                  Remittances / supporting documents
                </option>
              </select>
            </label>
            <p className="form-help">
              Import customers, aliases and invoices before bank transactions.
              Document ingestion is separate from the financial CSV contract.
            </p>
            <label>
              Source file
              <input
                key={kind}
                type="file"
                name="source-file"
                accept={kind === "documents" ? ".pdf,.txt,.json,.eml" : ".csv"}
                onChange={(e) => setFile(e.target.files?.[0])}
                required
                disabled={busy || readOnly}
              />
            </label>
            {kind === "documents" && (
              <label className="checkbox">
                <input
                  name="synthetic-approved"
                  type="checkbox"
                  checked={synthetic}
                  onChange={(e) => setSynthetic(e.target.checked)}
                />
                This is approved application-owned synthetic content.
              </label>
            )}
            <p className="form-help">
              Extraction uses the configured deterministic path. External Gemini
              calls stay disabled; no AI quota is consumed.
            </p>
            <button
              className="primary"
              type="submit"
              disabled={busy || readOnly}
            >
              <Upload size={15} aria-hidden="true" />
              {busy
                ? "Importing source…"
                : kind === "documents"
                  ? "Upload & parse document"
                  : "Validate & import CSV"}
            </button>
            {readOnly && <p>Auditor sessions cannot import records.</p>}
          </form>
          {error !== undefined && <ErrorNotice error={error} />}{" "}
          {result !== undefined && (
            <div role="status" className="import-result">
              <h3>Server result</h3>
              <Fields
                value={{
                  status: record(result).status,
                  reason: record(result).reason,
                  result: record(result).result,
                }}
              />
            </div>
          )}
        </Section>
        <div>
          <Section title="Recent imports" meta={<Badge>Server records</Badge>}>
            {state.loading && <Loading />}
            {state.error !== undefined && (
              <ErrorNotice
                error={state.error}
                retry={() => setRevision((v) => v + 1)}
              />
            )}{" "}
            {state.data?.imports.map((i) => (
              <div key={i.id} className="import-row">
                <strong>{i.source_name}</strong>
                <Badge>{human(i.status)}</Badge>
                <small>
                  {human(i.kind)} · {i.row_count} rows · {date(i.created_at)}
                </small>
              </div>
            ))}
            {state.data?.imports.length === 0 && <Empty>No imports yet.</Empty>}
          </Section>
          <Section title="Original documents">
            {state.data?.documents.map((d) => (
              <div key={d.id} className="import-row">
                <strong>{d.source_name}</strong>
                <Badge>{human(d.parse_status)}</Badge>
                <small>
                  {d.mime} · {short(d.id)} · {d.size_bytes} bytes
                </small>
              </div>
            ))}
            {state.data?.documents.length === 0 && (
              <Empty>No documents uploaded.</Empty>
            )}
          </Section>
        </div>
      </div>
    </main>
  );
}
