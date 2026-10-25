"""Application runner: receives VisibleSplit, never hidden answers or scenario labels."""

import csv
import hashlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from clearledger.document_contract import ExtractionError
from clearledger.document_privacy import project
from clearledger.models import (
    BankTransaction,
    Customer,
    Invoice,
    Organization,
    PayerAlias,
    ProviderReservation,
    Receipt,
)

ROOT = Path(__file__).resolve().parents[1]
FINANCIAL = (Customer, PayerAlias, Invoice, BankTransaction, Receipt)


def rows(engine, models=FINANCIAL):
    with engine.connect() as connection:
        return {
            m.__tablename__: [
                dict(row)
                for row in connection.execute(select(m.__table__).order_by(m.id)).mappings()
            ]
            for m in models
        }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


@contextmanager
def disposable_database(admin_url):
    """Never migrate/drop the URL's database. Destruction uses a generated exact name."""
    from sqlalchemy.engine import make_url

    url = make_url(admin_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Real PostgreSQL required")
    name = "clearledger_pilot_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        try:
            if created:
                assert re.fullmatch(r"clearledger_pilot_[0-9a-f]{32}", name)
                with admin.connect() as connection:
                    connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        finally:
            admin.dispose()


@contextmanager
def application(url, company, token, store, log):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "TEMP", "TMP"}
    }
    env.update(
        DATABASE_URL=url,
        ORGANIZATION_ID=str(company),
        DOCUMENT_API_TOKEN=token,
        DOCUMENT_ROOT=str(store),
        EXTRACTION_PROVIDER="disabled",
        EXTERNAL_AI_ENABLED="false",
        GEMINI_API_KEY="",
        GEMINI_MODEL="",
        PRIVACY_REVIEW_REFERENCE="",
        LLM_DAILY_REQUESTS="0",
        LLM_DAILY_INPUT_TOKENS="0",
        LLM_DAILY_OUTPUT_TOKENS="0",
    )
    # A separate process gets no dataset/hidden path, labels, source maps or score objects.
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "clearledger.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30
            ) as client:
                deadline = time.monotonic() + 20
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Application startup failed; inspect private log")
                    try:
                        if client.get("/ready").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Application readiness timeout")
                    time.sleep(0.1)
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


class API:
    def __init__(self, client, token):
        self.client, self.token = client, token
        self.latencies = []
        self.calls = 0

    def request(self, method, path, *, expected=200, key=None, headers=None, **kwargs):
        start = time.perf_counter_ns()
        response = self.client.request(
            method,
            path,
            headers={
                "Authorization": "Bearer " + self.token,
                "X-Actor-ID": "pilot-simulated-operator",
                "Idempotency-Key": str(key or uuid4()),
                **(headers or {}),
            },
            **kwargs,
        )
        self.calls += 1
        self.latencies.append(time.perf_counter_ns() - start)
        allowed = (expected,) if isinstance(expected, int) else expected
        if response.status_code not in allowed:
            raise RuntimeError(f"Unexpected API status {response.status_code} at {path}")
        return response

    def get(self, path):
        return self.request("GET", path).json()

    def collection(self, path):
        result = []
        while True:
            page = self.get(f"{path}?limit=100&offset={len(result)}")
            result.extend(page)
            if len(page) < 100:
                return result


def csv_subset(raw, row):
    """In-memory negative/replay API request, never edits or creates dataset files."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=next(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    )
    writer.writeheader()
    writer.writerow(row)
    return stream.getvalue().encode()


def import_files(api, visible, engine):
    results = []
    for kind in ("customers", "payer-aliases", "invoices", "bank-transactions"):
        raw = visible.read(f"imports/{kind}.csv")
        headers = {
            "Content-Type": "text/csv",
            "X-Data-Contract-Version": "1.0",
            "X-Source-Filename": kind + ".csv",
        }
        key = uuid4()
        first = api.request(
            "POST", f"/imports/{kind}", key=key, headers=headers, content=raw
        ).json()
        before = fingerprint(rows(engine))
        repeated = api.request(
            "POST", f"/imports/{kind}", key=key, headers=headers, content=raw
        ).json()
        duplicate = api.request("POST", f"/imports/{kind}", headers=headers, content=raw).json()
        assert fingerprint(rows(engine)) == before, "Replay mutated financial records"
        results.append({"kind": kind, "first": first, "same_key": repeated, "fresh_key": duplicate})
        # Header-only malformed request checks schema enforcement without altering original data.
        header, _, body = raw.partition(b"\n")
        invalid = header.rstrip(b"\r") + b",unexpected\n" + body
        api.request(
            "POST",
            f"/imports/{kind}",
            expected=422,
            headers=headers,
            content=invalid,
        )
        assert fingerprint(rows(engine)) == before, "Rejected CSV mutated financial records"
        if kind == "bank-transactions":
            probes = []
            for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
                same = api.request(
                    "POST", f"/imports/{kind}", headers=headers, content=csv_subset(raw, row)
                ).json()
                assert same["inserted"] == same["receipts_created"] == 0
                changed = {**row, "amount_paise": str(int(row["amount_paise"]) + 1)}
                api.request(
                    "POST",
                    f"/imports/{kind}",
                    headers=headers,
                    expected=409,
                    content=csv_subset(raw, changed),
                )
                assert fingerprint(rows(engine)) == before
                probes.append({"duplicate": fingerprint(row), "conflict": fingerprint(changed)})
            results[-1]["row_probes"] = probes
    return results


def match_all(api, receipts, invoices):
    versions = {row["id"]: row["version"] for row in invoices}
    results = {}
    for receipt in receipts:
        modes = {}
        for suffix, context in (
            ("match", "matching-context"),
            ("match-advanced", "advanced-matching-context"),
        ):
            path = f"/receipts/{receipt['id']}/{suffix}"
            snapshot = api.get(f"/receipts/{receipt['id']}/{context}")
            body = {
                "expected_receipt_version": receipt["version"],
                "expected_invoice_versions": versions,
                "expected_snapshot_sha256": snapshot["snapshot_sha256"],
            }
            key = uuid4()
            result = api.request("POST", path, key=key, json=body).json()
            for retry_key in (key, uuid4()):
                replay = api.request("POST", path, key=retry_key, json=body).json()
                assert replay == result, "Matching replay changed immutable proposal"
            modes[suffix] = result
        results[receipt["id"]] = modes
    return results


def attest_visible_references(api, receipts, banks, invoices, aliases):
    """Explicitly simulated operator mode, NOT naturally discovered verified intent.

    No answer labels consulted. Require an imported verified alias/owner association
    before attesting exact delimited memo literals; never use names/amounts alone.
    """
    bank_by_id = {row["id"]: row for row in banks}
    customers = {row["normalized_alias"]: row["customer_id"] for row in aliases}
    evidence = []
    for receipt in receipts:
        bank = bank_by_id[receipt["bank_transaction_id"]]
        customer = customers.get(" ".join(bank["payer_name"].split()).casefold())
        if customer is None:
            continue
        for invoice in invoices:
            if invoice["customer_id"] != customer:
                continue
            match = re.search(
                r"(?<![\w./-])" + re.escape(invoice["invoice_number"]) + r"(?![\w./-])",
                bank["memo"],
            )
            if match is None:
                continue
            record = api.request(
                "POST",
                f"/receipts/{receipt['id']}/matching-evidence",
                json={
                    "kind": "INVOICE_REFERENCE",
                    "customer_id": customer,
                    "invoice_id": invoice["id"],
                    "expected_customer_version": 1,
                    "expected_receipt_version": receipt["version"],
                    "expected_invoice_version": invoice["version"],
                    "source_import_id": bank["source_import_id"],
                    "source_row": bank["source_row"],
                    "source_field": "memo",
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "exact_quote": match.group(),
                },
            ).json()
            evidence.append(record)
    return evidence


def documents(api, visible):
    inventory = [
        json.loads(line)
        for line in visible.read(
            "app_visible/evidence_corpus/evidence_inventory.jsonl"
        ).splitlines()
        if line
    ]
    observations = {}
    visible_document_ids = set()
    for entry in sorted(
        inventory, key=lambda e: (datetime.fromisoformat(e["available_at"]), e["document_id"])
    ):
        # Public availability is the only clock; hidden investigation stages never enter here.
        raw = visible.read("app_visible/" + entry["source_path"])
        name = Path(entry["source_path"]).name
        mime = {".pdf": "application/pdf", ".eml": "message/rfc822", ".txt": "text/plain"}[
            Path(name).suffix
        ]
        headers = {"Content-Type": mime, "X-Source-Filename": name, "X-Synthetic-Data": "true"}
        key = uuid4()
        response = api.request(
            "POST", "/documents", headers=headers, key=key, content=raw, expected=(200, 422)
        )
        upload_result = response.json()
        doc = (
            upload_result
            if response.status_code == 200
            else api.get(f"/documents/{upload_result['document_id']}")
        )
        if response.status_code == 422:
            assert (
                doc["parse_status"] == "PARSE_FAILED"
                and doc["parse_error"] == upload_result["code"]
            )
        visible_document_ids.add(doc["id"])
        assert {row["id"] for row in api.collection("/documents")} == visible_document_ids
        assert (
            api.request(
                "POST",
                "/documents",
                headers=headers,
                key=key,
                content=raw,
                expected=response.status_code,
            ).json()
            == upload_result
        )
        assert (
            api.request(
                "POST", "/documents", headers=headers, content=raw, expected=response.status_code
            ).json()
            == upload_result
        )
        stored = api.request("GET", f"/documents/{doc['id']}/original").content
        assert stored == raw and hashlib.sha256(raw).hexdigest() == doc["content_sha256"]
        canonical = api.get(f"/documents/{doc['id']}/text")
        for page_number, page in enumerate(canonical["pages"], 1):
            if not page:
                continue
            span = {
                "page": page_number,
                "start": 0,
                "end": min(2000, len(page)),
                "quote": page[:2000],
            }
            verified = api.request("POST", f"/documents/{doc['id']}/verify-span", json=span).json()
            assert verified["source_consistent"] and not verified["financial_authority"]
            api.request(
                "POST",
                f"/documents/{doc['id']}/verify-span",
                expected=422,
                json={**span, "quote": "!" + span["quote"][1:]},
            )
        extraction = api.request(
            "POST",
            f"/documents/{doc['id']}/extract",
            json={"expected_document_version": doc["version"], "allow_external": False},
        ).json()
        assert not extraction["financial_authority"] and extraction["requires_human_review"]
        assert extraction["route"] != "LLM"
        blocked = api.request(
            "POST",
            f"/documents/{doc['id']}/extract",
            json={
                "expected_document_version": doc["version"],
                "allow_external": True,
                "revision_label": "offline-boundary",
            },
        ).json()
        assert blocked["route"] != "LLM" and blocked["metrics"]["attempts"] == 0
        privacy = {"status": "PROJECTED", "recognized_identifiers_remaining": 0}
        try:
            if not canonical["pages"]:
                privacy["status"] = "SKIPPED_NO_TEXT"
            sanitized = project(canonical["pages"])
            # Independent probes for representative identifiers, not a real-data privacy proof.
            sensitive = re.compile(
                r"\b[A-Z]{5}[0-9]{4}[A-Z]\b|"
                r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b|"
                r"\b[A-Z]{4}0[A-Z0-9]{6}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
            )
            privacy["recognized_identifiers_remaining"] = sum(
                len(sensitive.findall(page)) for page in sanitized.pages
            )
        except ExtractionError:
            privacy["status"] = "ABSTAINED"
        correlation = None
        if entry["document_type"] == "remittances":
            correlation = api.request(
                "POST",
                f"/documents/{doc['id']}/correlate",
                json={
                    "extraction_id": extraction["id"],
                    "expected_document_version": doc["version"],
                },
            ).json()
        observations[entry["document_id"]] = {
            "ingestion_http_status": response.status_code,
            "inventory": entry,
            "document": doc,
            "canonical": canonical,
            "extraction": extraction,
            "correlation": correlation,
            "disabled_optin": blocked,
            "privacy_probe": privacy,
        }
    return observations


def run_split(visible, url, output):
    output.mkdir(parents=True, exist_ok=False)
    engine = create_engine(url, pool_pre_ping=True)
    company, other_company, token = uuid4(), uuid4(), uuid4().hex + uuid4().hex
    try:
        with engine.connect() as connection:
            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
            schema = {
                name: [column["name"] for column in inspect(connection).get_columns(name)]
                for name in inspect(connection).get_table_names()
            }
            connection.commit()
        with Session(engine) as session, session.begin():
            session.add_all(
                [
                    Organization(id=company, name="Isolated independent pilot"),
                    Organization(id=other_company, name="Isolated scope probe"),
                ]
            )
        start = time.perf_counter_ns()
        with application(url, company, token, output / "originals", output / "api.log") as client:
            api = API(client, token)
            imports = import_files(api, visible, engine)
            before = rows(engine)
            data = {
                name: api.collection("/" + name)
                for name in (
                    "customers",
                    "payer-aliases",
                    "invoices",
                    "bank-transactions",
                    "receipts",
                )
            }
            assert len(data["receipts"]) == len(data["bank-transactions"])
            baseline = match_all(api, data["receipts"], data["invoices"])
            attestations = attest_visible_references(
                api,
                data["receipts"],
                data["bank-transactions"],
                data["invoices"],
                data["payer-aliases"],
            )
            attested = match_all(api, data["receipts"], data["invoices"])
            sources = documents(api, visible)
            other_token = uuid4().hex + uuid4().hex
            with application(
                url,
                other_company,
                other_token,
                output / "other-originals",
                output / "other-api.log",
            ) as other_client:
                scoped = API(other_client, other_token)
                for path in (
                    f"/receipts/{data['receipts'][0]['id']}",
                    f"/invoices/{data['invoices'][0]['id']}",
                    f"/documents/{next(iter(sources.values()))['document']['id']}",
                    f"/documents/{next(iter(sources.values()))['document']['id']}/original",
                ):
                    scoped.request("GET", path, expected=404)
            assert before == rows(engine), "Unexpected financial mutation"
            assert rows(engine, (ProviderReservation,))["provider_reservations"] == []
            assert client.get("/documents").status_code == 401
            elapsed = time.perf_counter_ns() - start
        result = {
            "records": data,
            "imports": imports,
            "unattested": baseline,
            "simulated_attested": attested,
            "attestations": attestations,
            "documents": sources,
            "financial_mutations": 0,
            "provider_reservations": 0,
            "tenant_isolation_404_checks": 4,
            "document_auth_401_checks": 1,
            "schema": schema,
            "visible_read_paths": visible.reads,
            "performance": {
                "elapsed_ns": elapsed,
                "api_calls": api.calls,
                "latencies_ns": api.latencies,
            },
        }
        (output / "observations.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        engine.dispose()
