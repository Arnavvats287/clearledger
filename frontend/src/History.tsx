import { useCallback } from "react";
import { Client, type Model, date, human } from "./api";
import {
  Disclosure,
  ErrorNotice,
  Fields,
  Loading,
  Provenance,
  Section,
  useResource,
} from "./ui";
import type { Loaded } from "./workstation";

export function History({ api, data }: { api: Client; data: Loaded }) {
  const load = useCallback(
    async () =>
      Promise.all([
        api.list<Model<"HistoryView">>(`/cases/${data.b.case.id}/events`),
        api.list<Model<"ReevaluationView">>(
          `/cases/${data.b.case.id}/reevaluations`,
        ),
        api.list<Model<"ActionView">>(
          `/cases/${data.b.case.id}/review-actions`,
        ),
      ]),
    [api, data.b.case.id],
  );

  const state = useResource(load);

  if (state.loading) return <Loading label="Loading immutable case history…" />;

  if (state.error) return <ErrorNotice error={state.error} />;

  return (
    <Section
      title="Case history"
      meta={<Provenance kind="check">Append-only history</Provenance>}
    >
      {state.data?.[2].map((a) => (
        <article className="review-history" key={a.id}>
          <Provenance kind="human" />
          <strong>{human(a.kind)}</strong>
          <small>
            {date(a.created_at)} ·{" "}
            {a.is_stale ? "Historical basis" : "Current basis"}
          </small>
          <Disclosure title="Recorded review content">
            <Fields value={a.content} />
          </Disclosure>
        </article>
      ))}
      <ol className="history-list">
        {state.data?.[0].map((e) => (
          <li key={e.id}>
            <span className="history-dot" aria-hidden="true" />
            <div>
              <strong>{human(e.event_type?.replaceAll(".", " "))}</strong>
              <small>
                {date(e.created_at)} ·{" "}
                {e.case_version ? `Case v${e.case_version}` : "Source event"}
              </small>
              <Disclosure title="Event provenance">
                <Fields
                  value={{ event: e.id, actor: e.actor_id, payload: e.payload }}
                />
              </Disclosure>
            </div>
          </li>
        ))}
      </ol>
      <h3>Reevaluations</h3>
      {state.data?.[1].map((e) => (
        <Disclosure
          key={e.id}
          title={`${date(e.created_at)} · evaluated case v${e.evaluated_version}`}
        >
          <Fields value={e.result} />
        </Disclosure>
      ))}
    </Section>
  );
}
