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
  short,
} from "./api";
import { Badge, Empty, ErrorNotice, Loading, useResource } from "./ui";

const filters = [
  "All exceptions",
  "Needs evidence",
  "Correlation review",
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
    const [customers, invoices, receipts] = await Promise.all([
      references<Customer>(
        api,
        "/customers",
        cases.flatMap((c) => (c.customer_id ? [c.customer_id] : [])),
      ),
      references<Invoice>(
        api,
        "/invoices",
        cases.flatMap((c) => c.invoice_ids),
      ),
      references<Receipt>(
        api,
        "/receipts",
        cases.flatMap((c) => c.receipt_ids),
      ),
    ]);
    // Bounded groups avoid unbounded per-case request fanout.
    const bundles: Bundle[] = [];
    for (let i = 0; i < cases.length; i += 3)
      bundles.push(
        ...(await Promise.all(
          cases.slice(i, i + 3).map((c) => bundle(api, c)),
        )),
      );
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
        (filter === "Correlation review" &&
          b.tasks.some((t) => t.status === "PENDING")) ||
        (filter === "Human review" && b.case.state === "AWAITING_REVIEW") ||
        (filter === "Conflict" && p.conflict) ||
        (filter === "Supported" && p.supported) ||
        (filter === "Stale" && p.stale);
      return (
        match &&
        `${name} ${b.case.id} ${b.case.invoice_ids.map((id) => state.data?.invoices.find((i) => i.id === id)?.invoice_number).join(" ")}`
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
            Review the claim. Inspect the proof. Keep the balance traceable.
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
          <div className="register-caption">
            <span>
              {rows.length} shown · {state.data.cases.length} cases on this page
            </span>
            <span>All values INR · no automatic settlement</span>
          </div>
          <div className="register-scroll">
            <table className="register">
              <caption className="sr-only">
                Exception cases and current financial records
              </caption>
              <thead>
                <tr>
                  <th scope="col">Case / customer</th>
                  <th scope="col" className="num">
                    Open invoice AR
                  </th>
                  <th scope="col" className="num">
                    Unapplied cash
                  </th>
                  <th scope="col" className="num">
                    Claim asserted
                  </th>
                  <th scope="col">Evidence / investigation</th>
                  <th scope="col">Required next action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((b) => {
                  const p = presentation(b),
                    c = b.case,
                    invoices = state.data!.invoices.filter((i) =>
                      c.invoice_ids.includes(i.id),
                    ),
                    receipts = state.data!.receipts.filter((r) =>
                      c.receipt_ids.includes(r.id),
                    );
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/cases/${c.id}`} className="case-link">
                          {state.data!.customers.find(
                            (x) => x.id === c.customer_id,
                          )?.name || "Unassigned customer"}
                          <ArrowUpRight size={16} aria-hidden="true" />
                        </Link>
                        <small>
                          {invoices.map((i) => i.invoice_number).join(", ") ||
                            "Invoice not associated"}{" "}
                          · <span className="mono">{short(c.id)}</span>
                        </small>
                        <small>Opened {date(c.created_at)}</small>
                      </td>
                      <td className="num">
                        {money(
                          invoices.length
                            ? invoices.reduce(
                                (n, i) => n + i.open_amount_paise,
                                0n,
                              )
                            : null,
                        )}
                      </td>
                      <td className="num">
                        {money(
                          receipts.length
                            ? receipts.reduce(
                                (n, r) => n + r.unapplied_amount_paise,
                                0n,
                              )
                            : null,
                        )}
                      </td>
                      <td className="num claim-money">
                        {money(c.claimed_total_paise)}
                        {c.unknown_amount_count > 0 && (
                          <small>{c.unknown_amount_count} unknown amount</small>
                        )}
                      </td>
                      <td>
                        <Badge
                          kind={
                            p.conflict
                              ? "danger"
                              : p.supported
                                ? "positive"
                                : "neutral"
                          }
                        >
                          {human(p.state)}
                        </Badge>
                        <small>
                          {b.runs[0]
                            ? `${b.runs[0].provider === "fake" ? "Offline control" : human(b.runs[0].provider)} · ${human(b.runs[0].status)}${p.stale ? " · changed inputs" : ""}`
                            : "No investigation yet"}
                        </small>
                        {b.accessError && (
                          <small>Correlation access unavailable</small>
                        )}
                      </td>
                      <td>
                        <Link
                          to={`/cases/${c.id}?tab=${b.tasks.some((t) => t.status === "PENDING") ? "correlation" : "investigation"}`}
                          className="action-link"
                        >
                          {human(p.action)}
                          <ArrowDownRight size={16} aria-hidden="true" />
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
      <aside className="queue-note">
        <span className="ledger-mark" aria-hidden="true">
          ↳
        </span>
        <div>
          <h2>Supported is not settled.</h2>
          <p>
            Evidence may support a deduction. Human review and financial
            authority remain separate.
          </p>
        </div>
        <Link to="/intake">
          Import & documents <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </aside>
    </main>
  );
}
