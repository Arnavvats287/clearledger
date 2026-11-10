import { parse, stringify } from "lossless-json";
import type { components } from "./generated";
import { PortfolioCache, publicReadKey } from "./portfolio-cache";

const deploymentOrigin = import.meta.env.VITE_API_BASE_URL as
  string | undefined;
export const publicPortfolio = Boolean(deploymentOrigin);
function apiUrl(path: string) {
  return deploymentOrigin ? `${deploymentOrigin}${path}` : `/api${path}`;
}

type Cash<T> = T extends readonly (infer U)[]
  ? Cash<U>[]
  : T extends object
    ? {
        [K in keyof T]: K extends `${string}_paise`
          ? bigint | (null extends T[K] ? null : never)
          : Cash<T[K]>;
      }
    : T;
export type Model<N extends keyof components["schemas"]> = Cash<
  components["schemas"][N]
>;
export type Case = Model<"CaseView">;
export type Claim = Model<"ClaimView">;
export type Run = Model<"RunView">;
export type Finding = Model<"FindingView">;
export type Task = Model<"TaskView">;
export type Decision = Model<"DecisionView">;
export type Doc = Model<"DocumentView">;
export type Extraction = Model<"ExtractionView">;
export type Invoice = Model<"InvoiceView">;
export type Receipt = Model<"ReceiptView">;
export type Customer = Model<"CustomerView">;
export type Span = Model<"Span">;
export type Trace = {
  id: string;
  node: string;
  metadata: Record<string, unknown>;
  created_at: string;
};
export type Me = {
  subject: string;
  role: "AR_ANALYST" | "CONTROLLER" | "AUDITOR";
  authority: "VERIFIED" | "LOCAL_DEMO_ONLY";
  financial_authority: false;
  included_available?: boolean;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export function decode(text: string): unknown {
  const value = parse(text, undefined, (token) => {
    if (!/^-?\d+$/.test(token))
      throw new ApiError(502, "NON_INTEGER_API_NUMBER");
    const n = BigInt(token);
    return n <= BigInt(Number.MAX_SAFE_INTEGER) &&
      n >= BigInt(Number.MIN_SAFE_INTEGER)
      ? Number(n)
      : n;
  });
  function visit(v: unknown, key = ""): unknown {
    if (key.endsWith("_paise") && v !== null) {
      if (
        typeof v !== "bigint" &&
        (typeof v !== "number" || !Number.isSafeInteger(v))
      )
        throw new ApiError(502, "INVALID_MONEY_RESPONSE");
      return BigInt(v);
    }
    if (Array.isArray(v)) return v.map((x) => visit(x));
    if (v && typeof v === "object")
      return Object.fromEntries(
        Object.entries(v).map(([k, x]) => [k, visit(x, k)]),
      );
    return v;
  }
  return visit(value);
}

export class Client {
  private reads = new PortfolioCache();
  constructor(private token: string) {}
  peek<T>(path: string) {
    return publicPortfolio ? this.reads.peek<T>(path) : undefined;
  }
  invalidate(path: string, related: string[] = []) {
    if (!publicPortfolio) return;
    this.reads.invalidate((key) =>
      [path, ...related].some(
        (p) => key === p || key.startsWith(p + "/") || key.startsWith(p + "?"),
      ),
    );
  }
  clear() {
    this.reads.clear();
  }
  request<T>(
    path: string,
    method = "GET",
    body?: unknown,
    key?: string,
    signal?: AbortSignal,
  ): Promise<T> {
    const cached =
      publicPortfolio &&
      method === "GET" &&
      body === undefined &&
      !signal &&
      publicReadKey(path);
    const load = () => this.fetchRequest<T>(path, method, body, key, signal);
    return cached ? this.reads.read(cached, load) : load();
  }
  sourceText(
    doc: Pick<Doc, "id" | "version" | "content_sha256" | "canonical_sha256">,
  ): Promise<SourceText> {
    const path = `/documents/${doc.id}/text`;
    if (!publicPortfolio) return this.request<SourceText>(path);
    return this.reads.read(
      `source:${doc.id}:${doc.version}:${doc.content_sha256}:${doc.canonical_sha256}`,
      async () => {
        const source = await this.request<SourceText>(path);
        if (
          source.document_version !== doc.version ||
          source.raw_sha256 !== doc.content_sha256 ||
          source.canonical_sha256 !== doc.canonical_sha256
        )
          throw new ApiError(409, "SOURCE_VERSION_CHANGED");
        return source;
      },
    );
  }
  private async fetchRequest<T>(
    path: string,
    method = "GET",
    body?: unknown,
    key?: string,
    signal?: AbortSignal,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(apiUrl(path), {
        method,
        signal,
        cache: "no-store",
        headers: {
          ...(this.token && (!publicPortfolio || path.startsWith("/portfolio/"))
            ? {
                Authorization: `${publicPortfolio ? "Portfolio" : "ReviewDemo"} ${this.token}`,
              }
            : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(method !== "GET" && !publicPortfolio
            ? {
                "Idempotency-Key": key || crypto.randomUUID(),
                "X-Actor-ID": "workstation",
              }
            : {}),
        },
        body: body === undefined ? undefined : stringify(body),
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new ApiError(0, "SERVER_UNAVAILABLE");
    }
    return this.readResponse<T>(response);
  }
  async portfolioUpload<T>(
    file: File,
    mime: string,
    geminiKey?: string,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(apiUrl("/portfolio/extract"), {
        method: "POST",
        cache: "no-store",
        redirect: "error",
        headers: {
          Authorization: `Portfolio ${this.token}`,
          "Content-Type": mime,
          "X-Portfolio-Filename": encodeURIComponent(file.name),
          "X-Portfolio-Consent": "true",
          ...(geminiKey
            ? {
                "X-Portfolio-Gemini-Key": geminiKey,
                "X-Portfolio-Gemini-Consent": "true",
              }
            : {}),
        },
        body: file,
      });
    } catch {
      throw new ApiError(0, "SERVER_UNAVAILABLE");
    }
    return this.readResponse<T>(response);
  }
  private async readResponse<T>(response: Response): Promise<T> {
    if (publicPortfolio && response.status === 503)
      throw new ApiError(503, "PORTFOLIO_API_UNAVAILABLE");
    let data: unknown;
    try {
      data = decode(await response.text());
    } catch {
      throw new ApiError(response.status || 502, "MALFORMED_API_RESPONSE");
    }
    if (!response.ok) {
      const d = record(data).detail;
      throw new ApiError(
        response.status,
        typeof d === "string" && /^[A-Z0-9_: .-]{1,160}$/.test(d)
          ? d
          : `REQUEST_${response.status}`,
      );
    }
    return data as T;
  }
  async list<T>(path: string, signal?: AbortSignal): Promise<T[]> {
    const rows = await this.request<unknown>(
      path,
      "GET",
      undefined,
      undefined,
      signal,
    );
    if (!Array.isArray(rows) || rows.some((r) => !r || typeof r !== "object"))
      throw new ApiError(502, "MALFORMED_LIST_RESPONSE");
    return rows as T[];
  }
  async case(id: string): Promise<Case> {
    const row = await this.request<Case>(`/cases/${id}`);
    if (
      !row ||
      typeof row.id !== "string" ||
      !Number.isSafeInteger(row.version) ||
      typeof row.context_sha256 !== "string" ||
      !Array.isArray(row.document_ids)
    )
      throw new ApiError(502, "MALFORMED_CASE_RESPONSE");
    return row;
  }
  async raw(
    path: string,
    bytes: File,
    headers: Record<string, string>,
    key: string,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(apiUrl(path), {
        method: "POST",
        headers: {
          Authorization: `ReviewDemo ${this.token}`,
          "Idempotency-Key": key,
          "X-Actor-ID": "workstation",
          ...headers,
        },
        body: bytes,
      });
    } catch {
      throw new ApiError(0, "SERVER_UNAVAILABLE");
    }
    const data = decode(await response.text());
    if (!response.ok)
      throw new ApiError(
        response.status,
        typeof record(data).detail === "string"
          ? String(record(data).detail)
          : `IMPORT_${response.status}`,
      );
    return data;
  }
  async original(id: string): Promise<Blob> {
    const response = await fetch(apiUrl(`/documents/${id}/original`), {
      headers: this.token ? { Authorization: `ReviewDemo ${this.token}` } : {},
      cache: "no-store",
    });
    if (!response.ok)
      throw new ApiError(response.status, "ORIGINAL_UNAVAILABLE");
    return response.blob();
  }
}

export function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}
export function human(value: unknown): string {
  return text(value)
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
}
export function money(value: bigint | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const v = value < 0n ? -value : value;
  return `${value < 0n ? "−" : ""}₹${new Intl.NumberFormat("en-IN").format(v / 100n)}.${(v % 100n).toString().padStart(2, "0")}`;
}
export function date(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.valueOf())
    ? "—"
    : new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(d);
}
export function short(id: string): string {
  return id.slice(0, 8);
}
export function sliceSpan(page: string, span: Span): [string, string, string] {
  const points = Array.from(page);
  if (
    !Number.isSafeInteger(span.start) ||
    !Number.isSafeInteger(span.end) ||
    span.start < 0 ||
    span.end <= span.start ||
    span.end > points.length ||
    points.slice(span.start, span.end).join("") !== span.quote
  )
    throw new ApiError(409, "SOURCE_SPAN_MISMATCH");
  return [
    points.slice(0, span.start).join(""),
    span.quote,
    points.slice(span.end).join(""),
  ];
}
export const basis = (c: Case) => ({
  expected_case_version: c.version,
  expected_context_sha256: c.context_sha256,
});

export type Bundle = {
  case: Case;
  claims: Claim[];
  tasks: Task[];
  runs: Run[];
  findings: Finding[];
  trace: Trace[];
  accessError?: ApiError;
};
export type SourceText = {
  document_version: number;
  raw_sha256: string;
  canonical_sha256: string;
  pages: string[];
};
export type AssessmentBundle = Omit<Bundle, "findings" | "trace"> & {
  findings: Pick<Finding, "state" | "unknowns" | "next_action">[];
  trace: Pick<Trace, "node" | "metadata">[];
};
export type PortfolioSnapshot = {
  cases: AssessmentBundle[];
  customers: Customer[];
  invoices: Invoice[];
  receipts: Receipt[];
  documents: Doc[];
  banks: Pick<
    Model<"BankView">,
    "id" | "external_transaction_id" | "payer_name" | "occurred_at_source"
  >[];
};
export const portfolioBootstrap = "/portfolio/bootstrap";
export const portfolioCase = (id: string) => `/portfolio/cases/${id}`;
export async function references<T extends { id: string }>(
  api: Client,
  path: string,
  ids: string[],
): Promise<T[]> {
  const wanted = new Set(ids),
    found = new Map<string, T>();
  if (!wanted.size) return [];
  if (wanted.size > 400) throw new ApiError(503, "QUEUE_REFERENCE_BUDGET");
  for (let page = 0; page < 20; page++) {
    const rows = await api.list<T>(`${path}?limit=100&offset=${page * 100}`);
    for (const row of rows) if (wanted.has(row.id)) found.set(row.id, row);
    if (found.size === wanted.size) return [...found.values()];
    if (rows.length < 100) break;
  }
  throw new ApiError(503, "QUEUE_REFERENCE_BUDGET");
}
export async function bundle(api: Client, c: Case): Promise<Bundle> {
  const [claims, runs, tasks] = await Promise.all([
    api.list<Claim>(`/cases/${c.id}/claims`),
    api.list<Run>(`/cases/${c.id}/investigations`),
    api
      .list<Task>(`/review/cases/${c.id}/correlation-tasks`)
      .catch((e) => e as ApiError),
  ]);
  const current = runs.find((r) => !r.is_stale) || runs[0];
  const [findings, trace] = current
    ? await Promise.all([
        api.list<Finding>(`/investigations/${current.id}/findings`),
        api.list<Trace>(`/investigations/${current.id}/trace`),
      ])
    : [[], []];
  return {
    case: c,
    claims,
    runs,
    tasks: tasks instanceof ApiError ? [] : tasks,
    findings,
    trace,
    accessError: tasks instanceof ApiError ? tasks : undefined,
  };
}

// Display projections only. Authority, transitions, currentness and proofs stay server-side.
export function presentation(b: AssessmentBundle) {
  const synth = b.trace.find(
    (t) =>
      t.node === "investigator_synthesize" &&
      record(t.metadata).fallback === false,
  );
  const s = record(record(synth?.metadata).synthesis);
  const next = b.trace.find(
    (t) => t.node === "human_review_or_request_evidence",
  );
  const finding = b.findings[0];
  const action =
    text(record(next?.metadata).next_action) ||
    text(s.next_action) ||
    finding?.next_action ||
    b.tasks.find((t) => t.status === "PENDING")?.next_action ||
    b.case.attention_codes[0] ||
    b.case.state;
  const state = text(s.state) || finding?.state || b.case.state;
  const stale = b.case.is_stale || !!b.runs[0]?.is_stale;
  return {
    action: stale ? "REFRESH_INPUTS" : action,
    state: stale ? "STALE" : state,
    conflict:
      state === "CONFLICTING_EVIDENCE" ||
      finding?.unknowns.includes("CONFLICTING_EVIDENCE"),
    stale,
    supported: !stale && state === "SUPPORTED",
    missing:
      action === "REQUEST_EVIDENCE" || b.case.state === "AWAITING_EVIDENCE",
  };
}
