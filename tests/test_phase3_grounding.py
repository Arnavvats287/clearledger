"""New prediction boundary and scorer arithmetic on minimal application-owned fixtures only."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from external_eval.contracts import ProviderMetadata  # noqa: E402
from external_eval.phase3 import reasoning_packet, resolve_decisions, resolve_invoice  # noqa: E402
from external_eval.scorers import GoldInvoice  # noqa: E402
from external_phase3_score import score_docile_canonical  # noqa: E402

from clearledger.source_candidates import discover  # noqa: E402
from clearledger.source_spans import text_source  # noqa: E402


def test_unknown_and_unoffered_ids_rejected_and_missing_not_contradiction():
    packet = {
        "document_id": "unit",
        "text": "Disclosure to employees is permitted.",
        "hypotheses": [{"hypothesis_id": "h1", "text": "Disclosure to employees is permitted."}],
    }
    source, payload = reasoning_packet(packet)
    identifier = source.spans[0].span_id
    row = {
        "hypothesis_id": "h1",
        "span_ids": [identifier],
        "relation": "CONFLICT",
        "predicted_label": "Contradiction",
    }
    payload["evidence_plan"] = {
        "evidence": [{k: v for k, v in row.items() if k != "predicted_label"}]
    }
    out, checks = resolve_decisions(
        {"answers": [row]}, payload, source, ProviderMetadata(provider="fake")
    )
    assert out.answers[0].predicted_label == "NotMentioned"
    assert "NO_EXPLICIT_CONFLICT" in checks["checks"][0]["reasons"]
    row["span_ids"] = ["invented"]
    with pytest.raises(ValueError, match="UNKNOWN_OR_UNOFFERED"):
        resolve_decisions({"answers": [row]}, payload, source, ProviderMetadata(provider="fake"))


def test_source_candidate_none_and_scorer_full_denominator():
    source = text_source("unit", ["Tax invoice\nInvoice no: INV-001"])
    c = discover(source)
    output, spans = resolve_invoice(
        {"document_class": "INVOICE", "candidate_ids": []},
        c,
        "unit",
        ProviderMetadata(provider="fake"),
    )
    result, native = score_docile_canonical(
        [GoldInvoice("unit", True, ("INV-001",))],
        [output],
        [{"document_id": "unit", "selected_spans": spans, "status": "SUCCESS"}],
        {"unit": {"canonical_source": asdict(source)}},
    )
    assert result["documents"] == 1 and result["invoice_id"]["fn"] == 1
    assert native == {"unit": []}


def test_worker_no_gold_product_handles_and_exact_isolated_startup(tmp_path):
    import subprocess

    from external_eval.phase3 import Decisions, InvoiceSelection, Plan
    from external_eval.source import sha256, write_json

    root = tmp_path
    directory = root / "inputs"
    packet = {
        "document_id": "unit",
        "text": "Disclosure to employees is permitted.",
        "hypotheses": [{"hypothesis_id": "h1", "text": "Disclosure to employees is permitted."}],
    }
    write_json(directory / "unit.json", packet)
    for part in ("attempts", "predictions", "logs/metadata"):
        (root / part).mkdir(parents=True)
    config = {
        "run_root": str(root),
        "pacing": {"http_interval_seconds": 0},
        "limits": {"generations": 4, "input_tokens": 200000, "output_tokens": 20000},
        "model": "gemini-3.5-flash-lite",
        "request_spec": {
            "plan_prompt": "unit",
            "plan_schema": Plan.model_json_schema(),
            "synthesis_prompt": "unit",
            "synthesis_schema": Decisions.model_json_schema(),
            "extraction_prompt": "unit",
            "extraction_schema": InvoiceSelection.model_json_schema(),
        },
        "phases": {
            "unit": {
                "dataset": "contract-nli",
                "ids": ["unit"],
                "input_directory": str(directory),
                "packet_hashes": {"unit.json": sha256(directory / "unit.json")},
            }
        },
    }
    path = root / "config.json"
    write_json(path, config)
    path.with_suffix(".sha256").write_text(sha256(path))
    script = """
import sys,json
sys.path.insert(0,'scripts')
import external_gemini_worker as base
class Fake:
    def __init__(self,key):pass
    def close(self):pass
    def request(self,operation,body):
        if operation=='countTokens':return {'totalTokens':10}
        packet=json.loads(body['contents'][0]['parts'][0]['text'])
        s=packet['source_spans'][0]['span_id']
        row={'hypothesis_id':'h1','span_ids':[s],'relation':'SUPPORT'}
        if 'evidence_plan' in packet:row['predicted_label']='Entailment';value={'answers':[row]}
        else:value={'evidence':[row]}
        candidate={'finishReason':'STOP','content':{'parts':[{'text':json.dumps(value)}]}}
        return {'candidates':[candidate],
                'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':10,'totalTokenCount':20}}
base.GeminiHTTP=Fake
from external_phase3_worker import main
main()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        input=json.dumps({"key": "unit-not-secret", "config_path": str(path), "phases": ["unit"]}),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads((root / "predictions/unit.jsonl").read_text())
    assert output["answers"][0]["predicted_label"] == "Entailment"
    assert "unit-not-secret" not in result.stdout + result.stderr


def test_product_isolated_worker_resolves_ids_before_returning_legacy_fact_schema():
    import subprocess

    script = """
import json
from types import SimpleNamespace as N
from google import genai
class Fake:
    def __init__(self,**kwargs):self.models=self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def get(self,**kwargs):return N(name='models/unit',supported_actions=['generateContent'],
        input_token_limit=100000,output_token_limit=4096,version='offline')
    def count_tokens(self,**kwargs):return N(total_tokens=100)
    def generate_content(self,**kwargs):
        p=json.loads(kwargs['contents'])
        assert 'start' not in kwargs['config'].response_json_schema['properties']
        c=next(c for c in p['invoice_candidates'] if c['value']=='I-1')
        description=next(s for s in p['source_spans'] if 'deduction' in s['text'])
        amount=next(s for s in p['source_spans'] if s['text']=='INR 1.01')
        v={'invoice_candidate_ids':[c['candidate_id']],'utr_span_ids':[],
           'payer_span_id':None,'claims':[{'category':'damage','description_span_id':description['span_id'],
           'amount_paise':101,'amount_span_id':amount['span_id'],'reason_code_span_id':None}],
           'uncertainty':'review','unparsed_span_ids':[]}
        usage=N(prompt_token_count=100,candidates_token_count=100,
            total_token_count=200,thoughts_token_count=None,cached_content_token_count=None)
        return N(text=json.dumps(v),usage_metadata=usage)
genai.Client=Fake
from clearledger.gemini_worker import main
main()
"""
    body = {
        "key": "unit-never-live",
        "model": "unit",
        "timeout_ms": 1000,
        "pages": ["Invoice I-1 payment includes a disputed damage deduction of INR 1.01."],
        "task": "remittance_grounded",
        "max_input_tokens": 8192,
        "max_output_tokens": 512,
        "source_context": {
            "source_id": "company/document",
            "source_hash": "a" * 64,
            "version": "2",
        },
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        input=json.dumps(body),
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    output = json.loads(result.stdout)
    assert "error" not in output, output
    facts = json.loads(output["json_text"])
    assert facts["claims"][0]["amount_paise"] == 101
    assert facts["claims"][0]["reason_code"] is None
    assert output["grounding"]["selected_span_ids"]
    assert not output["grounding"]["financial_authority"]
    assert "unit-never-live" not in result.stdout + result.stderr
