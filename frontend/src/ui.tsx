import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  RefreshCw,
} from "lucide-react";
import { ApiError, human, record, text } from "./api";

export function useResource<T>(load: () => Promise<T>) {
  const [state, set] = useState<{
    data?: T;
    error?: unknown;
    loading: boolean;
  }>({ loading: true });
  useEffect(() => {
    let active = true;
    set((s) => ({ ...s, loading: true, error: undefined }));
    load()
      .then((data) => {
        if (active) set({ data, loading: false });
      })
      .catch((error) => {
        if (active) set({ error, loading: false });
      });
    return () => {
      active = false;
    };
  }, [load]);
  return state;
}

const explanations: Record<string, string> = {
  SERVER_UNAVAILABLE:
    "The application server is unreachable. Check that FastAPI is running, then retry.",
  MALFORMED_API_RESPONSE:
    "The server returned an unreadable response. Retry or inspect the local server log.",
  MALFORMED_LIST_RESPONSE:
    "The API response does not match its contract. No records have been assumed.",
  STALE_CORRELATION_CASE:
    "This case changed while you were reviewing it. Refresh and inspect the new evidence before deciding.",
  STALE_CORRELATION_EVIDENCE:
    "The source proof changed. Refresh the task and review it again.",
  AUTHORITATIVE_CORRELATION_REQUIRED:
    "An independently authenticated remittance is required. A reviewer label cannot replace source proof.",
  REVIEW_CONTROLLER_REQUIRED:
    "A controller session is required for this review decision.",
  VERIFIED_FINANCE_IDENTITY_UNAVAILABLE:
    "Production authority is not configured. This session cannot grant financial permission.",
  DEMO_LOGIN_FAILED:
    "The username or password was not accepted. Check the local session access file.",
};
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const api = error instanceof ApiError ? error : undefined;
  const message = api
    ? explanations[api.code] ||
      (api.status === 403
        ? "Your session does not have permission for this operation."
        : api.status === 401
          ? "Your session has expired or is not authorized. Sign in again."
          : api.status === 409
            ? "The server rejected changed or conflicting inputs. Refresh before continuing."
            : "This request failed. Retry or inspect the local application log.")
    : "This section could not be loaded. Retry to retrieve its current state.";
  return (
    <div className="error-note" role="alert">
      <AlertTriangle size={17} aria-hidden="true" />
      <div>
        <strong>{message}</strong>
        {api && (
          <small>
            {api.status ? `HTTP ${api.status} · ` : ""}
            {api.code}
          </small>
        )}
      </div>
      {retry && (
        <button onClick={retry}>
          <RefreshCw size={14} aria-hidden="true" />
          Retry
        </button>
      )}
    </div>
  );
}
export function Badge({
  kind = "neutral",
  children,
}: {
  kind?: string;
  children: ReactNode;
}) {
  return <span className={`badge ${kind}`}>{children}</span>;
}
export function Provenance({
  kind,
  children,
}: {
  kind: "source" | "check" | "ai" | "human" | "authority" | "offline";
  children?: ReactNode;
}) {
  const labels = {
    source: "Source verified",
    check: "Rules check",
    ai: "AI generated",
    human: "Human decision",
    authority: "Financial permission not granted",
    offline: "Demo scenario",
  };
  return (
    <span className={`provenance ${kind}`}>
      {kind === "source" ? (
        <Check size={12} aria-hidden="true" />
      ) : (
        <span aria-hidden="true">
          {kind === "human"
            ? "↳"
            : kind === "ai" || kind === "offline"
              ? "◇"
              : "—"}
        </span>
      )}
      <span>{children || labels[kind]}</span>
    </span>
  );
}
export function Section({
  title,
  meta,
  children,
  className = "",
}: {
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`section ${className}`}>
      <header className="section-head">
        <h2>{title}</h2>
        {meta}
      </header>
      {children}
    </section>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
export function Loading({
  label = "Loading current records…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <RefreshCw size={16} aria-hidden="true" />
      {label}
    </div>
  );
}

export function ConfirmDialog({
  title,
  children,
  action,
  confirm,
  close,
}: {
  title: string;
  children: ReactNode;
  action: string;
  confirm: () => Promise<void>;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    const d = ref.current;
    const prior = document.activeElement as HTMLElement;
    d?.showModal();
    return () => {
      d?.close();
      prior?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) close();
      }}
      aria-labelledby="decision-title"
    >
      <h2 id="decision-title">{title}</h2>
      {children}
      {error !== undefined && <ErrorNotice error={error} />}
      <footer>
        <button onClick={close} disabled={busy} autoFocus>
          Cancel
        </button>
        <button
          className="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await confirm();
              close();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Recording decision…" : action}
          <ArrowRight size={16} aria-hidden="true" />
        </button>
      </footer>
    </dialog>
  );
}

export function Fields({ value }: { value: unknown }) {
  const rows = Object.entries(record(value));
  if (!rows.length) return null;
  return (
    <dl className="fields">
      {rows.map(([key, v]) => (
        <div key={key}>
          <dt>{human(key)}</dt>
          <dd>
            {typeof v === "boolean" ? (
              v ? (
                "Yes"
              ) : (
                "No"
              )
            ) : v === null || v === undefined ? (
              "—"
            ) : Array.isArray(v) ? (
              v.length ? (
                v.map((a, i) => (
                  <div key={i}>
                    {typeof a === "object" ? (
                      <Fields value={a} />
                    ) : (
                      human(a) || String(a)
                    )}
                  </div>
                ))
              ) : (
                "None"
              )
            ) : typeof v === "object" ? (
              <Fields value={v} />
            ) : typeof v === "string" ? (
              text(v).length > 90 ? (
                <span className="wrap">{v}</span>
              ) : (
                human(v)
              )
            ) : (
              String(v)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Disclosure({
  title,
  children,
  open = false,
}: {
  title: ReactNode;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details open={open || undefined}>
      <summary>
        {title}
        <ChevronDown size={15} aria-hidden="true" />
      </summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}
export function Saved({ children }: { children: ReactNode }) {
  return (
    <p className="saved" role="status">
      <Check size={14} aria-hidden="true" />
      {children}
    </p>
  );
}
