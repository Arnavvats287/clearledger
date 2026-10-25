"""Runs only in the bounded, credential-free parser subprocess. No URLs/OCR/tools."""

import io
import logging
from email import policy
from email.parser import BytesParser

from pypdf import PdfReader, apply_configuration
from pypdf.generic import DictionaryObject

from clearledger.document_contract import MAX_DOCUMENT_BYTES, MAX_PAGES, MAX_TEXT, ExtractionError
from clearledger.remittance_parser import json_positions, unique_json

PARSER_VERSION = "canonical-text-v1"


def canonical(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or len(value) > MAX_TEXT:
        raise ExtractionError("INVALID_TEXT")
    return value


def parse_pdf(raw: bytes) -> tuple[list[str], str]:
    import pypdf.filters as filters

    logging.getLogger("pypdf").disabled = True
    original_decode = filters.decode_stream_data
    decoded = 0

    def bounded_decode(stream):
        nonlocal decoded
        declarations = stream.get("/Filter", [])
        if isinstance(declarations, str):
            declarations = [declarations]
        if any(value not in {"/FlateDecode", "/ASCIIHexDecode"} for value in declarations):
            raise ExtractionError("UNSUPPORTED_PDF_FILTER")
        value = original_decode(stream)
        decoded += len(value)
        if decoded > 8_388_608:
            raise ExtractionError("PDF_DECOMPRESSION_LIMIT")
        return value

    filters.decode_stream_data = bounded_decode
    try:
        with apply_configuration(
            maximum_declared_stream_length=MAX_DOCUMENT_BYTES,
            zlib_maximum_output_length=MAX_DOCUMENT_BYTES,
            array_based_stream_maximum_output_length=MAX_DOCUMENT_BYTES,
            array_maximum_element_count=4096,
            dictionary_maximum_element_count=4096,
            stream_decoding_work_maximum_length=8_388_608,
            stream_filters_maximum_length=2,
            stream_parsing_work_maximum_count=100_000,
            page_tree_maximum_entries=MAX_PAGES,
            page_tree_maximum_depth=8,
            xform_maximum_invocations_per_extraction=100,
        ):
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise ExtractionError("ENCRYPTED_PDF")
            if sum(len(values) for values in reader.xref.values()) > 4096:
                raise ExtractionError("PDF_OBJECT_LIMIT")
            if not 1 <= len(reader.pages) <= MAX_PAGES:
                raise ExtractionError("PAGE_LIMIT")
            # Inspect dictionaries, but never decode images, attachments or follow external links.
            for generation, values in reader.xref.items():
                for identifier in values:
                    if identifier == 0:
                        continue
                    from pypdf.generic import IndirectObject

                    value = reader.get_object(IndirectObject(identifier, generation, reader))
                    if isinstance(value, DictionaryObject) and any(
                        key in value
                        for key in (
                            "/JS",
                            "/JavaScript",
                            "/Launch",
                            "/EmbeddedFiles",
                            "/EmbeddedFile",
                            "/XFA",
                            "/OpenAction",
                            "/AA",
                            "/RichMedia",
                            "/AcroForm",
                        )
                    ):
                        raise ExtractionError("ACTIVE_PDF_CONTENT")
            pages = [canonical(page.extract_text()) for page in reader.pages]
            if sum(map(len, pages)) > MAX_TEXT:
                raise ExtractionError("TEXT_LIMIT")
            return pages, ("NEEDS_OCR" if any(not page.strip() for page in pages) else "READY")
    finally:
        filters.decode_stream_data = original_decode


def parse_email(raw: bytes) -> tuple[list[str], str]:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if message.defects:
        raise ExtractionError("MALFORMED_EMAIL")
    if not message.keys() or not (message.get("From") or message.get("Subject")):
        raise ExtractionError("MALFORMED_EMAIL")
    parts = []
    for part in message.walk():
        parts.append(part)
        if len(parts) > 32:
            raise ExtractionError("EMAIL_PART_LIMIT")
    text_parts = []
    total = 0
    for part in parts:
        if part.defects:
            raise ExtractionError("MALFORMED_EMAIL")
        if part.is_multipart():
            continue
        if (
            part.get_content_type() != "text/plain"
            or part.get_content_disposition() == "attachment"
        ):
            raise ExtractionError("UNSUPPORTED_EMAIL_PART")
        data = part.get_payload(decode=True)
        if part.defects or not isinstance(data, bytes):
            raise ExtractionError("MALFORMED_EMAIL")
        if str(part.get("Content-Transfer-Encoding", "7bit")).lower() not in {
            "7bit",
            "8bit",
            "base64",
            "quoted-printable",
            "binary",
        }:
            raise ExtractionError("UNSUPPORTED_EMAIL_ENCODING")
        total += len(data)
        if total > MAX_DOCUMENT_BYTES:
            raise ExtractionError("EMAIL_DECODE_LIMIT")
        charset = part.get_content_charset() or "utf-8"
        if charset not in {"utf-8", "us-ascii"}:
            raise ExtractionError("UNSUPPORTED_EMAIL_CHARSET")
        text_parts.append(data.decode(charset, errors="strict"))
    # Header addresses/names are unnecessary to extraction; immutable original retains them.
    subject = str(message.get("Subject", ""))
    return [
        canonical((f"Subject: {subject}\n\n" if subject else "") + "\n".join(text_parts))
    ], "READY"


def parse(raw: bytes, mime: str) -> dict:
    if not 0 < len(raw) <= MAX_DOCUMENT_BYTES:
        raise ExtractionError("DOCUMENT_SIZE")
    if mime == "application/pdf":
        if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-1024:]:
            raise ExtractionError("MALFORMED_PDF")
        pages, status = parse_pdf(raw)
    elif mime == "message/rfc822":
        pages, status = parse_email(raw)
    elif mime in {"text/plain", "application/json"}:
        if raw.startswith((b"%PDF", b"PK", b"\x1f\x8b", b"MZ")):
            raise ExtractionError("MIME_MISMATCH")
        pages, status = [canonical(raw.decode("utf-8-sig", errors="strict"))], "READY"
        if not pages[0].strip() or pages[0].lstrip().lower().startswith(("<html", "<!doctype")):
            raise ExtractionError("UNSUPPORTED_TEXT")
        if mime == "application/json":
            try:
                json_positions(pages[0])
                unique_json(pages[0])
            except (ValueError, IndexError, RecursionError, ExtractionError):
                raise ExtractionError("MALFORMED_JSON") from None
    else:
        raise ExtractionError("UNSUPPORTED_MIME")
    return {"pages": pages, "status": status, "parser_version": PARSER_VERSION}
