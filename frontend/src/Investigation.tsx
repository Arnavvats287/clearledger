import { useCallback, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowRight, FileText } from "lucide-react";
import {
  Client,
  basis,
  type Me,
  type Model,
  type Trace,
  date,
  human,
  money,
  presentation,
  record,
  short,
  text,
} from "./api";
import {
  Badge,
  Disclosure,
  Empty,
  ErrorNotice,
  Fields,
  Loading,
  Provenance,
  Section,
  useResource,
} from "./ui";
import type { Loaded } from "./workstation";
import { ReviewAction } from "./ReviewAction";
import type { Selection } from "./Documents";
const nodes: Record<string, string> = {
  director_route: "Director route",
  investigator_plan: "Investigator plan",
  evidence_tool: "Evidence retrieval",
  evidence_verify: "Evidence verification",
  investigator_synthesize: "Investigator synthesis",
  policy_validate: "Policy validation",
  human_review_or_request_evidence: "Required human action",
  PROVIDER: "Provider operation",
  TOOL: "Read-only evidence tool",
  VERIFY: "Deterministic verification",
  EMIT: "Persisted finding",
};

export function Investigation({
  api,
  data,
  refresh,
  inspect,
  me,
}: {
  api: Client;
  data: Loaded;
  refresh: () => void;
  inspect: (s: Selection) => void;
  me: Me;
}) {
  const { b } = data;

  const [params, setParams] = useSearchParams();

  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [selected, setSelected] = useState("");

  const admission = useRef<{ snapshot: string; key: string } | undefined>(
    undefined,
  );

  const run =
    b.runs.find((r) => r.id === selected) ||
    b.runs.find((r) => !r.is_stale) ||
    b.runs[0];

  const load = useCallback(async () => {
    if (!run)
      return {
        trace: [] as Trace[],
        findings: [] as Model<"FindingView">[],
        sources: [] as Model<"RecordView">[],
      };

    const [trace, findings] = await Promise.all([
      api.list<Trace>(`/investigations/${run.id}/trace`),
      api.list<Model<"FindingView">>(`/investigations/${run.id}/findings`),
    ]);

    const query = new URLSearchParams({
      expected_case_version: String(b.case.version),
      expected_context_sha256: b.case.context_sha256,
      customer_id: b.case.customer_id || "",
    });

    const ids = [
      ...new Set(findings.flatMap((f) => f.citations.map((c) => c.record_id))),
    ];

    const sources = b.case.customer_id
      ? await Promise.all(
          ids
            .slice(0, 20)
            .map((id) =>
              api.request<Model<"RecordView">>(
                `/cases/${b.case.id}/evidence/records/${id}?${query}`,
              ),
            ),
        )
      : [];

    return { trace, findings, sources };
  }, [api, run, b.case]);

  const state = useResource(load),
    p = presentation(b);

  async function start() {
    setBusy(true);
    setError(undefined);

    try {
      const body = {
        ...basis(b.case),
        claim_ids: b.claims
          .filter((c) => c.state !== "RESOLVED")
          .map((c) => c.id),
        allow_external: false,
      };

      const snapshot = JSON.stringify(body);

      if (admission.current?.snapshot !== snapshot)
        admission.current = { snapshot, key: crypto.randomUUID() };

      await api.request(
        `/cases/${b.case.id}/investigations`,
        "POST",
        body,
        admission.current!.key,
      );
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const ordered = [
    "director_route",
    "investigator_plan",
    "evidence_tool",
    "evidence_verify",
    "investigator_synthesize",
    "policy_validate",
    "human_review_or_request_evidence",
  ];

  const stages = ordered.flatMap((name) => {
    const row = state.data?.trace.find((t) => t.node === name);
    return row ? [row] : [];
  });

  const active =
    stages.find((t) => t.node === params.get("step")) ||
    stages.find((t) => t.node === "investigator_synthesize") ||
    stages[0];

  const meta = record(active?.metadata),
    content = record(meta.plan || meta.synthesis || meta.verification);

  const generated =
    active &&
    ["investigator_plan", "investigator_synthesize"].includes(active.node) &&
    meta.fallback !== true;

  const origin = generated
    ? run?.provider === "fake"
      ? "offline"
      : "ai"
    : "check";

  const runtime =
    state.data?.trace.filter((t) =>
      ["PROVIDER", "TOOL", "VERIFY", "EMIT"].includes(t.node),
    ) || [];

  const evidenceName = (id: string) =>
    (
      ({
        POD: "Proof of delivery",
        WMS: "Warehouse delivery",
        REMITTANCE: "Remittance",
        CONTRACT: "Contract",
      }) as Record<string, string>
    )[state.data?.sources.find((r) => r.id === id)?.kind || ""] ||
    "Source record";

  return (
    <>
      <Section
        title="Technical investigation trace"
        meta={
          run && (
            <Badge>
              {run.provider === "fake" ? "Demo scenario" : human(run.provider)}
            </Badge>
          )
        }
      >
        <ReviewAction api={api} data={data} me={me} refresh={refresh} />
        <div className="investigation-intro">
          <div>
            <h3>{human(p.action)}</h3>
            <p>
              Recommendations are checked against source facts. They grant no
              financial authority.
            </p>
          </div>
          <button
            onClick={() => void start()}
            disabled={
              busy ||
              me.role === "AUDITOR" ||
              !b.claims.length ||
              b.case.is_stale
            }
          >
            {busy ? "Scheduling…" : "Run current investigation"}
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </div>

        {error !== undefined && <ErrorNotice error={error} />}

        {b.runs.length > 0 && (
          <label className="run-select">
            Investigation history
            <select
              value={run?.id || ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              {b.runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {short(r.id)} · {human(r.status)} ·{" "}
                  {r.is_stale ? "Changed inputs" : "Current"}
                </option>
              ))}
            </select>
          </label>
        )}

        {!run && (
          <Empty>No investigation has been scheduled for this case.</Empty>
        )}

        {run && (
          <div className="run-meta">
            <Badge kind={run.is_stale ? "warning" : "neutral"}>
              {run.is_stale ? "Historical · inputs changed" : "Current inputs"}
            </Badge>
            <span>{run.tool_calls} read-only tool calls</span>
            <span>Reserved {money(run.reserved_cost_paise)}</span>
            {run.error_code && (
              <Badge kind="warning">{human(run.error_code)}</Badge>
            )}
          </div>
        )}

        {state.loading && <Loading label="Loading persisted graph stages…" />}
        {state.error !== undefined && <ErrorNotice error={state.error} />}

        {!!stages.length && (
          <div className="investigation-spread">
            <nav
              className="stage-nav"
              aria-label="Persisted investigation stages"
            >
              {stages.map((t) => (
                <button
                  key={t.id}
                  data-provenance={
                    t.node === "human_review_or_request_evidence"
                      ? "human"
                      : [
                            "investigator_plan",
                            "investigator_synthesize",
                          ].includes(t.node) && t.metadata.fallback !== true
                        ? "model"
                        : "rules"
                  }
                  aria-current={active?.id === t.id ? "step" : undefined}
                  onClick={() =>
                    setParams((v) => {
                      v.set("step", t.node);
                      return v;
                    })
                  }
                >
                  <span className="stage-dot" aria-hidden="true" />
                  <span>
                    {nodes[t.node]}
                    <small>
                      {[
                        "investigator_plan",
                        "investigator_synthesize",
                      ].includes(t.node)
                        ? t.metadata.fallback === true
                          ? "Safe fallback"
                          : run?.provider === "fake"
                            ? "Demo model"
                            : "AI generated"
                        : "Rules check"}
                    </small>
                  </span>
                </button>
              ))}
            </nav>
            <article
              key={active?.id}
              className="stage-detail"
              aria-live="polite"
            >
              <div className="stage-title">
                <h3>{active && nodes[active.node]}</h3>
                <Provenance kind={origin} />
              </div>

              {meta.fallback === true ? (
                <p>
                  <Badge kind="warning">Deterministic safe fallback</Badge>{" "}
                  {human(meta.rejection)}
                </p>
              ) : (
                <>
                  {meta.cached === true && (
                    <p className="stage-note">
                      Accepted assertion plan reused. Evidence and conclusions
                      are verified again.
                    </p>
                  )}

                  {active?.node === "investigator_plan" && (
                    <>
                      <p className="stage-lead">
                        Test the {text(content.category)} claim for{" "}
                        {money(
                          typeof content.amount_paise === "bigint"
                            ? content.amount_paise
                            : null,
                        )}
                        .
                      </p>
                      <Fields
                        value={{
                          evidence_requested: content.evidence_types,
                          selected_tools: content.tools,
                        }}
                      />
                      <Disclosure title="Support, contradiction & missing-proof tests">
                        <Fields
                          value={{
                            support_test: content.support_test,
                            contradiction_test: content.contradiction_test,
                            unresolved_test: content.unresolved_test,
                          }}
                        />
                      </Disclosure>
                    </>
                  )}

                  {active?.node === "investigator_synthesize" && (
                    <>
                      <Badge
                        kind={
                          content.state === "SUPPORTED"
                            ? "positive"
                            : content.state === "CONFLICTING_EVIDENCE"
                              ? "danger"
                              : "neutral"
                        }
                      >
                        {human(content.state)}
                      </Badge>
                      <p className="stage-lead">{text(content.rationale)}</p>
                      <Fields
                        value={{
                          next_action: content.next_action,
                          missing_evidence: content.missing_evidence_types,
                          uncertainty: content.uncertainty,
                          confidence_in_recommendation: content.confidence,
                        }}
                      />
                      {Array.isArray(content.observations) && (
                        <Disclosure
                          title={`${content.observations.length} source-backed numeric observations`}
                        >
                          <Fields
                            value={{ observations: content.observations }}
                          />
                        </Disclosure>
                      )}
                    </>
                  )}

                  {active?.node === "evidence_verify" && (
                    <>
                      <Badge
                        kind={
                          content.outcome === "SUPPORTED"
                            ? "positive"
                            : content.outcome === "CONTRADICTED"
                              ? "danger"
                              : "neutral"
                        }
                      >
                        {human(content.outcome)}
                      </Badge>
                      <p className="stage-lead">
                        {Array.isArray(content.reasons)
                          ? content.reasons.map(human).join(". ")
                          : "Source facts only."}
                      </p>
                      <Fields
                        value={{
                          purpose: content.purpose,
                          search_complete: content.search_complete,
                          requires_human_review: content.requires_human_review,
                        }}
                      />
                    </>
                  )}

                  {active?.node === "evidence_tool" && (
                    <>
                      <p className="stage-lead">
                        Scoped read-only evidence retrieval.
                      </p>
                      <Fields value={{ selected_tools: meta.tools }} />
                    </>
                  )}

                  {active?.node === "director_route" && (
                    <>
                      <p className="stage-lead">
                        The deterministic Director sets scope, tools and
                        financial boundaries.
                      </p>
                      <Fields
                        value={{
                          provider: meta.provider,
                          financial_authority: meta.financial_authority,
                        }}
                      />
                    </>
                  )}

                  {active?.node === "policy_validate" && (
                    <Fields
                      value={{
                        state: meta.state,
                        fallback: meta.fallback,
                        financial_authority: meta.financial_authority,
                      }}
                    />
                  )}

                  {active?.node === "human_review_or_request_evidence" && (
                    <>
                      <p className="stage-lead">{human(meta.next_action)}</p>
                      <Provenance kind="authority" />
                    </>
                  )}
                </>
              )}

              <Disclosure title="Persisted stage fields & provenance">
                <Fields value={meta} />
                <small>{active && date(active.created_at)}</small>
              </Disclosure>
            </article>
          </div>
        )}

        {runtime.length > 0 && (
          <Disclosure
            title={`${runtime.length} runtime operations · tools, usage & diagnostics`}
          >
            {runtime.map((t) => (
              <Disclosure
                key={t.id}
                title={`${nodes[t.node] || t.node} · ${date(t.created_at)}`}
              >
                <Fields
                  value={{
                    ...record(t.metadata.metadata),
                    usage: t.metadata.usage,
                    diagnostic: t.metadata.diagnostic,
                    error_code: t.metadata.error_code,
                  }}
                />
              </Disclosure>
            ))}
          </Disclosure>
        )}
      </Section>

      {state.data?.findings.map((f, i) => (
        <Section
          key={i}
          title="Verified findings & citations"
          meta={<Provenance kind="check" />}
        >
          <div className="finding-summary">
            <Badge
              kind={
                f.state === "SUPPORTED"
                  ? "positive"
                  : f.unknowns.includes("CONFLICTING_EVIDENCE")
                    ? "danger"
                    : "neutral"
              }
            >
              {human(f.state)}
            </Badge>
            <span>{f.is_current ? "Current" : "Historical finding"}</span>
          </div>
          {f.unknowns.length > 0 && <p>{f.unknowns.map(human).join(" · ")}</p>}
          {f.contradictions.length > 0 && (
            <p className="conflict-text">
              {f.contradictions.map(human).join(" · ")}
            </p>
          )}
          <div className="citation-list">
            {f.citations.map((c) => (
              <button
                key={c.record_id}
                onClick={() =>
                  inspect({
                    document: c.document_id,
                    record: c.record_id,
                    span: {
                      page: c.page,
                      start: c.start,
                      end: c.end,
                      quote: c.excerpt,
                    },
                    expected: {
                      version: c.document_version,
                      raw: c.raw_sha256,
                      canonical: c.canonical_sha256,
                    },
                  })
                }
              >
                <FileText size={15} aria-hidden="true" />
                <span>
                  Inspect source · {evidenceName(c.record_id)}
                  <small>
                    <span className="mono">{short(c.record_id)}</span> · page{" "}
                    {c.page} · characters {c.start}–{c.end}
                  </small>
                </span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
          <Disclosure title="Deterministic predicate results">
            <Fields value={{ findings: f.source_facts }} />
          </Disclosure>
          <p className="boundary">
            Requires human review · no financial authority
          </p>
        </Section>
      ))}
    </>
  );
}
