"""Source-only packet preparation and verification. Never reads scorer annotations."""

import csv
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .contracts import Box, ContractPacket, DocilePacket, Hypothesis, Page, Quote, Word


def no_links(path: Path) -> None:
    for parent in (path, *path.absolute().parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("LINK_REFUSED")


def load_json(path: Path) -> Any:
    no_links(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("INPUT_TOO_LARGE")
    return json.loads(path.read_text(encoding="utf8"))


def sha256(path: Path) -> str:
    no_links(path)
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def load_plan(path: Path) -> dict[str, Any]:
    no_links(path.with_suffix(".sha256"))
    if sha256(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("FROZEN_PLAN_HASH_MISMATCH")
    plan: dict[str, Any] = load_json(path)
    if plan["protocol"] != "clearledger-external-evaluation-v1":
        raise ValueError("UNKNOWN_PROTOCOL")
    return plan


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


@dataclass(frozen=True)
class Located:
    status: Literal["VALID", "MISSING", "AMBIGUOUS", "RANGE_MISMATCH"]
    intervals: tuple[tuple[int, int], ...] = ()


def locate(text: str, quote: Quote) -> Located:
    # Overlapping occurrences count. Explicit offsets cannot rescue ambiguous text.
    start = text.find(quote.text)
    if start < 0:
        return Located("MISSING")
    if text.find(quote.text, start + 1) >= 0:
        return Located("AMBIGUOUS")
    end = start + len(quote.text)
    if quote.start is not None and (quote.start, quote.end) != (start, end):
        return Located("RANGE_MISMATCH")
    return Located("VALID", ((start, end),))


def contract_packets(path: Path, ids: list[str], hypothesis_ids: list[str]) -> list[ContractPacket]:
    data = load_json(path)
    wanted = set(ids)
    if len(wanted) != len(ids):
        raise ValueError("DUPLICATE_DOCUMENT")
    # Only whitelist public hypotheses, never copy raw dictionaries.
    hypotheses = [
        Hypothesis(hypothesis_id=k, text=data["labels"][k]["hypothesis"]) for k in hypothesis_ids
    ]
    packets = {}
    for document in data["documents"]:
        identifier = str(document["id"])
        if identifier in wanted:
            if identifier in packets:
                raise ValueError("DUPLICATE_DOCUMENT")
            packets[identifier] = ContractPacket(
                document_id=identifier,
                text=document["text"],
                hypotheses=hypotheses,
            )
    if set(packets) != wanted:
        raise ValueError("MISSING_DOCUMENT")
    return [packets[k] for k in ids]


def docile_packet(ocr_path: Path, document_id: str) -> DocilePacket:
    # Reads supplied OCR only. No Dataset object: that eagerly loads annotations.
    data = load_json(ocr_path)
    pages = []
    for page_number, raw_page in enumerate(data["pages"]):
        if raw_page["page_idx"] != page_number:
            raise ValueError("INVALID_OCR_PAGE")
        pieces, words = [], []
        offset = 0
        for block_index, block in enumerate(raw_page["blocks"]):
            if block_index:
                pieces.append("\n")
                offset += 1
            for line in block["lines"]:
                for word_index, word in enumerate(line["words"]):
                    if word_index:
                        pieces.append(" ")
                        offset += 1
                    value = word["value"]
                    if not isinstance(value, str) or not value:
                        raise ValueError("INVALID_OCR_WORD")
                    (left, top), (right, bottom) = word["geometry"]
                    words.append(
                        Word(
                            start=offset,
                            end=offset + len(value),
                            box=Box(
                                left=float(left),
                                top=float(top),
                                right=float(right),
                                bottom=float(bottom),
                            ),
                        )
                    )
                    pieces.append(value)
                    offset += len(value)
                pieces.append("\n")
                offset += 1
        text = "".join(pieces)
        # Empty OCR is explicit: no synthetic text or fabricated source locations.
        if not text.strip():
            raise ValueError("EMPTY_OCR_PAGE")
        pages.append(Page(page=page_number, text=text, words=words))
    return DocilePacket(document_id=document_id, pages=pages)


def quote_box(packet: DocilePacket, quote: Quote, page_hint: int | None) -> dict[str, Any]:
    candidates = []
    ambiguous = False
    for page in packet.pages:
        result = locate(page.text, quote)
        ambiguous |= result.status == "AMBIGUOUS"
        if result.status == "VALID":
            candidates.append((page, result.intervals[0]))
    # Page hints do not rescue repeated quotes elsewhere in the source.
    if ambiguous or len(candidates) > 1:
        return {"status": "AMBIGUOUS"}
    if not candidates:
        return {"status": "UNALIGNED"}
    page, (start, end) = candidates[0]
    if page_hint is not None and page.page != page_hint:
        return {"status": "PAGE_MISMATCH"}
    words = [word for word in page.words if word.start < end and word.end > start]
    if not words:
        return {"status": "UNALIGNED"}
    # The bbox is derived only from input OCR word geometry, never annotation boxes.
    return {
        "status": "VALID",
        "page": page.page,
        "bbox": [
            min(w.box.left for w in words),
            min(w.box.top for w in words),
            max(w.box.right for w in words),
            max(w.box.bottom for w in words),
        ],
    }


def write_packets(
    directory: Path, packets: list[ContractPacket] | list[DocilePacket]
) -> dict[str, str]:
    no_links(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("PACKET_DIRECTORY_NOT_EMPTY")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for packet in packets:
        path = directory / f"{packet.document_id}.json"
        write_json(path, packet.model_dump(mode="json"))
        manifest[path.name] = sha256(path)
    return manifest


def read_packets(directory: Path, manifest: dict[str, str], kind: str) -> dict[str, Any]:
    no_links(directory)
    if kind not in {"contract-nli", "docile"}:
        raise ValueError("UNSUPPORTED_PACKET_KIND")
    if set(p.name for p in directory.iterdir()) != set(manifest):
        raise ValueError("UNEXPECTED_PACKET_FILES")
    model = ContractPacket if kind == "contract-nli" else DocilePacket
    result = {}
    for name, expected_hash in manifest.items():
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("UNSAFE_PACKET_NAME")
        path = directory / name
        if sha256(path) != expected_hash:
            raise ValueError("PACKET_HASH_MISMATCH")
        packet = model.model_validate(load_json(path))
        if name != f"{packet.document_id}.json":
            raise ValueError("PACKET_ID_MISMATCH")
        result[packet.document_id] = packet
    return result


RECBENCH_COLUMNS = {
    "bank_statements": "stmt_line_id bank_account currency amount_minor value_date "
    "counterparty reference direction",
    "ledger": "txn_id order_id type entity_id currency amount_minor created_at processor "
    "processor_ref customer_ref original_txn_id status",
    "payouts": "payout_id payout_ref processor entity_id settle_currency amount_minor "
    "line_count sales_date expected_arrival_date",
    "settlement_lines": "line_id processor line_type processor_txn_ref merchant_ref entity_id "
    "gross_currency gross_amount_minor fee_amount_minor net_amount_minor settle_currency "
    "fx_rate sales_date payout_id",
}


def project_recbench_sources(root: Path, output: Path) -> dict[str, str]:
    """Copy only four native source tables; no AR/currency adapter and no gold traversal."""
    no_links(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("PACKET_DIRECTORY_NOT_EMPTY")
    output.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, columns in RECBENCH_COLUMNS.items():
        path = root / "csv" / f"{name}.csv"
        no_links(path)
        with path.open(encoding="utf8", newline="") as stream:
            if next(csv.reader(stream)) != columns.split():
                raise ValueError("UNEXPECTED_SOURCE_COLUMNS")
        target = output / path.name
        # Exclusive creation and bounded streaming; retain original bytes and natural units.
        hasher = hashlib.sha256()
        with path.open("rb") as source, target.open("xb") as destination:
            while block := source.read(1024 * 1024):
                hasher.update(block)
                destination.write(block)
        result[target.name] = hasher.hexdigest()
    return result


def verify_source_tables(directory: Path, manifest: dict[str, str]) -> None:
    no_links(directory)
    expected = {f"{name}.csv" for name in RECBENCH_COLUMNS}
    if set(manifest) != expected or {p.name for p in directory.iterdir()} != expected:
        raise ValueError("UNEXPECTED_SOURCE_TABLES")
    if any(sha256(directory / name) != checksum for name, checksum in manifest.items()):
        raise ValueError("SOURCE_TABLE_HASH_MISMATCH")
