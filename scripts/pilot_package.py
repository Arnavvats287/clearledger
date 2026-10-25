"""Evaluator-only package verification. Never runs a dataset generator."""

import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_relative(value):
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(
            part.rstrip(" .") != part
            or re.search(r'[<>"|?*\x00-\x1f]', part)
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I)
            for part in path.parts
        )
    ):
        raise ValueError("Unsafe package path")
    return path


def verify_archive(archive):
    """Verify every byte before extracting; manifest has no external trust signature."""
    if Path(archive).stat().st_size > 16_777_216:
        raise ValueError("Archive resource limit")
    with ZipFile(archive) as zipped:
        members = zipped.infolist()
        if len(members) > 1000 or sum(i.file_size for i in members) > 16_777_216:
            raise ValueError("Package resource limit")
        names = set()
        for item in members:
            path = safe_relative(item.filename)
            if (
                len(path.parts) < 2
                or path.parts[0] != "clearledger_pilot_v1"
                or stat.S_ISLNK(item.external_attr >> 16)
                or item.flag_bits & 1
                or item.file_size > 2_097_152
                or item.file_size > max(1, item.compress_size) * 200
            ):
                raise ValueError("Unsupported package member")
            if item.filename.casefold() in names:
                raise ValueError("Duplicate package member")
            names.add(item.filename.casefold())
        manifest = json.loads(zipped.read("clearledger_pilot_v1/MANIFEST.json"))
        files = manifest["all_other_files"]
        actual = {
            str(PurePosixPath(i.filename).relative_to("clearledger_pilot_v1")) for i in members
        } - {"MANIFEST.json"}
        if set(files) != actual or manifest["file_count_excluding_manifest"] != len(actual):
            raise ValueError("Manifest coverage mismatch")
        for name, metadata in files.items():
            safe_relative(name)
            raw = zipped.read("clearledger_pilot_v1/" + name)
            if len(raw) != metadata["bytes"] or digest(raw) != metadata["sha256"]:
                raise ValueError("Manifest integrity mismatch")
        return {
            "zip_sha256": digest(Path(archive).read_bytes()),
            "files": len(members),
            "verified_members": len(files),
            "expanded_bytes": sum(i.file_size for i in members),
        }


def unpack(archive, destination):
    integrity = verify_archive(archive)
    destination.mkdir(parents=True, exist_ok=False)
    with ZipFile(archive) as zipped:
        for item in zipped.infolist():
            path = destination.joinpath(*safe_relative(item.filename).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(zipped.read(item))
    return destination / "clearledger_pilot_v1", integrity


class VisibleSplit:
    """Explicit app-input boundary: imports, inventory, events and original sources only.

    No hidden labels, canonical-text answers, extraction sidecars or package metadata.
    This is dataflow isolation, not OS access control against a compromised host.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.reads = []

    def read(self, relative):
        path = safe_relative(relative)
        allowed = (
            (
                len(path.parts) == 2
                and path.parts[0] == "imports"
                and path.name
                in {"customers.csv", "payer-aliases.csv", "invoices.csv", "bank-transactions.csv"}
            )
            or relative
            in {
                "app_visible/evidence_corpus/evidence_inventory.jsonl",
                "app_visible/operational_events.jsonl",
            }
            or (
                path.parts[:2] == ("app_visible", "evidence_corpus")
                and path.suffix in {".pdf", ".eml", ".txt"}
                and not path.name.endswith(".canonical.txt")
            )
        )
        requested = self.root.joinpath(*path.parts)
        target = requested.resolve()
        if (
            not allowed
            or not target.is_relative_to(self.root)
            or "hidden_ground_truth" in path.parts
            or any(part.is_symlink() for part in (requested, *requested.parents))
        ):
            raise ValueError("Forbidden application input")
        self.reads.append(relative)
        return target.read_bytes()


def copy_visible(package_root, split, destination):
    """Copy allowlisted originals only to a distinct app input directory."""
    visible = VisibleSplit(package_root / split)
    inventory = [
        json.loads(line)
        for line in visible.read(
            "app_visible/evidence_corpus/evidence_inventory.jsonl"
        ).splitlines()
        if line
    ]
    paths = [
        f"imports/{name}.csv"
        for name in ("customers", "payer-aliases", "invoices", "bank-transactions")
    ]
    paths += [
        "app_visible/evidence_corpus/evidence_inventory.jsonl",
        "app_visible/operational_events.jsonl",
    ]
    paths += ["app_visible/" + entry["source_path"] for entry in inventory]
    for relative in paths:
        target = destination.joinpath(*safe_relative(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(visible.read(relative))
    # No metadata/answer key/generator directory is copied across this boundary.
    assert not any(p.name == "hidden_ground_truth" for p in destination.rglob("*"))
    return VisibleSplit(destination)


def verify_unchanged(package_root, archive):
    """Validator and application must not edit even the evaluator's package copy."""
    with ZipFile(archive) as zipped:
        return all(
            (package_root.parent / item.filename).read_bytes() == zipped.read(item)
            for item in zipped.infolist()
        )
