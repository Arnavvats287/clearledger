import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Link2, RefreshCw } from "lucide-react";
import {
  ApiError,
  Client,
  basis,
  type Customer,
  type Decision,
  type Me,
  type Task,
  type Invoice,
  type Model,
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
  utr,
}: {
  api: Client;
  invoice: string;
  receipt: string;
  utr: string;
}) {
  const load = useCallback(async () => {
    const [bill, payment] = await Promise.all([
      api.request<Invoice>(`/invoices/${invoice}`),
      api.request<Receipt>(`/receipts/${receipt}`),
    ]);
    const [customer, bank] = await Promise.all([
      api.request<Customer>(`/customers/${bill.customer_id}`),
      api.request<Model<"BankView">>(
        `/bank-transactions/${payment.bank_transaction_id}`,
      ),
    ]);
    return { invoice: bill, receipt: payment, customer, bank };
  }, [api, invoice, receipt]);
  const state = useResource(load);
  if (state.error) return <ErrorNotice error={state.error} />;
  if (!state.data) return <p>Loading proposed financial records…</p>;
  const { invoice: bill, receipt: payment, customer, bank } = state.data;
  return (
    <div className="candidate-financials">
      <div>
        <span>Invoice {bill.invoice_number}</span>
        <strong>{money(bill.original_amount_paise)}</strong>
        <small>
          {customer.name} · {money(bill.open_amount_paise)} open
        </small>
      </div>
      <Link2 size={16} aria-hidden="true" />
      <div>
        <span>Bank receipt</span>
        <strong>{money(payment.amount_paise)}</strong>
        {utr && <small className="candidate-reference">UTR {utr}</small>}
        <small>
          {bank.payer_name || "Payer not recorded"} ·{" "}
          {money(payment.unapplied_amount_paise)} unapplied
        </small>
        <small>Received {date(bank.occurred_at)}</small>
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
          {!t.candidates.length && (
            <Empty>
              No source-backed payment candidate is available for this task.
            </Empty>
          )}

          {t.candidates.map((candidate, i) => {
            const c = record(candidate);
            return (
              <div key={i} className="association-proof">
                <span>
                  {t.status === "CONFIRMED"
                    ? "Confirmed association"
                    : t.status === "REJECTED"
                      ? "Rejected candidate"
                      : "Proposed association"}
                </span>
                <CandidateFinancials
                  api={api}
                  invoice={text(c.invoice_id)}
                  receipt={text(c.receipt_id)}
                  utr={text(record(c.utr_span).quote)}
                />
                <small>Association review does not apply cash.</small>
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
              utr={text(record(record(candidate).utr_span).quote)}
            />
          ))}
          <p>
            {decision.kind === "CONFIRM"
              ? "Link the source-backed invoice and receipt for case review."
              : "Reject this association. New evidence will be needed for another review."}
          </p>
        </ConfirmDialog>
      )}
    </Section>
  );
}
