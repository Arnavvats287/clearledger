import csv
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from clearledger.config import Settings
from clearledger.data_contract import INPUTS, MAX_BYTES, BankInput
from clearledger.db import build_engine
from clearledger.imports import ImportFailure, ingest, parse_csv
from clearledger.main import create_app
from clearledger.models import (
    AuditEvent,
    BankTransaction,
    Customer,
    Invoice,
    Organization,
    Receipt,
    SourceImport,
)

# Deliberately tiny, isolated code fixtures. No demonstration/evaluation dataset.
CUSTOMER = {"external_reference": "c", "name": "Test"}
INVOICE = {
    "customer_reference": "c",
    "invoice_number": "i",
    "issued_date": "2026-01-01",
    "due_date": "2026-01-02",
    "original_amount_paise": "101",
    "open_amount_paise": "100",
    "currency": "INR",
}
BANK = {
    "source_system": "test",
    "account_ref": "a",
    "external_transaction_id": "t",
    "occurred_at": "2026-01-01T12:00:00+05:30",
    "amount_paise": "100",
    "currency": "INR",
    "payer_name": "",
    "memo": "",
}
ALIAS = {
    "customer_reference": "c",
    "alias": "Test Alias",
    "verified_by": "tester",
    "verified_at": "2026-01-01T00:00:00Z",
    "evidence_reference": "test-evidence",
}


def csv_bytes(kind, *rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(INPUTS[kind].model_fields))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def post(client, kind, *rows, key=None, filename="test.csv", raw=None, **headers):
    return client.post(
        f"/imports/{kind}",
        content=csv_bytes(kind, *rows) if raw is None else raw,
        headers={
            "Content-Type": "text/csv",
            "X-Actor-ID": "tester",
            "Idempotency-Key": str(key or uuid4()),
            "X-Data-Contract-Version": "1.0",
            "X-Source-Filename": filename,
            **headers,
        },
    )


@pytest.fixture
def environment(disposable_database, migration_config):
    engine = build_engine(disposable_database.render_as_string(hide_password=False))
    with engine.connect() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
        connection.commit()
    first, second = uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add_all(
            [Organization(id=first, name="Test A"), Organization(id=second, name="Test B")]
        )
    app = create_app(
        Settings(
            database_url=disposable_database.render_as_string(hide_password=False),
            organization_id=first,
        )
    )
    other = create_app(
        Settings(
            database_url=disposable_database.render_as_string(hide_password=False),
            organization_id=second,
        )
    )
    try:
        with TestClient(app) as client, TestClient(other) as other_client:
            yield engine, first, second, client, other_client
    finally:
        engine.dispose()


def count(session, model, organization_id):
    return session.scalar(
        select(func.count()).select_from(model).where(model.organization_id == organization_id)
    )


@pytest.mark.postgres
def test_valid_imports_provenance_and_scoped_reads(environment):
    engine, first, second, client, other = environment
    customer = post(client, "customers", CUSTOMER)
    assert customer.status_code == 200, customer.text
    alias = post(client, "payer-aliases", ALIAS)
    assert alias.status_code == 200, alias.text
    invoice = post(client, "invoices", INVOICE)
    assert invoice.status_code == 200, invoice.text
    bank = post(client, "bank-transactions", BANK)
    assert bank.status_code == 200, bank.text
    assert bank.json()["receipts_created"] == 1
    for path in (
        "customers",
        "payer-aliases",
        "invoices",
        "bank-transactions",
        "receipts",
        "payments",
        "imports",
        "audit/events",
    ):
        records = client.get(f"/{path}").json()
        assert records
        assert all(record["organization_id"] == str(first) for record in records)
        assert client.get(f"/{path}/{records[0]['id']}").status_code == 200
        assert other.get(f"/{path}").json() == []
        assert other.get(f"/{path}/{records[0]['id']}").status_code == 404
    balance = client.get("/invoices").json()[0]
    assert (
        balance["original_amount_paise"],
        balance["initial_open_amount_paise"],
        balance["open_amount_paise"],
    ) == (101, 100, 100)
    receipt = client.get("/receipts").json()[0]
    assert (receipt["amount_paise"], receipt["unapplied_amount_paise"], receipt["status"]) == (
        100,
        100,
        "UNAPPLIED",
    )
    transaction = client.get("/bank-transactions").json()[0]
    assert transaction["occurred_at_source"].endswith("+05:30")
    assert transaction["occurred_at"].endswith("Z")
    assert "raw_bytes" not in client.get("/imports").text
    with Session(engine) as session:
        source = session.scalar(
            select(SourceImport).where(
                SourceImport.organization_id == first, SourceImport.kind == "bank-transactions"
            )
        )
        assert source.raw_bytes == csv_bytes("bank-transactions", BANK)
        assert source.content_sha256 == hashlib.sha256(source.raw_bytes).hexdigest()
        assert count(session, Receipt, second) == 0


@pytest.mark.postgres
def test_duplicate_replays_renames_and_conflicts(environment):
    engine, first, _, client, _ = environment
    key = uuid4()
    initial = post(client, "bank-transactions", BANK, key=key)
    assert initial.status_code == 200, initial.text
    assert (
        post(client, "bank-transactions", BANK, key=key, filename="renamed.csv").json()
        == initial.json()
    )
    duplicate = post(client, "bank-transactions", BANK, filename="renamed.csv")
    assert duplicate.json()["duplicates"] == 1
    assert duplicate.json()["receipts_created"] == 0
    # Same source timestamp expressed in another timezone is semantically identical.
    equivalent = post(client, "bank-transactions", {**BANK, "occurred_at": "2026-01-01T06:30:00Z"})
    assert equivalent.json()["duplicates"] == 1
    changed = {**BANK, "amount_paise": "101"}
    assert (
        post(client, "bank-transactions", changed, key=key).json()["code"] == "IDEMPOTENCY_CONFLICT"
    )
    conflict = post(
        client, "bank-transactions", {**BANK, "external_transaction_id": "new"}, changed
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDENTITY_CONFLICT"
    with Session(engine) as session:
        assert count(session, BankTransaction, first) == count(session, Receipt, first) == 1
        assert count(session, AuditEvent, first) >= 8
    same_file = post(client, "bank-transactions", BANK, BANK)
    assert same_file.json()["duplicates"] == 2


@pytest.mark.postgres
def test_atomic_errors_and_unknown_customer(environment):
    engine, first, _, client, other = environment
    bad = post(client, "customers", CUSTOMER, {**CUSTOMER, "external_reference": "x", "name": " "})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["row"] == 3
    assert client.get("/customers").json() == []
    assert client.get("/imports").json()[0]["status"] == "REJECTED"
    assert post(other, "customers", CUSTOMER).status_code == 200
    missing = post(client, "invoices", INVOICE)
    assert missing.status_code == 422
    assert missing.json()["code"] == "UNKNOWN_CUSTOMER"
    with Session(engine) as session:
        assert count(session, Customer, first) == count(session, Invoice, first) == 0
        assert count(session, SourceImport, first) == 2


@pytest.mark.postgres
def test_concurrent_receipt_creation(environment):
    engine, first, _, _, _ = environment

    def upload(_):
        with Session(engine) as session:
            return ingest(
                session,
                organization_id=first,
                actor_id="tester",
                kind="bank-transactions",
                raw=csv_bytes("bank-transactions", BANK),
                source_name="test.csv",
                idempotency_key=uuid4(),
                contract_version="1.0",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload, range(2)))
    assert sorted(result["inserted"] for result in results) == [0, 1]
    with Session(engine) as session:
        assert count(session, Receipt, first) == 1


@pytest.mark.postgres
def test_database_guards(environment):
    engine, first, second, client, _ = environment
    assert post(client, "customers", CUSTOMER).status_code == 200
    assert post(client, "invoices", INVOICE).status_code == 200
    assert post(client, "bank-transactions", BANK).status_code == 200
    for table in ("audit_events", "bank_transactions", "source_imports"):
        for statement in (
            f"UPDATE {table} SET version = version + 1 WHERE organization_id = :org",
            f"DELETE FROM {table} WHERE organization_id = :org",
            f"TRUNCATE {table} CASCADE",
        ):
            with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    connection.execute(text(statement), {"org": first})
                connection.rollback()
    with Session(engine) as session:
        invoice = session.scalar(select(Invoice).where(Invoice.organization_id == first))
        invoice.organization_id = second
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        receipt = session.scalar(select(Receipt).where(Receipt.organization_id == first))
        receipt.amount_paise = 101
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        invoice = session.scalar(select(Invoice).where(Invoice.organization_id == first))
        invoice.open_amount_paise = 102
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.postgres
def test_transport_validation_and_missing_scope(environment):
    _, _, _, client, _ = environment
    assert (
        post(client, "customers", CUSTOMER, **{"X-Data-Contract-Version": "2.0"}).json()["code"]
        == "UNSUPPORTED_CONTRACT"
    )
    assert post(client, "customers", CUSTOMER, filename="../bad.csv").status_code == 422
    assert (
        post(client, "customers", CUSTOMER, **{"Content-Type": "application/json"}).status_code
        == 415
    )
    assert post(client, "customers", raw=b"x" * (MAX_BYTES + 1)).status_code == 413
    assert client.post("/imports/customers", content=b"x").status_code == 422
    assert client.get("/customers?limit=101").status_code == 422
    app = create_app(
        Settings(_env_file=None, database_url="postgresql+psycopg://unused@127.0.0.1:1/unused")
    )
    with TestClient(app) as no_scope:
        assert no_scope.get("/customers").status_code == 503


@pytest.mark.parametrize(
    "amount", ["1.0", "1e2", "-1", "+1", "01", "NaN", "", "9223372036854775808"]
)
def test_money_csv_rejection(amount):
    with pytest.raises(ImportFailure):
        parse_csv(
            "bank-transactions", csv_bytes("bank-transactions", {**BANK, "amount_paise": amount})
        )


@pytest.mark.parametrize("amount", [1.0, True])
def test_input_schema_rejects_float_and_bool(amount):
    with pytest.raises(ValueError):
        BankInput.model_validate({**BANK, "amount_paise": amount})


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "USD"},
        {"amount_paise": "0"},
        {"occurred_at": "2026-01-01"},
        {"occurred_at": "2026-01-01T00:00:00"},
        {"occurred_at": "2026-02-30T00:00:00Z"},
        {"source_system": " padded"},
        {"memo": "line\nbreak"},
    ],
)
def test_bank_validation(change):
    with pytest.raises(ImportFailure):
        parse_csv("bank-transactions", csv_bytes("bank-transactions", {**BANK, **change}))


@pytest.mark.parametrize(
    "change",
    [
        {"issued_date": "01/01/2026"},
        {"due_date": "2025-12-31"},
        {"issued_date": "2026-02-30"},
        {"open_amount_paise": "102"},
        {"original_amount_paise": "0"},
    ],
)
def test_invoice_validation(change):
    with pytest.raises(ImportFailure):
        parse_csv("invoices", csv_bytes("invoices", {**INVOICE, **change}))


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"name,name\na,b\n",
        b"external_reference,name\n",
        b"external_reference,name\nc,Test,extra\n",
        b"external_reference,name\nc,\xff",
        b'external_reference,name\nc,"unclosed',
        b"external_reference,name\n\n",
        b"organization_id,name\nx,y\n",
    ],
)
def test_csv_structure_rejection(raw):
    with pytest.raises(ImportFailure):
        parse_csv("customers", raw)


def test_bom_reordered_columns_and_quoted_text():
    rows = parse_csv("customers", '\ufeffname,external_reference\r\n"Test, quoted",c\r\n'.encode())
    assert rows[0][1].name == "Test, quoted"
    assert rows[0][1].external_reference == "c"


def test_row_limit(monkeypatch):
    monkeypatch.setattr("clearledger.imports.MAX_ROWS", 1)
    with pytest.raises(ImportFailure) as error:
        parse_csv("customers", csv_bytes("customers", CUSTOMER, CUSTOMER))
    assert error.value.code == "TOO_MANY_ROWS"


def test_alias_normalization_and_extreme_timestamp_rejection():
    with pytest.raises(ImportFailure):
        parse_csv("payer-aliases", csv_bytes("payer-aliases", {**ALIAS, "alias": "ß" * 200}))
    with pytest.raises(ImportFailure):
        parse_csv(
            "bank-transactions",
            csv_bytes("bank-transactions", {**BANK, "occurred_at": "0001-01-01T00:00:00+01:00"}),
        )


@pytest.mark.postgres
def test_rejected_replay_closed_invoice_alias_conflict_and_receipt_unique(environment):
    engine, first, _, client, other = environment
    key = uuid4()
    rejected = post(client, "customers", {**CUSTOMER, "name": ""}, key=key)
    assert rejected.status_code == 422
    assert post(client, "customers", {**CUSTOMER, "name": ""}, key=key).json() == rejected.json()
    assert post(client, "customers", CUSTOMER, key=key).status_code == 409
    assert post(client, "customers", CUSTOMER).status_code == 200
    assert post(client, "customers", {**CUSTOMER, "name": "Different"}).status_code == 409
    assert post(client, "invoices", {**INVOICE, "open_amount_paise": "0"}).status_code == 200
    assert client.get("/invoices").json()[0]["status"] == "CLOSED"
    assert post(client, "payer-aliases", ALIAS).status_code == 200
    assert post(client, "payer-aliases", ALIAS).json()["duplicates"] == 1
    assert post(client, "payer-aliases", {**ALIAS, "alias": "TEST ALIAS"}).status_code == 409
    assert post(client, "bank-transactions", BANK).status_code == 200
    # Identical external transaction identity is independent across companies.
    assert post(other, "bank-transactions", BANK).json()["receipts_created"] == 1
    with Session(engine) as session:
        original = session.scalar(select(Receipt).where(Receipt.organization_id == first))
        session.add(
            Receipt(
                organization_id=first,
                bank_transaction_id=original.bank_transaction_id,
                amount_paise=100,
                unapplied_amount_paise=100,
                currency="INR",
                status="UNAPPLIED",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.postgres
def test_concurrent_same_idempotency_key(environment):
    engine, first, _, _, _ = environment
    key = uuid4()

    def upload(_):
        with Session(engine) as session:
            return ingest(
                session,
                organization_id=first,
                actor_id="tester",
                kind="bank-transactions",
                raw=csv_bytes("bank-transactions", BANK),
                source_name="test.csv",
                idempotency_key=key,
                contract_version="1.0",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload, range(2)))
    assert results[0] == results[1]
    with Session(engine) as session:
        assert count(session, SourceImport, first) == 1
        assert count(session, Receipt, first) == 1


@pytest.mark.postgres
def test_company_provisioning_cli_is_configuration_only(environment):
    import os
    import subprocess
    import sys

    engine, _, _, _, _ = environment
    company_id = uuid4()
    env = {
        **os.environ,
        "DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "ORGANIZATION_ID": str(company_id),
    }
    arguments = [
        sys.executable,
        "-m",
        "clearledger.cli",
        "init-organization",
        "--name",
        "Test config",
    ]
    for _ in range(2):
        result = subprocess.run(arguments, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
    with Session(engine) as session:
        assert session.get(Organization, company_id).name == "Test config"
        assert count(session, Customer, company_id) == count(session, Receipt, company_id) == 0
    result = subprocess.run(
        [*arguments[:-1], "Different"], env=env, capture_output=True, timeout=15
    )
    assert result.returncode != 0
