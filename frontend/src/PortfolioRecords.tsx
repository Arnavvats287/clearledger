import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import {
  type Client,
  type PortfolioSnapshot,
  human,
  money,
  portfolioBootstrap,
} from "./api";
import { PortfolioCaseLink } from "./PortfolioCaseLink";
import { Badge, ErrorNotice, useResource } from "./ui";

type Register = "invoices" | "receipts" | "remittances";
const copy = {
  invoices: [
    "Invoices",
    "Issued invoices and open receivables for the synthetic customer ledger.",
  ],
  receipts: [
    "Receipts",
    "Bank references, payer names and cash still awaiting application.",
  ],
  remittances: [
    "Remittances",
    "Seeded source documents and the cases that refer to them.",
  ],
} as const;

function project(kind: Register, snapshot: PortfolioSnapshot) {
  const related = snapshot.cases.map((row) => row.case);
  if (kind === "invoices") {
    const customers = new Map(snapshot.customers.map((r) => [r.id, r.name]));
    return {
      columns: [
        "Invoice",
        "Customer",
        "Issued",
        "Due",
        "Invoiced",
        "Open AR",
        "Status",
      ],
      moneyColumns: [4, 5],
      rows: snapshot.invoices.map((r) => ({
        id: r.id,
        cases: related.filter((c) => c.invoice_ids.includes(r.id)),
        values: [
          r.invoice_number,
          customers.get(r.customer_id) || "—",
          r.issued_date,
          r.due_date,
          money(r.original_amount_paise),
          money(r.open_amount_paise),
          human(r.status),
        ],
      })),
    };
  }
  if (kind === "receipts") {
    const bank = new Map(snapshot.banks.map((r) => [r.id, r]));
    return {
      columns: [
        "Bank reference",
        "Payer",
        "Received",
        "Receipt",
        "Unapplied",
        "Status",
      ],
      moneyColumns: [3, 4],
      rows: snapshot.receipts.map((r) => {
        const entry = bank.get(r.bank_transaction_id);
        return {
          id: r.id,
          cases: related.filter((c) => c.receipt_ids.includes(r.id)),
          values: [
            entry?.external_transaction_id || "—",
            entry?.payer_name || "—",
            entry?.occurred_at_source.slice(0, 10) || "—",
            money(r.amount_paise),
            money(r.unapplied_amount_paise),
            human(r.status),
          ],
        };
      }),
    };
  }
  return {
    columns: ["Source file", "Document type", "Registered", "Parse status"],
    moneyColumns: [],
    rows: snapshot.documents
      .filter(
        (r) =>
          r.document_type === "REMITTANCE" ||
          related.some((c) => c.document_ids.includes(r.id)),
      )
      .map((r) => ({
        id: r.id,
        cases: related.filter((c) => c.document_ids.includes(r.id)),
        values: [
          r.source_name,
          human(r.document_type),
          r.created_at.slice(0, 10),
          human(r.parse_status),
        ],
      })),
  };
}

export function PortfolioRecords({
  api,
  kind,
}: {
  api: Client;
  kind: Register;
}) {
  const [retry, setRetry] = useState(0);
  const load = useCallback(() => {
    void retry;
    return api.request<PortfolioSnapshot>(portfolioBootstrap);
  }, [api, retry]);
  const state = useResource(load, {
    initial: api.peek<PortfolioSnapshot>(portfolioBootstrap),
    retainOnError: true,
  });
  const table = state.data && project(kind, state.data);
  return (
    <main id="main" className="queue-page portfolio-register">
      <header className="case-heading">
        <div>
          <h1 tabIndex={-1}>{copy[kind][0]}</h1>
          <p>{copy[kind][1]}</p>
        </div>
        {kind === "remittances" && (
          <Link to="/intake">Open document sandbox →</Link>
        )}
      </header>
      {state.loading && !table && (
        <p role="status">Loading {copy[kind][0].toLowerCase()}…</p>
      )}
      {state.error !== undefined && (
        <ErrorNotice error={state.error} retry={() => setRetry((n) => n + 1)} />
      )}
      {table && (
        <div
          className="portfolio-table"
          tabIndex={0}
          role="region"
          aria-label={`${copy[kind][0]} register`}
        >
          <table>
            <thead>
              <tr>
                {table.columns.map((column, i) => (
                  <th
                    scope="col"
                    key={column}
                    className={
                      table.moneyColumns.includes(i)
                        ? "portfolio-money"
                        : undefined
                    }
                  >
                    {column}
                  </th>
                ))}
                <th scope="col">Case</th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.values[0]}</th>
                  {row.values.slice(1).map((value, i) => (
                    <td
                      key={i}
                      className={
                        table.moneyColumns.includes(i + 1)
                          ? "portfolio-money"
                          : undefined
                      }
                    >
                      {i + 2 === row.values.length ? (
                        <Badge>{value}</Badge>
                      ) : (
                        value
                      )}
                    </td>
                  ))}
                  <td>
                    {row.cases.length
                      ? row.cases.map((c, i) => (
                          <PortfolioCaseLink
                            key={c.id}
                            api={api}
                            caseId={c.id}
                            to={`/cases/${c.id}`}
                          >
                            {row.cases.length > 1
                              ? `Case ${i + 1}`
                              : "Open case"}
                          </PortfolioCaseLink>
                        ))
                      : "—"}
                  </td>
                </tr>
              ))}
              {table.rows.length === 0 && (
                <tr>
                  <td colSpan={table.columns.length + 1}>
                    No seeded records are available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
