"""Evaluator-only package verification. Never runs a dataset generator."""

import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

PACKAGE_ROOTS = {"clearledger_pilot_v1", "clearledger_pilot_v1_1"}


def archive_root(zipped):
    roots = {safe_relative(item.filename).parts[0] for item in zipped.infolist()}
    if len(roots) != 1 or not roots.issubset(PACKAGE_ROOTS):
        raise ValueError("Unsupported archive root")
    return roots.pop()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def portable_validator_source(source):
    """Evaluator adapter only: preserve every assertion and original package byte."""
    old = "str(p.relative_to(root))"
    if source.count(old) != 1:
        raise ValueError("Unexpected validator path expression")
    return source.replace(old, "p.relative_to(root).as_posix()")


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
        root = archive_root(zipped)
        for item in members:
            path = safe_relative(item.filename)
            if (
                len(path.parts) < 2
                or path.parts[0] != root
                or stat.S_ISLNK(item.external_attr >> 16)
                or item.flag_bits & 1
                or item.file_size > 2_097_152
                or item.file_size > max(1, item.compress_size) * 200
            ):
                raise ValueError("Unsupported package member")
            if item.filename.casefold() in names:
                raise ValueError("Duplicate package member")
            names.add(item.filename.casefold())
        manifest = json.loads(zipped.read(root + "/MANIFEST.json"))
        if manifest.get("archive_root", root) != root:
            raise ValueError("Manifest root mismatch")
        files = manifest["all_other_files"]
        actual = {str(PurePosixPath(i.filename).relative_to(root)) for i in members} - {
            "MANIFEST.json"
        }
        if set(files) != actual or manifest["file_count_excluding_manifest"] != len(actual):
            raise ValueError("Manifest coverage mismatch")
        for name, metadata in files.items():
            safe_relative(name)
            raw = zipped.read(root + "/" + name)
            if len(raw) != metadata["bytes"] or digest(raw) != metadata["sha256"]:
                raise ValueError("Manifest integrity mismatch")
        return {
            "zip_sha256": digest(Path(archive).read_bytes()),
            "files": len(members),
            "verified_members": len(files),
            "expanded_bytes": sum(i.file_size for i in members),
            "archive_root": root,
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
    return destination / integrity["archive_root"], integrity


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
                "app_visible/COMPATIBILITY_ADDITIONS.json",
            }
            or (
                path.parts[:2] == ("app_visible", "evidence_corpus")
                and path.suffix in {".pdf", ".eml", ".txt"}
                and not path.name.endswith(".canonical.txt")
            )
            or (
                len(path.parts) == 3
                and path.parts[:2] == ("app_visible", "compatibility_structured_remittances")
                and path.suffix == ".json"
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
    if (package_root / split / "app_visible/COMPATIBILITY_ADDITIONS.json").exists():
        paths.append("app_visible/COMPATIBILITY_ADDITIONS.json")
        additions = json.loads(visible.read("app_visible/COMPATIBILITY_ADDITIONS.json"))
        paths += ["app_visible/" + entry["source_path"] for entry in additions["documents"]]
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


def compare_successor(baseline, successor):
    """Evaluator-only predecessor preservation check; never supplies runtime inputs."""
    with ZipFile(baseline) as old, ZipFile(successor) as new:
        first, second = archive_root(old) + "/", archive_root(new) + "/"
        csvs = canonical = inventory = pdfs = 0
        for name in old.namelist():
            relative = name.removeprefix(first)
            if "/imports/" in relative and relative.endswith(".csv"):
                assert old.read(name) == new.read(second + relative), "Financial CSV changed"
                csvs += 1
            if relative.endswith(".canonical.txt"):
                assert old.read(name) == new.read(second + relative), "Canonical sidecar changed"
                canonical += 1
            if relative.endswith("/evidence_inventory.jsonl"):
                assert old.read(name) == new.read(second + relative), "Legacy inventory changed"
                inventory += 1
            if relative.endswith(".pdf"):
                pdfs += old.read(name) != new.read(second + relative)
        for split in ("dev", "eval"):
            path = split + "/hidden_ground_truth/ground_truth_cases.jsonl"
            a = [json.loads(line) for line in old.read(first + path).splitlines() if line]
            b = [json.loads(line) for line in new.read(second + path).splitlines() if line]
            for cases in (a, b):
                for case in cases:
                    for pointer in case["evidence_pointers"]:
                        pointer.pop("source_sha256")
            assert a == b, "Case expectations or citation spans changed"
        return {
            "baseline_sha256": digest(Path(baseline).read_bytes()),
            "unchanged_csvs": csvs,
            "unchanged_canonical_sidecars": canonical,
            "unchanged_legacy_inventories": inventory,
            "changed_pdfs": pdfs,
            "case_semantics_and_citation_offsets_preserved": True,
        }
