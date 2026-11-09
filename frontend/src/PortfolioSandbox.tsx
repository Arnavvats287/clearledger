import { useRef, useState, type FormEvent } from "react";
import { ApiError, human, money, type Client, type Span } from "./api";
import { Badge } from "./ui";

const formats: Record<string, string> = {
  txt: "text/plain",
  json: "application/json",
  eml: "message/rfc822",
  pdf: "application/pdf",
};
type Ref = { value: string; span: Span };
type Extraction = {
  invoice_references: Ref[];
  utr_references: Ref[];
  claims: {
    category: string;
    amount_paise: bigint | null;
    amount_span: Span | null;
  }[];
  uncertainty: string;
};
type Upload = {
  filename: string;
  pages: string[];
  parse_status: string;
  deterministic_status: string;
  extraction: Extraction | null;
  ai: null | {
    model: string;
    status: string;
    proposal: Extraction | null;
    validated: Extraction | null;
  };
};
type Citation = { alias: string; quote: string; page: number };
type Included = {
  model: string;
  status: string;
  proposal: { state: string; next_action: string } | null;
  finding: string;
  next_action: string;
  amount_paise: bigint;
  offered: Citation[];
  citations: Citation[];
};
const errors: Record<string, string> = {
  REQUEST_TOO_LARGE: "Choose a file of 2 MiB or less.",
  UNSUPPORTED_DOCUMENT_TYPE: "Choose a PDF, TXT, JSON or EML document.",
  INVALID_DOCUMENT_FILENAME:
    "Use a simple filename with letters, numbers, spaces, dots, dashes or underscores.",
  DOCUMENT_PARSE_FAILED:
    "This file could not be parsed safely. Try the sample remittance or a plain-text copy.",
  DEMO_INCLUDED_DAILY_LIMIT:
    "Today's included live AI demo quota has been used. Deterministic mode remains available, or you can use your own Gemini key.",
  DEMO_INCLUDED_SESSION_LIMIT:
    "This session has already used its included live attempt.",
  DEMO_GEMINI_NOT_CONFIGURED: "The included live run is currently unavailable.",
  DEMO_BYOK_SESSION_LIMIT:
    "This session has reached its three visitor-key attempts. Deterministic mode remains available.",
  DEMO_BYOK_DAILY_LIMIT:
    "Today's visitor-key limit has been reached. Deterministic mode remains available.",
  DEMO_UPLOADS_SESSION_LIMIT: "This session has reached its upload limit.",
  DEMO_UPLOADS_DAILY_LIMIT: "Today's document sandbox limit has been reached.",
  SANDBOX_BUSY: "The sandbox is processing another request. Try again shortly.",
  DEMO_SESSION_REQUIRED: "Your demo session expired. Sign out and enter again.",
  GEMINI_KEY_OR_CONSENT_REQUIRED:
    "Enter a valid-looking Gemini API key and confirm the Google processing notice.",
};
const errorText = (err: unknown) =>
  err instanceof ApiError
    ? errors[err.code] ||
      "The sandbox could not complete this request. Try again in a moment."
    : "The sandbox could not complete this request.";
const outcome: Record<string, string> = {
  SOURCE_CHECKED: "Source checks passed",
  ABSTAINED: "Needs review",
  BLOCKED: "Withheld before Gemini",
  PROVIDER_UNAVAILABLE: "Gemini unavailable",
  REJECTED: "Rejected by source validation",
};
function Fields({
  data,
  select,
}: {
  data: Extraction | null;
  select?: (span: Span) => void;
}) {
  if (!data) return <p>No source-backed fields to show.</p>;
  const items = [
    ...data.invoice_references.map((r) => ({
      label: "Invoice",
      value: r.value,
      span: r.span,
    })),
    ...data.utr_references.map((r) => ({
      label: "UTR",
      value: r.value,
      span: r.span,
    })),
    ...data.claims.map((r) => ({
      label: `${human(r.category)} claim`,
      value: money(r.amount_paise),
      span: r.amount_span,
    })),
  ];
  if (!items.length) return <p>No references or amounts were selected.</p>;
  return (
    <dl className="sandbox-fields">
      {items.map((item, i) => (
        <div key={i}>
          <dt>{item.label}</dt>
          <dd>
            {select && item.span ? (
              <button type="button" onClick={() => select(item.span!)}>
                {item.value}
              </button>
            ) : (
              item.value
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function PortfolioSandbox({
  api,
  includedAvailable,
}: {
  api: Client;
  includedAvailable: boolean;
}) {
  const [file, setFile] = useState<File>(),
    [consent, setConsent] = useState(false),
    [byok, setByok] = useState(false),
    [googleConsent, setGoogleConsent] = useState(false),
    [upload, setUpload] = useState<Upload>(),
    [span, setSpan] = useState<Span>(),
    [uploadError, setUploadError] = useState(""),
    [included, setIncluded] = useState<Included>(),
    [includedError, setIncludedError] = useState(""),
    [attempted, setAttempted] = useState(false),
    [busy, setBusy] = useState<"upload" | "included">();
  const keyInput = useRef<HTMLInputElement>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !consent || busy) return;
    const key = byok ? keyInput.current?.value.trim() : undefined;
    if (keyInput.current) keyInput.current.value = "";
    const mime = formats[file.name.split(".").pop()?.toLowerCase() ?? ""];
    if (!mime || file.size > 2_097_152) {
      setUploadError(
        !mime ? errors.UNSUPPORTED_DOCUMENT_TYPE : errors.REQUEST_TOO_LARGE,
      );
      return;
    }
    if (byok && (!key || !googleConsent)) return;
    setBusy("upload");
    setUploadError("");
    setUpload(undefined);
    setSpan(undefined);
    try {
      setUpload(await api.portfolioUpload<Upload>(file, mime, key));
    } catch (err) {
      setUploadError(errorText(err));
    } finally {
      setBusy(undefined);
    }
  }
  async function run() {
    setBusy("included");
    setIncludedError("");
    try {
      setIncluded(await api.request<Included>("/portfolio/included", "POST"));
      setAttempted(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "DEMO_INCLUDED_SESSION_LIMIT")
        setAttempted(true);
      setIncludedError(errorText(err));
    } finally {
      setBusy(undefined);
    }
  }
  return (
    <main id="main" className="queue-page sandbox">
      <header className="case-heading">
        <div>
          <h1 tabIndex={-1}>Import & documents</h1>
          <p>
            Read a remittance, check its references and inspect the exact
            source.
          </p>
        </div>
        <Badge>Ephemeral sandbox</Badge>
      </header>
      <div className="sandbox-grid">
        <section className="sandbox-panel" aria-labelledby="upload-heading">
          <h2 id="upload-heading">Upload a demo document</h2>
          <p>
            PDF, TXT, JSON or EML, up to 2 MiB. Uploads are processed for the
            current request and are never added to the shared dataset.
          </p>
          <a href={`${import.meta.env.BASE_URL}sample-remittance.txt`} download>
            Download sample remittance
          </a>
          <form onSubmit={(event) => void submit(event)}>
            <label>
              Document{" "}
              <input
                type="file"
                accept=".pdf,.txt,.json,.eml"
                required
                onChange={(e) => setFile(e.currentTarget.files?.[0])}
              />
            </label>
            <label className="sandbox-check">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.currentTarget.checked)}
              />
              <span>
                I confirm this is synthetic or non-confidential content suitable
                for a public portfolio demo.
              </span>
            </label>
            <fieldset>
              <legend>AI assistance</legend>
              <p>Source checks govern every extraction result.</p>
              <label className="sandbox-check">
                <input
                  type="radio"
                  name="mode"
                  checked={!byok}
                  onChange={() => setByok(false)}
                />{" "}
                Deterministic only
              </label>
              <label className="sandbox-check">
                <input
                  type="radio"
                  name="mode"
                  checked={byok}
                  onChange={() => setByok(true)}
                />{" "}
                Use my Gemini key
              </label>
              {byok && (
                <div className="sandbox-key">
                  <p>
                    The privacy-filtered source text will be sent to Google
                    Gemini. ClearLedger does not retain your key. Do not upload
                    personal, confidential, regulated, customer or production
                    data. Your Google project may incur charges.
                  </p>
                  <a
                    href="https://ai.google.dev/gemini-api/terms"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Google Gemini API terms ↗
                  </a>
                  <label className="sandbox-check">
                    <input
                      type="checkbox"
                      required
                      checked={googleConsent}
                      onChange={(e) =>
                        setGoogleConsent(e.currentTarget.checked)
                      }
                    />
                    <span>
                      I am 18 or older, am using Gemini for a professional
                      purpose in a supported region, and consent to this Google
                      request.
                    </span>
                  </label>
                  <label>
                    Gemini API key{" "}
                    <input
                      ref={keyInput}
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      minLength={20}
                      maxLength={180}
                      required
                    />
                  </label>
                </div>
              )}
            </fieldset>
            <button
              className="primary"
              type="submit"
              disabled={!file || !consent || !!busy}
            >
              {busy === "upload" ? "Processing document…" : "Extract document"}
            </button>
            {uploadError && <p role="alert">{uploadError}</p>}
          </form>
        </section>
        <section
          className="sandbox-panel"
          id="live-ai"
          aria-labelledby="live-ai-heading"
        >
          <h2 id="live-ai-heading" tabIndex={-1}>
            Included live Gemini demo
          </h2>
          <p>
            Review a bundled damage claim where the warehouse record is present
            and the signed proof of delivery is missing. This run sends only the
            bundled fixture.
          </p>
          <p>
            One included live attempt per session, subject to daily
            availability. Use only for professional purposes if you are 18 or
            older and in a{" "}
            <a
              href="https://ai.google.dev/gemini-api/docs/available-regions"
              target="_blank"
              rel="noreferrer"
            >
              supported region
            </a>
            .
          </p>
          <button
            type="button"
            disabled={!includedAvailable || !!busy || attempted}
            onClick={() => void run()}
          >
            {busy === "included"
              ? "Running live investigation…"
              : "Run one live AI investigation"}
          </button>
          {!includedAvailable && (
            <p role="status">
              Included live AI is currently unavailable. You can still extract
              documents with deterministic mode or use your own Gemini key.
            </p>
          )}
          {includedError && <p role="alert">{includedError}</p>}
          {included && (
            <div aria-live="polite" className="sandbox-result">
              <Badge>{outcome[included.status]}</Badge>
              <p>Model · {included.model}</p>
              <h3>Model proposal</h3>
              <p>
                {included.proposal
                  ? human(included.proposal.state)
                  : "No accepted typed proposal was returned."}
              </p>
              <h3>Verified ClearLedger result</h3>
              <p>
                {money(included.amount_paise)} · {human(included.finding)} ·{" "}
                {human(included.next_action)}
              </p>
              <h3>Evidence aliases offered</h3>
              <ul>
                {included.offered.map((r) => (
                  <li key={r.alias}>
                    <code>{r.alias}</code> · Page {r.page} · {r.quote}
                  </li>
                ))}
              </ul>
              <h3>Validated model citations</h3>
              {included.citations.length ? (
                <ul>
                  {included.citations.map((r) => (
                    <li key={r.alias}>
                      <code>{r.alias}</code> · {r.quote}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No model citations were accepted.</p>
              )}
            </div>
          )}
          <p>
            Customer, invoice and bank imports are available in the local
            workstation. The public sandbox cannot change the seeded ledger or
            cases.
          </p>
        </section>
      </div>
      {upload && (
        <section
          className="sandbox-panel sandbox-output"
          aria-labelledby="extraction-heading"
        >
          <h2 id="extraction-heading">Extraction result</h2>
          <p role="status">
            {upload.filename} · {human(upload.parse_status)}
          </p>
          <div className="sandbox-grid">
            <div>
              <h3>Deterministic extraction</h3>
              <Badge>{outcome[upload.deterministic_status]}</Badge>
              <Fields data={upload.extraction} select={setSpan} />
              {upload.ai && (
                <div className="sandbox-result">
                  <h3>Gemini-assisted extraction</h3>
                  <p>
                    {upload.ai.model} · {outcome[upload.ai.status]}
                  </p>
                  {upload.ai.status === "BLOCKED" && (
                    <p>
                      The document exceeded the AI text limit or contained data
                      the privacy filter would not transmit.
                    </p>
                  )}
                  <h4>Typed model proposal</h4>
                  <Fields data={upload.ai.proposal} />
                  <h4>Validated result</h4>
                  <Fields data={upload.ai.validated} select={setSpan} />
                </div>
              )}
            </div>
            <div>
              <h3>Parsed source</h3>
              {upload.pages.map((page, i) => {
                const chars = Array.from(page);
                return (
                  <div key={i}>
                    <p>Page {i + 1}</p>
                    <pre>
                      {span?.page === i + 1 ? (
                        <>
                          {chars.slice(0, span.start).join("")}
                          <mark>
                            {chars.slice(span.start, span.end).join("")}
                          </mark>
                          {chars.slice(span.end).join("")}
                        </>
                      ) : (
                        page || "No text layer on this page."
                      )}
                    </pre>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
