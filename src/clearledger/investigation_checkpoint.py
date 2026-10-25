"""JSON-only LangGraph persistence, fenced by the owning outbox lease."""

import json

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.case_repository import scoped
from clearledger.investigation_models import InvestigationCheckpoint, InvestigationWrite
from clearledger.matching import digest


def safe_json(value):
    encoded = json.dumps(value, allow_nan=False, ensure_ascii=True)
    if len(encoded) > 512000:
        raise CaseError("CHECKPOINT_LIMIT")
    return json.loads(encoded)


class PostgresSaver(BaseCheckpointSaver):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.thread = f"{runtime.org}/{runtime.case_id}/{runtime.run_id}"

    def config(self, identifier=None):
        return {
            "configurable": {
                "thread_id": self.thread,
                "checkpoint_ns": "",
                **({"checkpoint_id": identifier} if identifier else {}),
            }
        }

    def check_scope(self, config):
        values = config.get("configurable", {})
        if values.get("thread_id") != self.thread or values.get("checkpoint_ns", "") != "":
            raise CaseError("CHECKPOINT_SCOPE", 403)

    def get_tuple(self, config):
        self.check_scope(config)
        with Session(self.runtime.engine) as session:
            statement = select(InvestigationCheckpoint).where(
                InvestigationCheckpoint.organization_id == self.runtime.org,
                InvestigationCheckpoint.run_id == self.runtime.run_id,
            )
            identifier = config["configurable"].get("checkpoint_id")
            if identifier:
                statement = statement.where(InvestigationCheckpoint.checkpoint_id == identifier)
            row = session.scalar(
                statement.order_by(InvestigationCheckpoint.checkpoint_id.desc()).limit(1)
            )
            if row is None:
                return None
            if digest({"checkpoint": row.checkpoint, "metadata": row.meta}) != row.content_sha256:
                raise CaseError("CHECKPOINT_INTEGRITY")
            writes = list(
                session.scalars(
                    select(InvestigationWrite)
                    .where(
                        InvestigationWrite.organization_id == self.runtime.org,
                        InvestigationWrite.run_id == self.runtime.run_id,
                        InvestigationWrite.checkpoint_id == row.checkpoint_id,
                    )
                    .order_by(
                        InvestigationWrite.task_path,
                        InvestigationWrite.task_id,
                        InvestigationWrite.write_index,
                    )
                )
            )
            return CheckpointTuple(
                self.config(row.checkpoint_id),
                row.checkpoint,
                row.meta,
                self.config(row.parent_id) if row.parent_id else None,
                [(w.task_id, w.channel, w.value["value"]) for w in writes],
            )

    def put(self, config, checkpoint, metadata, new_versions):
        self.check_scope(config)
        value, meta = safe_json(checkpoint), safe_json(metadata)
        checksum = digest({"checkpoint": value, "metadata": meta})
        with self.runtime.transaction() as (session, run, row):
            previous = scoped(
                session,
                InvestigationCheckpoint,
                self.runtime.org,
                run_id=run.id,
                checkpoint_id=checkpoint["id"],
            )
            if previous and previous.content_sha256 != checksum:
                raise CaseError("CHECKPOINT_CONFLICT")
            if previous is None:
                session.add(
                    InvestigationCheckpoint(
                        organization_id=self.runtime.org,
                        run_id=run.id,
                        checkpoint_id=checkpoint["id"],
                        parent_id=config["configurable"].get("checkpoint_id"),
                        checkpoint=value,
                        meta=meta,
                        content_sha256=checksum,
                    )
                )
        return self.config(checkpoint["id"])

    def put_writes(self, config, writes, task_id, task_path=""):
        self.check_scope(config)
        with self.runtime.transaction() as (session, run, row):
            for index, (channel, value) in enumerate(writes):
                # Node errors are converted to safe states before reaching LangGraph.
                wrapped = safe_json({"value": value})
                previous = scoped(
                    session,
                    InvestigationWrite,
                    self.runtime.org,
                    run_id=run.id,
                    checkpoint_id=config["configurable"]["checkpoint_id"],
                    task_id=task_id,
                    write_index=index,
                )
                if previous and (previous.channel != channel or previous.value != wrapped):
                    raise CaseError("CHECKPOINT_WRITE_CONFLICT")
                if previous is None:
                    session.add(
                        InvestigationWrite(
                            organization_id=self.runtime.org,
                            run_id=run.id,
                            checkpoint_id=config["configurable"]["checkpoint_id"],
                            task_id=task_id,
                            task_path=task_path,
                            write_index=index,
                            channel=channel,
                            value=wrapped,
                        )
                    )
