"""Protocol 1: current bytes only, strict binding and cumulative immutable deltas."""

import base64
import csv
import io
import json
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID
from zoneinfo import ZoneInfo

from application_eval_inputs import GROUPS, IMPORTS, MIMES, sha

from clearledger.data_contract import INPUTS, timestamp
from clearledger.imports import ImportFailure, parse_csv

MAX_WIRE = 96 * 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def allowed(name):
    if not isinstance(name, str) or len(name) > 240:
        return False
    p = PurePosixPath(name)
    if (
        p.as_posix() != name
        or p.is_absolute()
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
        or any(c in name for c in ("\\", ":", "\x00"))
        or any(part in ("..", ".") or part.startswith(".") for part in p.parts)
    ):
        return False
    return name in {f"imports/{k}.csv" for k in IMPORTS} or (
        p.suffix.lower() in MIMES
        and (
            (
                len(p.parts) == 3
                and p.parts[:2] == ("app_visible", "correlation_sources")
                and p.suffix == ".json"
            )
            or (
                len(p.parts) == 4
                and p.parts[:2] == ("app_visible", "evidence_corpus")
                and p.parts[2] in GROUPS
            )
        )
    )


class Stage:
    def __init__(self, message):
        if not isinstance(message, dict) or set(message) != {
            "request",
            "manifest",
            "files",
            "company",
            "run_id",
            "nonce",
            "payload",
        }:
            raise ValueError("MESSAGE_FIELDS")
        request = message["request"]
        if not isinstance(request, dict) or set(request) != {
            "split",
            "transaction",
            "as_of",
            "request_id",
            "snapshot_id",
        }:
            raise ValueError("REQUEST_FIELDS")
        if request["split"] != "dev":
            raise ValueError("DEVELOPMENT_SPLIT_ONLY")
        for value in (message["run_id"], request["request_id"], request["snapshot_id"]):
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError("CANONICAL_UUID_REQUIRED")
        for field in ("company", "nonce"):
            value = message[field]
            if (
                not isinstance(value, str)
                or not 1 <= len(value) <= 200
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
            ):
                raise ValueError("SCOPE_OR_NONCE")
        key = request["transaction"]
        if (
            not isinstance(key, dict)
            or set(key) != {"source_system", "account_ref", "external_transaction_id"}
            or any(
                not isinstance(v, str)
                or not 1 <= len(v) <= 100
                or v != v.strip()
                or any(ord(c) < 32 for c in v)
                for v in key.values()
            )
        ):
            raise ValueError("NATURAL_KEY")
        self.cutoff = timestamp(request["as_of"])
        if self.cutoff > datetime.now(UTC):
            raise ValueError("FUTURE_REPLAY_CLOCK_UNSUPPORTED")
        manifest, payload = message["manifest"], message["payload"]
        if (
            not isinstance(manifest, dict)
            or not isinstance(payload, dict)
            or (set(manifest) != set(payload) or len(manifest) > 10000)
        ):
            raise ValueError("MANIFEST_PAYLOAD")
        if (
            not isinstance(message["files"], list)
            or len(set(message["files"])) != len(message["files"])
            or any(n not in manifest for n in message["files"])
        ):
            raise ValueError("CHANGED_FILES")
        self.bytes = {}
        for name, digest in manifest.items():
            if (
                not allowed(name)
                or not isinstance(digest, str)
                or not re.fullmatch("[0-9a-f]{64}", digest)
            ):
                raise ValueError("INPUT_ALLOWLIST_OR_HASH")
            encoded = payload[name]
            if not isinstance(encoded, str) or len(encoded) > 2796204:
                raise ValueError("INPUT_SIZE")
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 2 * 1024 * 1024 or sha(raw) != digest:
                raise ValueError("INPUT_HASH_OR_SIZE")
            self.bytes[name] = raw
        if sum(map(len, self.bytes.values())) > 64 * 1024 * 1024:
            raise ValueError("TOTAL_INPUT_SIZE")
        self.message, self.request, self.manifest = message, request, manifest
        self.digest = sha(
            canonical({k: v for k, v in message.items() if k not in {"payload", "files", "nonce"}})
        )

    def envelope(self):
        return {
            **{k: self.message[k] for k in ("company", "run_id", "nonce")},
            **{k: self.request[k] for k in ("request_id", "snapshot_id")},
            "input_manifest_sha256": sha(canonical(self.manifest)),
            "prediction": {"receipt": self.request["transaction"], "as_of": self.request["as_of"]},
            "mode": "REAL_API",
            "elapsed_ns": 0,
            "status": "ERROR",
            "financial_mutation_check": "NOT_EVALUABLE",
        }


def natural(kind, row):
    if kind == "customers":
        return (row["external_reference"],)
    if kind == "payer-aliases":
        return (" ".join(row["alias"].split()).casefold(),)
    if kind == "invoices":
        return (row["invoice_number"],)
    return tuple(row[k] for k in ("source_system", "account_ref", "external_transaction_id"))


class Deltas:
    def __init__(self):
        self.accepted = {kind: {} for kind in IMPORTS}
        self.documents = {}

    def plan(self, stage):
        planned, accepted = {}, {}
        for kind in IMPORTS:
            name = f"imports/{kind}.csv"
            if name not in stage.bytes:
                if self.accepted[kind]:
                    raise ValueError("REMOVED_IMPORT")
                continue
            raw = stage.bytes[name]
            try:
                parse_csv(kind, raw)  # Existing strict schema, paise and row limits.
            except ImportFailure as exc:
                if exc.code != "EMPTY_IMPORT":
                    raise ValueError("INVALID_CONTRACT_CSV") from None
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
            present, new = {}, []
            for row in reader:
                key, digest = natural(kind, row), sha(canonical(row))
                if key in present and present[key] != digest:
                    raise ValueError("CONFLICTING_SNAPSHOT_ROWS")
                if key in self.accepted[kind] and self.accepted[kind][key] != digest:
                    raise ValueError("CHANGED_NATURAL_PAYLOAD")
                field = {
                    "invoices": "issued_date",
                    "payer-aliases": "verified_at",
                    "bank-transactions": "occurred_at",
                }.get(kind)
                future = False
                if field:
                    future = (
                        row[field]
                        > stage.cutoff.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
                        if kind == "invoices"
                        else timestamp(row[field]) > stage.cutoff
                    )
                if future:
                    raise ValueError("FUTURE_SOURCE_ROW")
                if key not in present and key not in self.accepted[kind]:
                    new.append(row)
                present[key] = digest
            if not self.accepted[kind].keys() <= present.keys():
                raise ValueError("REMOVED_SOURCE_ROW")
            accepted[kind] = present
            if new:
                out = io.StringIO(newline="")
                writer = csv.DictWriter(out, fieldnames=list(INPUTS[kind].model_fields))
                writer.writeheader()
                writer.writerows(new)
                planned[kind] = (out.getvalue().encode("utf-8"), len(new))
        current_docs = {n: d for n, d in stage.manifest.items() if n.startswith("app_visible/")}
        if any(current_docs.get(n) != d for n, d in self.documents.items()):
            raise ValueError("CHANGED_OR_REMOVED_ORIGINAL")
        new_docs = {n: stage.bytes[n] for n in current_docs if n not in self.documents}
        return planned, new_docs, accepted, current_docs

    def commit(self, plan):
        self.accepted.update(plan[2])
        self.documents = plan[3]
