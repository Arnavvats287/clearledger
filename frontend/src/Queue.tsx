import { useCallback, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight, RefreshCw, Search } from "lucide-react";
import {
  Client,
  bundle,
  references,
  type Bundle,
  type Case,
  type Customer,
  type Invoice,
  type Receipt,
  date,
  human,
  money,
  presentation,
  record,
  text,
} from "./api";
import { assessment, financialStory } from "./story";
import { Badge, Empty, ErrorNotice, Loading, useResource } from "./ui";

function proposedInvoices(b: Bundle, invoices: Invoice[]) {
  const ids = new Set(
    b.tasks.flatMap((t) => t.candidates.map((c) => text(record(c).invoice_id))),
  );
  return invoices
    .filter((i) => ids.has(i.id))
    .map((i) => i.invoice_number)
    .join(", ");
}
const filters = [
  "All exceptions",
  "Needs evidence",
  "Payment match",
  "Human review",
  "Conflict",
  "Supported",
  "Stale",
];
export function Queue({ api }: { api: Client }) {
  const [params, setParams] = useSearchParams(),
    [revision, setRevision] = useState(0);
  const page = Math.max(0, Number(params.get("page")) || 0),
    filter = params.get("filter") || filters[0],
    query = params.get("q") || "";
  const load = useCallback(async () => {
    void revision;
    const cases = await api.list<Case>(`/cases?limit=20&offset=${page * 20}`);
    // Bounded groups avoid unbounded per-case request fanout.
    const bundles: Bundle[] = [];
    for (let i = 0; i < cases.length; i += 3)
      bundles.push(
        ...(await Promise.all(
          cases.slice(i, i + 3).map((c) => bundle(api, c)),
        )),
      );
    const [customers, invoices, receipts] = await Promise.all([
      references<Customer>(
        api,
        "/customers",
        cases.flatMap((c) => (c.customer_id ? [c.customer_id] : [])),
      ),
      references<Invoice>(api, "/invoices", [
        ...cases.flatMap((c) => c.invoice_ids),
        ...bundles
          .flatMap((b) =>
            b.tasks.flatMap((t) =>
              t.candidates.map((c) => text(record(c).invoice_id)),
            ),
          )
          .filter(Boolean),
      ]),
      references<Receipt>(
        api,
        "/receipts",
        cases.flatMap((c) => c.receipt_ids),
      ),
    ]);
    return { cases: bundles, customers, invoices, receipts };
  }, [api, page, revision]); // revision intentionally refreshes the server snapshot
  const state = useResource(load);
  function change(k: string, v: string) {
    setParams((p) => {
      p.set(k, v);
      if (k !== "page") p.delete("page");
      return p;
    });
  }
  const rows =
    state.data?.cases.filter((b) => {
      const p = presentation(b),
        name =
          state.data?.customers.find((x) => x.id === b.case.customer_id)
            ?.name || "Unassigned customer";
      const match =
        filter === filters[0] ||
        (filter === "Needs evidence" && p.missing) ||
        (filter === "Payment match" &&
          b.tasks.some((t) => t.status === "PENDING")) ||
        (filter === "Human review" && b.case.state === "AWAITING_REVIEW") ||
        (filter === "Conflict" && p.conflict) ||
        (filter === "Supported" && p.supported) ||
        (filter === "Stale" && p.stale);
      return (
        match &&
        `${name} ${proposedInvoices(b, state.data!.invoices)} ${b.case.id} ${b.case.invoice_ids.map((id) => state.data?.invoices.find((i) => i.id === id)?.invoice_number).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase())
      );
    }) || [];
  return (
    <main id="main" className="queue-page">
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>Exception register</h1>
          <p>
            Investigate short payments and review proposed payment associations.
          </p>
        </div>
        <button
          onClick={() => setRevision((v) => v + 1)}
          disabled={state.loading}
        >
          <RefreshCw size={15} aria-hidden="true" />
          Refresh queue
        </button>
      </div>
      <div className="queue-toolbar">
        <div className="filters" aria-label="Operational filters">
          {filters.map((f) => (
            <button
              key={f}
              aria-pressed={filter === f}
              className={filter === f ? "selected" : ""}
              onClick={() => change("filter", f)}
            >
              {f}
            </button>
          ))}
        </div>
        <label className="search">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search loaded cases</span>
          <input
            value={query}
            name="case-search"
            autoComplete="off"
            placeholder="Customer, invoice or case…"
            onChange={(e) => change("q", e.target.value)}
          />
        </label>
      </div>
      {state.loading && <Loading />}
      {state.error !== undefined && (
        <ErrorNotice
          error={state.error}
          retry={() => setRevision((v) => v + 1)}
        />
      )}
      {state.data && (
        <>
          <div className="register-caption" role="status">
            <span>
              {rows.length} shown · {state.data.cases.length} cases on this page
            </span>
            <span>INR · comparison amounts</span>
          </div>
          <div
            className="register-scroll"
            role="region"
            aria-label="Exception table"
            tabIndex={0}
          >
            <table className="register story-register">
              <caption className="sr-only">
                Short payments, customer explanations, evidence and next actions
              </caption>
              <thead>
                <tr>
                  <th scope="col">Customer / invoice</th>
                  <th scope="col" className="queue-amount">
                    Invoiced
                  </th>
                  <th scope="col" className="queue-amount">
                    Received
                  </th>
                  <th scope="col" className="num">
                    Short payment
                  </th>
                  <th scope="col">Evidence / exception</th>
                  <th scope="col">Next action / case status</th>
                </tr>
              </thead>
              <tbody key={`${filter}:${query}:${page}`}>
                {rows.map((b) => {
                  const c = b.case,
                    a = assessment(b),
                    invoices = state.data!.invoices.filter((i) =>
                      c.invoice_ids.includes(i.id),
                    ),
                    receipts = state.data!.receipts.filter((r) =>
                      c.receipt_ids.includes(r.id),
                    ),
                    f = financialStory(invoices, receipts);
                  return (
                    <tr
                      key={c.id}
                      data-state={
                        a.stale
                          ? "stale"
                          : a.conflict
                            ? "conflict"
                            : a.supported
                              ? "supported"
                              : a.pending
                                ? "review"
                                : "missing"
                      }
                    >
                      <td>
                        <Link className="case-link" to={`/cases/${c.id}`}>
                          {state.data!.customers.find(
                            (x) => x.id === c.customer_id,
                          )?.name || "Customer not verified"}
                          <ArrowUpRight size={15} aria-hidden="true" />
                        </Link>
                        <small>
                          {invoices.map((i) => i.invoice_number).join(", ") ||
                            (proposedInvoices(b, state.data!.invoices)
                              ? `Proposed: ${proposedInvoices(b, state.data!.invoices)}`
                              : "Invoice association pending")}
                        </small>
                        <small>Opened {date(c.created_at)}</small>
                      </td>
                      <td className="queue-amount" data-label="Invoiced">
                        {money(f.invoiced)}
                      </td>
                      <td className="queue-amount" data-label="Received">
                        {money(f.received)}
                      </td>
                      <td className="num">
                        <strong>{money(f.difference)}</strong>
                        <small>
                          {b.claims.length
                            ? `${money(c.claimed_total_paise)} ${b.claims.map((q) => human(q.category).toLowerCase()).join(", ")} claim`
                            : "No claim linked yet"}
                        </small>
                      </td>
                      <td>
                        <Badge
                          kind={
                            a.conflict
                              ? "danger"
                              : a.supported
                                ? "positive"
                                : "neutral"
                          }
                        >
                          {a.title}
                        </Badge>
                        <small>
                          {b.runs[0]?.provider === "fake"
                            ? "Demo scenario"
                            : b.runs.length
                              ? "Evidence assessment available"
                              : "Awaiting investigation"}
                        </small>
                        {b.accessError && (
                          <small>Review access unavailable</small>
                        )}
                      </td>
                      <td>
                        <Link
                          className="action-link"
                          to={`/cases/${c.id}${a.pending ? "?tab=correlation" : ""}`}
                        >
                          {a.action}
                          <ArrowDownRight size={15} aria-hidden="true" />
                        </Link>
                        <small>{human(c.state)}</small>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!rows.length && (
            <Empty>
              {state.data.cases.length
                ? "No loaded cases match this view. Clear the filters to return to the register."
                : "No cases yet. Import financial records or a remittance to begin."}
            </Empty>
          )}
          <div className="paging">
            <span>Page {page + 1} · filters apply to this loaded page</span>
            <div>
              <button
                onClick={() => change("page", String(page - 1))}
                disabled={page === 0}
              >
                Previous page
              </button>
              <button
                onClick={() => change("page", String(page + 1))}
                disabled={state.data.cases.length < 20}
              >
                Next page
              </button>
            </div>
          </div>
        </>
      )}
      <div className="queue-footnote">
        <span>
          Amounts are comparisons, not allocations. Evidence support never posts
          a deduction.
        </span>
        <Link to="/intake">
          Import invoices or receipts <ArrowUpRight size={15} />
        </Link>
      </div>
    </main>
  );
}
