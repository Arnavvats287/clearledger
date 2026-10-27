import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, FileText, RefreshCw } from "lucide-react";
import {
  ApiError,
  Client,
  basis,
  type Decision,
  type Me,
  type Task,
  type Invoice,
  type Receipt,
  date,
  human,
  money,
  record,
  text,
} from "./api";
import {
  Badge,
  ConfirmDialog,
  Disclosure,
  Empty,
  ErrorNotice,
  Fields,
  Provenance,
  Saved,
  Section,
  useResource,
} from "./ui";
import { ReviewContext } from "./ReviewContext";
import type { Loaded } from "./workstation";
import type { Selection } from "./Documents";

function CandidateFinancials({
  api,
  invoice,
  receipt,
}: {
  api: Client;
  invoice: string;
  receipt: string;
}) {
  const load = useCallback(
    async () => ({
      invoice: await api.request<Invoice>(`/invoices/${invoice}`),
      receipt: await api.request<Receipt>(`/receipts/${receipt}`),
    }),
    [api, invoice, receipt],
  );
  const state = useResource(load);
  if (state.error) return <ErrorNotice error={state.error} />;
  if (!state.data) return <p>Loading proposed financial records…</p>;
  return (
    <div className="candidate-financials">
      <div>
        <span>Invoice {state.data.invoice.invoice_number}</span>
        <strong>{money(state.data.invoice.open_amount_paise)}</strong>
        <small>Outstanding AR</small>
      </div>
      <ArrowLeft size={16} aria-hidden="true" />
      <div>
        <span>Bank receipt</span>
        <strong>{money(state.data.receipt.unapplied_amount_paise)}</strong>
        <small>Unapplied cash</small>
      </div>
    </div>
  );
}

export function Correlation({
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
  const { b } = data,
    navigate = useNavigate();

  const [decision, setDecision] = useState<{
      task: Task;
      kind: "CONFIRM" | "REJECT";
      key: string;
    }>(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState("");

  const historyLoad = useCallback(
    async () =>
      (
        await Promise.all(
          b.tasks.map((t) =>
            api.list<Decision>(`/review/correlation-tasks/${t.id}/decisions`),
          ),
        )
      ).flat(),
    [api, b.tasks],
  );

  const history = useResource(historyLoad);

  async function update() {
    setBusy(true);
    setError(undefined);
    try {
      await api.request(
        `/review/cases/${b.case.id}/correlation-tasks/refresh`,
        "POST",
        {},
      );
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function recordDecision() {
    if (!decision) return;

    // Re-read current server inputs, but never silently change the reviewed decision basis.

    const current = await api.case(b.case.id);

    if (
      current.version !== b.case.version ||
      current.context_sha256 !== b.case.context_sha256
    )
      throw new ApiError(409, "STALE_CORRELATION_CASE");

    await api.request(
      `/review/correlation-tasks/${decision.task.id}/decision`,
      "POST",
      {
        ...basis(current),
        expected_task_sha256: decision.task.input_sha256,
        decision: decision.kind,
      },
      decision.key,
    );

    setSaved(
      `${decision.kind === "CONFIRM" ? "Association confirmed" : "Association rejected"}. The immutable decision was recorded.`,
    );

    const canonical = await api.case(b.case.id);

    if (canonical.id !== b.case.id)
      navigate(`/cases/${canonical.id}?tab=correlation`, { replace: true });

    refresh();
  }

  return (
    <Section
      title="Match payment to invoice"
      meta={
        <button
          onClick={() => void update()}
          disabled={busy || me.role === "AUDITOR"}
        >
          <RefreshCw size={14} aria-hidden="true" />
          Refresh proof
        </button>
      }
    >
      <p>
        A remittance statement is not verified payment intent. Independent
        source proof and a deliberate controller decision are required.
      </p>
      {b.accessError && <ErrorNotice error={b.accessError} />}{" "}
      {error !== undefined && <ErrorNotice error={error} />}
      {saved && <Saved>{saved}</Saved>}
      {!b.tasks.length && !b.accessError && (
        <Empty>No correlation task is currently available.</Empty>
      )}
      {b.tasks.map((t) => (
        <article className="task" key={t.id}>
          <div className="task-title">
            <Badge
              kind={
                t.reason === "READY_FOR_REVIEW" && !t.is_stale
                  ? "positive"
                  : "neutral"
              }
            >
              {human(t.is_stale ? "STALE" : t.status)}
            </Badge>
            <h3>
              {t.status === "CONFIRMED"
                ? "Payment association confirmed"
                : t.status === "REJECTED"
                  ? "Payment association rejected"
                  : t.reason === "READY_FOR_REVIEW"
                    ? "Independent proof ready for review"
                    : human(t.reason)}
            </h3>
          </div>
          <p>
            {t.next_action === "REVIEW_CORRELATION"
              ? "Review the source-backed association before confirming."
              : human(t.next_action)}
          </p>

          {t.candidates.map((candidate, i) => {
            const c = record(candidate);
            return (
              <div key={i} className="association-proof">
                <span>Proposed association</span>
                <CandidateFinancials
                  api={api}
                  invoice={text(c.invoice_id)}
                  receipt={text(c.receipt_id)}
                />
                <small>
                  These are server-provided candidates, not a financial
                  allocation.
                </small>
                <div className="span-actions">
                  {Array.isArray(c.evidence_ids) &&
                    c.evidence_ids.map((id) => (
                      <button
                        key={String(id)}
                        onClick={() =>
                          inspect({
                            document: t.document_id,
                            record: String(id),
                            proofTask: { id: t.id, hash: t.input_sha256 },
                          })
                        }
                      >
                        <FileText size={14} aria-hidden="true" />
                        Inspect independent payment proof
                      </button>
                    ))}
                </div>
              </div>
            );
          })}

          {t.status === "PENDING" && (
            <div className="review-controls">
              <button
                className="primary"
                disabled={
                  me.role !== "CONTROLLER" ||
                  t.is_stale ||
                  b.case.is_stale ||
                  t.reason !== "READY_FOR_REVIEW"
                }
                onClick={() =>
                  setDecision({
                    task: t,
                    kind: "CONFIRM",
                    key: crypto.randomUUID(),
                  })
                }
              >
                Review & confirm association
              </button>
              <button
                disabled={
                  me.role !== "CONTROLLER" || t.is_stale || b.case.is_stale
                }
                onClick={() =>
                  setDecision({
                    task: t,
                    kind: "REJECT",
                    key: crypto.randomUUID(),
                  })
                }
              >
                Review & reject
              </button>
              <small>
                {me.role !== "CONTROLLER"
                  ? "Controller access required."
                  : t.is_stale || b.case.is_stale
                    ? "Changed inputs must be refreshed."
                    : t.reason !== "READY_FOR_REVIEW"
                      ? "Confirmation unavailable until independent proof is complete."
                      : "Confirmation links case evidence; it does not apply cash."}
              </small>
            </div>
          )}

          <Disclosure title="Review basis & provenance">
            <Fields
              value={{
                task_id: t.id,
                source_snapshot: t.input_sha256,
                current: !t.is_stale,
                created_at: t.created_at,
              }}
            />
          </Disclosure>
        </article>
      ))}
      <h3 className="subheading">Decision history</h3>
      {history.error !== undefined && <ErrorNotice error={history.error} />}
      {history.data?.length === 0 && <Empty>No decisions recorded.</Empty>}
      {history.data?.map((d) => (
        <div className="decision-history" key={d.id}>
          <Provenance kind="human" />
          <strong>{human(d.decision)}</strong>
          <span>{date(d.created_at)}</span>
          <small>
            {text(d.actor.authority) === "LOCAL_DEMO_ONLY"
              ? "Local synthetic reviewer · no financial authority"
              : "Verified review identity · financial authority remains separate"}
          </small>
        </div>
      ))}
      {decision && (
        <ConfirmDialog
          title={
            decision.kind === "CONFIRM"
              ? "Confirm this evidence association?"
              : "Reject this proposed association?"
          }
          action={
            decision.kind === "CONFIRM"
              ? "Confirm association"
              : "Record rejection"
          }
          close={() => setDecision(undefined)}
          confirm={recordDecision}
        >
          <ReviewContext
            data={data}
            proof={{
              ready:
                decision.task.reason === "READY_FOR_REVIEW" &&
                !decision.task.is_stale,
              records: new Set(
                decision.task.candidates.flatMap((c) => {
                  const ids = record(c).evidence_ids;
                  return Array.isArray(ids) ? ids.map(String) : [];
                }),
              ).size,
            }}
          />
          {decision.task.candidates.slice(0, 1).map((candidate, i) => (
            <CandidateFinancials
              key={i}
              api={api}
              invoice={text(record(candidate).invoice_id)}
              receipt={text(record(candidate).receipt_id)}
            />
          ))}
          <p>
            {decision.kind === "CONFIRM"
              ? "Link the source-backed invoice/receipt association. No balance changes, settlement or posting will occur."
              : "Reject this association. New evidence will be needed for another review."}
          </p>
        </ConfirmDialog>
      )}
    </Section>
  );
}
