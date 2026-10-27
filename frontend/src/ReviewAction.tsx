import { useState } from "react";
import { ApiError, Client, basis, presentation, type Me } from "./api";
import { ConfirmDialog, Saved } from "./ui";
import { ReviewContext } from "./ReviewContext";
import type { Loaded } from "./workstation";

export function ReviewAction({
  api,
  data,
  me,
  refresh,
}: {
  api: Client;
  data: Loaded;
  me: Me;
  refresh: () => void;
}) {
  const [opened, setOpened] = useState<string>(),
    [comment, setComment] = useState(""),
    [saved, setSaved] = useState(false);
  const state = presentation(data.b),
    draft = state.missing || state.conflict;
  const label = draft ? "Draft evidence request" : "Record review note";
  async function recordReview() {
    if (!opened) return;
    if (!draft && !comment.trim())
      throw new ApiError(422, "REVIEW_NOTE_REQUIRED");
    const current = await api.case(data.b.case.id);
    if (
      current.version !== data.b.case.version ||
      current.context_sha256 !== data.b.case.context_sha256
    )
      throw new ApiError(409, "STALE_CORRELATION_CASE");
    const body = {
      ...basis(current),
      reason: draft
        ? state.conflict
          ? "CONTRADICTORY_EVIDENCE"
          : "MISSING_EVIDENCE"
        : "REVIEW_COMMENT",
      comment,
      ...(draft
        ? {
            invoice_ids: current.invoice_ids,
            claim_ids: data.b.claims.map((c) => c.id),
          }
        : {}),
    };
    await api.request(
      `/cases/${current.id}/${draft ? "draft-evidence-request" : "review-comments"}`,
      "POST",
      body,
      opened,
    );
    setSaved(true);
    refresh();
  }
  return (
    <div className="human-action">
      <button
        className="primary"
        disabled={
          me.role === "AUDITOR" ||
          data.b.case.is_stale ||
          (draft && !data.b.case.invoice_ids.length)
        }
        onClick={() => {
          setComment("");
          setSaved(false);
          setOpened(crypto.randomUUID());
        }}
      >
        {label}
      </button>
      {saved && (
        <Saved>
          {draft
            ? "Evidence request saved as a draft. Nothing was sent."
            : "Review note recorded in the immutable case history."}
        </Saved>
      )}
      {opened && (
        <ConfirmDialog
          title={label}
          action={draft ? "Save draft only" : "Record review note"}
          close={() => setOpened(undefined)}
          confirm={recordReview}
        >
          <ReviewContext data={data} />
          <p>
            {draft
              ? "Prepare a source-linked request for the missing or conflicting evidence. This is a draft only; no customer message is sent."
              : "Record your review of the sources. A note cannot approve a deduction, settle a balance or grant financial authority."}
          </p>
          <label className="review-note">
            Review note{draft ? " (optional)" : ""}
            <textarea
              name="review-note"
              maxLength={2000}
              rows={4}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              autoComplete="off"
            />
          </label>
          <p>
            Bound to the current case version and cited invoice/claim
            relationships.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
