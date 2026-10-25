"""Supplemental public-source probes only; no answer keys or semantic model calls."""

import hashlib
import json
from pathlib import PurePosixPath
from uuid import uuid4


def structured_remittances(api, visible, records):
    additions = json.loads(visible.read("app_visible/COMPATIBILITY_ADDITIONS.json"))
    banks = {row["id"]: row for row in records["bank-transactions"]}
    observations = {}
    for entry in additions["documents"]:
        raw = visible.read("app_visible/" + entry["source_path"])
        assert hashlib.sha256(raw).hexdigest() == entry["source_sha256"]
        source = json.loads(raw)
        headers = {
            "Content-Type": "application/json",
            "X-Source-Filename": PurePosixPath(entry["source_path"]).name,
            "X-Synthetic-Data": "true",
        }
        doc = api.request("POST", "/documents", headers=headers, content=raw).json()
        duplicate = api.request("POST", "/documents", headers=headers, content=raw).json()
        assert duplicate == doc and doc["parse_status"] == "READY"
        assert api.request("GET", f"/documents/{doc['id']}/original").content == raw
        canonical = api.get(f"/documents/{doc['id']}/text")
        extraction = api.request(
            "POST",
            f"/documents/{doc['id']}/extract",
            json={"expected_document_version": doc["version"], "allow_external": False},
        ).json()
        assert extraction["route"] == "DETERMINISTIC" and extraction["status"] == "SUCCEEDED"
        assert extraction["financial_authority"] is False and extraction["requires_human_review"]
        facts = extraction["result"]
        verified_spans = 0
        for kind in ("invoice_references", "utr_references"):
            assert [item["value"] for item in facts[kind]] == source[kind]
            for item in facts[kind]:
                result = api.request(
                    "POST", f"/documents/{doc['id']}/verify-span", json=item["span"]
                ).json()
                assert result["source_consistent"] and not result["financial_authority"]
                verified_spans += 1
        assert facts["payer_hint"] == source["payer_hint"] is None
        assert facts["claims"] == source["claims"] == []
        path = f"/documents/{doc['id']}/correlate"
        base = {"extraction_id": extraction["id"], "expected_document_version": doc["version"]}
        unattested = api.request("POST", path, json=base).json()
        assert unattested["status"] != "LINKED"
        utrs = sorted({item["value"] for item in facts["utr_references"]})
        versions = {
            row["id"]: row["version"]
            for row in records["receipts"]
            if banks[row["bank_transaction_id"]]["external_transaction_id"] in utrs
        }
        # Uniform, explicitly simulated operator attestation of extracted literals,
        # never targets, scenario names or expected decisions from hidden answers.
        body = {**base, "verified_utr_values": utrs, "expected_receipt_versions": versions}
        key = uuid4()
        attested = api.request("POST", path, key=key, json=body).json()
        for replay_key in (key, uuid4()):
            assert api.request("POST", path, key=replay_key, json=body).json() == attested
        api.request(
            "POST",
            path,
            expected=422,
            json={**body, "verified_utr_values": ["not-present-in-source"]},
        )
        if attested["status"] == "LINKED":
            assert attested["receipt_id"] in versions
            api.request("POST", path, expected=409, json={**body, "expected_receipt_versions": {}})
        if versions:
            api.request(
                "POST",
                path,
                expected=409,
                json={
                    **body,
                    "expected_receipt_versions": {
                        key: value + 1 for key, value in versions.items()
                    },
                },
            )
        assert attested["result"]["financial_authority"] is False
        observations[PurePosixPath(entry["source_path"]).name] = {
            "inventory": entry,
            "document": doc,
            "canonical": canonical,
            "extraction": extraction,
            "unattested": unattested,
            "simulated_utr_attested": attested,
            "verified_spans": verified_spans,
            "stale_version_probed": bool(versions),
            "missing_version_probed": attested["status"] == "LINKED",
        }
    return observations
