"""Read only an explicitly exported application-visible snapshot, never a corpus root."""

import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path

IMPORTS = ("customers", "payer-aliases", "invoices", "bank-transactions")
GROUPS = {
    "alias_verifications",
    "contracts",
    "late_evidence",
    "pods",
    "promotions",
    "remittances",
    "tax_certificates",
    "warehouse_records",
}
MIMES = {
    ".pdf": "application/pdf",
    ".eml": "message/rfc822",
    ".txt": "text/plain",
    ".json": "application/json",
}
FORBIDDEN = {
    "hidden_ground_truth",
    "ground_truth",
    "answers",
    "sidecars",
    "templates",
    "generators",
    "validation",
    "scripts",
    "inventories",
    "__pycache__",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def aware(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Snapshot timestamp must include timezone")
    return result


class Snapshot:
    def __init__(self, root, as_of):
        self.root = Path(root).absolute()
        self.as_of = aware(as_of)
        self.files = {}
        if self.root.is_symlink() or self.root.is_junction():
            raise ValueError("Linked snapshot roots forbidden")
        if not (self.root / "imports").is_dir() or not (self.root / "app_visible").is_dir():
            raise ValueError("Expected exported imports/ and app_visible/, not a benchmark root")
        for path in sorted(self.root.rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise ValueError("Linked snapshot members forbidden")
            relative = path.relative_to(self.root)
            if any(part.lower() in FORBIDDEN for part in relative.parts):
                raise ValueError("Forbidden non-runtime snapshot member")
            if not path.is_file():
                continue
            name = relative.as_posix()
            valid = name in {f"imports/{kind}.csv" for kind in IMPORTS}
            valid |= (
                len(relative.parts) == 3
                and relative.parts[:2] == ("app_visible", "correlation_sources")
                and path.suffix.lower() == ".json"
            )
            valid |= (
                len(relative.parts) == 4
                and relative.parts[:2] == ("app_visible", "evidence_corpus")
                and relative.parts[2] in GROUPS
                and path.suffix.lower() in MIMES
            )
            if not valid or path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Unallowlisted or oversized application input")
            self.files[name] = {"sha256": sha(path.read_bytes()), "bytes": path.stat().st_size}
        if (
            len(self.files) > 10000
            or sum(v["bytes"] for v in self.files.values()) > 64 * 1024 * 1024
        ):
            raise ValueError("Snapshot resource limit")
        if not all(f"imports/{kind}.csv" in self.files for kind in IMPORTS):
            raise ValueError("Four unchanged CSV imports required")

    def read(self, name):
        if name not in self.files:
            raise ValueError("Input outside sealed runtime allowlist")
        path = self.root / name
        if not path.resolve().is_relative_to(self.root.resolve()) or path.is_symlink():
            raise ValueError("Input escaped snapshot root")
        raw = path.read_bytes()
        if sha(raw) != self.files[name]["sha256"]:
            raise ValueError("Snapshot changed during evaluation")
        return raw

    def verify(self):
        other = Snapshot(self.root, self.as_of.isoformat())
        if self.files != other.files:
            raise ValueError("Source export was modified")

    def temporal_checks(self):
        findings = []
        for kind in IMPORTS:
            rows = list(
                csv.DictReader(io.StringIO(self.read(f"imports/{kind}.csv").decode("utf-8-sig")))
            )
            field = {
                "bank-transactions": "occurred_at",
                "payer-aliases": "verified_at",
                "invoices": "issued_date",
            }.get(kind)
            for index, row in enumerate(rows, 2):
                if field:
                    future = (
                        aware(row[field]) > self.as_of
                        if field != "issued_date"
                        else row[field] > self.as_of.date().isoformat()
                    )
                    if future:
                        findings.append({"kind": kind, "row": index, "code": "AFTER_EXPORT_CUTOFF"})
        return findings
