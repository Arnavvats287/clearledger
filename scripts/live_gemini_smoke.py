"""Explicitly authorized synthetic-only smoke; never part of pytest/CI or a benchmark.

Requires fresh operator quota confirmation and current reviewed official prices.
No billing settings are modified. Configuration is process-local and disabled in finally.
"""

import argparse
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from application_eval_host import initialize  # noqa: E402
from pilot_runtime import disposable_database, fingerprint, rows  # noqa: E402
from test_ai_usefulness import SMOKE  # noqa: E402
from test_documents import TOKEN, auth, extract, get, upload  # noqa: E402
from test_matching import setup  # noqa: E402

from clearledger.config import Settings  # noqa: E402
from clearledger.document_contract import Extraction, validate_semantics  # noqa: E402
from clearledger.document_privacy import project  # noqa: E402
from clearledger.extraction_provider import decode_output  # noqa: E402
from clearledger.main import create_app  # noqa: E402
from clearledger.models import ProviderReservation  # noqa: E402
from clearledger.provider_diagnostics import diagnostic  # noqa: E402


def schema_diagnostics(text):
    """Fixed schema categories/paths only; no generated values, error text or URLs."""
    known = {
        "invoice_references",
        "utr_references",
        "payer_hint",
        "claims",
        "uncertainty",
        "unparsed_fields",
        "value",
        "span",
        "page",
        "start",
        "end",
        "quote",
        "category",
        "description",
        "amount_paise",
        "amount_span",
        "reason_code",
    }
    codes = {
        "missing",
        "extra_forbidden",
        "int_type",
        "string_type",
        "list_type",
        "model_type",
        "dict_type",
        "literal_error",
        "greater_than_equal",
        "less_than_equal",
        "value_error",
    }
    try:
        Extraction.model_validate(decode_output(text))
    except ValidationError as error:
        return [
            {
                "code": row["type"] if row["type"] in codes else "VALIDATION",
                "path": [
                    part if type(part) is int or part in known else "UNKNOWN" for part in row["loc"]
                ],
            }
            for row in error.errors(include_input=False, include_context=False, include_url=False)[
                :30
            ]
        ]
    except Exception:
        return [{"code": "DECODE", "path": []}]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-live", action="store_true")
    parser.add_argument("--confirmed-rpm", type=int, required=True)
    parser.add_argument("--confirmed-tpm", type=int, required=True)
    parser.add_argument("--remaining-rpd", type=int, required=True)
    parser.add_argument(
        "--model",
        choices=["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
        default="gemini-3.1-flash-lite",
    )
    parser.add_argument("--remaining-budget-paise", type=int)
    args = parser.parse_args()
    # Prices must be re-reviewed on a different day, not blindly replayed later.
    if not args.authorized_live or date.today() != date(2026, 10, 27):
        raise SystemExit("Explicit live authorization/current pricing review required")
    if args.confirmed_rpm < 3 or args.confirmed_tpm < 2048 or args.remaining_rpd < 4:
        raise SystemExit("Confirmed project quotas insufficient")
    alternate = args.model == "gemini-3.5-flash-lite"
    attempt_cost = 26 if alternate else 17
    remaining_budget = args.remaining_budget_paise if alternate else 66
    if alternate and (
        type(remaining_budget) is not int or not attempt_cost <= remaining_budget <= 398
    ):
        raise SystemExit("Explicit remaining alternative-model budget required")
    logging.disable(logging.CRITICAL)
    local = dotenv_values(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY") or local.get("GEMINI_API_KEY")
    admin = os.environ.get("TEST_DATABASE_URL") or local.get("TEST_DATABASE_URL")
    if not key or not admin:
        raise SystemExit("Local key and disposable-database connection required")
    output = ROOT / "local-data/live-gemini" / uuid4().hex
    output.mkdir(parents=True)
    report = {
        "provider": "gemini",
        "model": args.model,
        "cases": [],
        "attempt_cost_cap_paise": attempt_cost,
        "remaining_authorized_cap_paise": remaining_budget,
        "maximum_attempts": 1,
        "maximum_reserved_paise": attempt_cost,
        "billing_changes": False,
        "operator_confirmed_quotas": vars(args),
    }
    settings = None
    engine = None
    try:
        with httpx.Client(trust_env=False, timeout=15) as client:
            response = client.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
            response.raise_for_status()
        dated = next(x for x in ET.fromstring(response.content).iter() if "time" in x.attrib)
        rates = {x.attrib["currency"]: Decimal(x.attrib["rate"]) for x in dated}
        fx = rates["INR"] / rates["USD"]
        if not 0 <= (date.today() - date.fromisoformat(dated.attrib["time"])).days <= 4 or fx > 110:
            raise ValueError("FX_GATE_FAILED")
        report.update(
            fx_date=dated.attrib["time"],
            inr_per_usd=str(fx),
            conservative_inr_per_usd=110,
            contingency_percent=20,
        )
        from google import genai
        from google.genai import errors, types

        with genai.Client(
            api_key=key,
            vertexai=False,
            http_options=types.HttpOptions(
                timeout=10000,
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"trust_env": False},
            ),
        ) as client:
            try:
                info = client.models.get(model=report["model"])
            except errors.APIError as error:
                report["preflight_diagnostic"] = diagnostic(
                    "MODEL_LOOKUP", "HTTP_API", error.code, getattr(error, "status", None)
                )
                raise
        if info.name != f"models/{args.model}" or "generateContent" not in (
            info.supported_actions or []
        ):
            raise ValueError("MODEL_GATE_FAILED")
        if info.input_token_limit < 2048 or info.output_token_limit < 512:
            raise ValueError("MODEL_LIMIT_GATE_FAILED")
        report["model_metadata_verified"] = True
        # This standalone metadata call plus any transport calls stay below15 RPM.
        # Subsequent attempts are separated by61s; one caller and no retry.
        with disposable_database(admin) as url:
            engine, org, _unused_password = initialize(url)
            settings = Settings(
                _env_file=None,
                database_url=url,
                organization_id=org,
                document_root=output / "originals",
                document_api_token=SecretStr(TOKEN),
                review_demo_enabled=False,
                review_access_enabled=False,
                extraction_provider="gemini",
                external_ai_enabled=True,
                privacy_review_reference="authorized-synthetic-prose-review-2026-10-27",
                gemini_api_key=SecretStr(key),
                gemini_model=report["model"],
                investigation_provider="deterministic",
                investigation_external_enabled=False,
                llm_attempts=1,
                llm_timeout_ms=30000,
                llm_requests_per_minute=1,
                llm_shared_requests_per_minute=3,
                llm_daily_requests=3,
                llm_max_input_tokens=2048,
                llm_max_output_tokens=512,
                llm_daily_input_tokens=2048,
                llm_daily_output_tokens=512,
                llm_input_paise_per_million_tokens=3960 if alternate else 3300,
                llm_output_paise_per_million_tokens=33000 if alternate else 19800,
                llm_max_cost_paise_per_attempt=attempt_cost,
            )
            app = create_app(settings)
            assert app.state.finance_identity_verifier is None
            if alternate:
                original_transport = app.state.extraction_gateway.transport

                class ObservedTransport:
                    def generate(self, pages):
                        reply = original_transport.generate(pages)
                        report.setdefault("schema_diagnostics", []).append(
                            schema_diagnostics(reply.json_text)
                        )
                        return reply  # Unchanged actual provider output; no repair or fake facts.

                app.state.extraction_gateway.transport = ObservedTransport()
            try:
                with TestClient(app) as api:
                    setup(api)
                    before = fingerprint(rows(engine))
                    selected = [next(row for row in SMOKE if row[0] == name) for name in ("prose",)]
                    for index, (name, raw, mime, suffix, reference, _) in enumerate(selected):
                        if index:
                            time.sleep(61)
                        pages = [raw.decode()]
                        projection = project(pages).pages
                        observation = {"fixture": name, "privacy_projected_pages": projection}
                        report["cases"].append(observation)
                        with Session(engine) as session:
                            used = session.query(ProviderReservation).count()
                        if used >= 1 or (used + 1) * attempt_cost > remaining_budget:
                            raise ValueError("EXPERIMENT_BUDGET_GATE")
                        doc_response = upload(api, raw, name=f"unit-{name}.{suffix}", mime=mime)
                        assert doc_response.status_code == 200
                        doc = doc_response.json()
                        assert get(api, f"/documents/{doc['id']}/text").json()["pages"] == pages
                        baseline = extract(api, doc["id"]).json()
                        observation["deterministic"] = baseline
                        started = time.perf_counter_ns()
                        actual_response = extract(api, doc["id"], allow_external=True)
                        observation["elapsed_ns"] = time.perf_counter_ns() - started
                        observation["http_status"] = actual_response.status_code
                        assert actual_response.status_code == 200
                        actual = actual_response.json()
                        observation["live"] = actual
                        assert not actual["financial_authority"] and actual["requires_human_review"]
                        assert fingerprint(rows(engine)) == before
                        observation["financial_nonmutation"] = True
                        (output / "observations.json").write_text(
                            json.dumps(report, indent=2), encoding="utf-8"
                        )
                        print(f"Live fixture {index + 1}: {actual['status']}", flush=True)
                        if not actual["result"] or actual["status"] not in {
                            "SUCCEEDED",
                            "NEEDS_REVIEW",
                        }:
                            report["stopped"] = "EXTRACTION_FAILED_OR_ABSTAINED"
                            break
                        parsed = Extraction.model_validate(actual["result"])
                        validate_semantics(parsed, pages)
                        expected_amount = None if name == "missing_amount" else 101
                        correct = (
                            [r.value for r in parsed.invoice_references] == [reference]
                            and not parsed.utr_references
                            and parsed.payer_hint is None
                            and (
                                not parsed.claims
                                if name == "injection"
                                else len(parsed.claims) == 1
                                and parsed.claims[0].amount_paise == expected_amount
                                and parsed.claims[0].category
                                == ("rebate" if name == "conditional" else "damage")
                                and parsed.claims[0].reason_code is None
                            )
                        )
                        observation["expected_fields_correct"] = correct
                        for pointer in (
                            [r.span for r in parsed.invoice_references]
                            + [c.description for c in parsed.claims]
                            + [c.amount_span for c in parsed.claims if c.amount_span is not None]
                        ):
                            verified = api.post(
                                f"/documents/{doc['id']}/verify-span",
                                headers=auth(),
                                json=pointer.model_dump(mode="json"),
                            )
                            assert verified.status_code == 200
                            assert verified.json()["source_consistent"]
                        persisted = get(api, f"/documents/{doc['id']}/extractions")
                        assert persisted.status_code == 200
                        assert any(
                            row["id"] == actual["id"] and row["result"] == actual["result"]
                            for row in persisted.json()
                        )
                        observation["source_spans_verified"] = True
                        observation["facts_persisted"] = True
                        if not correct or name == "injection":
                            report["stopped"] = "FIELDS_INCORRECT_OR_FINAL_CONTROL"
                            break
            finally:
                settings.external_ai_enabled = False
                settings.extraction_provider = "disabled"
                settings.investigation_external_enabled = False
                settings.gemini_api_key = None
                app.state.extraction_gateway = None
                engine.dispose()
                engine = None
            report["disposable_database_cleaned"] = True
    except Exception as exc:
        # No exception body, HTTP headers, connection URL or raw model output in logs.
        report["failure_type"] = type(exc).__name__
        print("Live smoke stopped:", type(exc).__name__, flush=True)
    finally:
        if engine is not None:
            engine.dispose()
        if settings is not None:
            settings.external_ai_enabled = False
            settings.extraction_provider = "disabled"
            settings.gemini_api_key = None
        report["external_settings_disabled"] = True
        (output / "observations.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Sanitized synthetic observations:", output, flush=True)
    return (
        0
        if "failure_type" not in report
        and report["cases"]
        and all(row.get("expected_fields_correct", False) for row in report["cases"])
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
