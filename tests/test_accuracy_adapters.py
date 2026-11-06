"""Application-owned fixtures for request aliases and independent task policies."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from external_eval.accuracy_nli import evidence_items, packet, validate  # noqa: E402

from clearledger.document_contract import validate_semantics
from clearledger.grounded_extraction import RemittanceSelection, catalog, payload, resolve_selection
from clearledger.source_aliases import aliases
from clearledger.source_invoice_candidates import candidates, compact
from clearledger.source_presentations import remittance_packet, remittance_selection
from clearledger.source_retrieval import assertion_gate
from clearledger.source_semantics import rank, semantic_source
from clearledger.source_spans import GroundingError, Page, Token, build, text_source


def fixture(n=17, strategy="global"):
    s = semantic_source(
        text_source(
            "unit",
            [
                "RECORD RETENTION\nArchival duplicates may be kept.\n"
                "DELIVERY\nSigned delivery proof is absent."
            ],
        )
    )
    hs = [{"hypothesis_id": f"H{i:02}", "text": "Copies can be retained."} for i in range(n)]
    p = packet(s, hs, request="unit", strategy=strategy, k=1)
    a = p.registry.bindings[0].alias
    rows = [
        dict(
            hypothesis_id=h["hypothesis_id"],
            predicted_label="Entailment",
            aliases=[a],
            relation="SUPPORT",
            contradiction_basis="NONE",
        )
        for h in hs
    ]
    return p, rows


@pytest.mark.parametrize("failure", ["alias", "extra", "missing", "duplicate", "type"])
def test_one_bad_hypothesis_preserves_other_sixteen(failure):
    p, rows = fixture()
    if failure == "alias":
        rows[7]["aliases"] = ["E999"]
    elif failure == "extra":
        rows[7]["invented"] = True
    elif failure == "missing":
        rows.pop(7)
    elif failure == "duplicate":
        rows.append(dict(rows[7]))
    else:
        rows[7]["aliases"] = "E01"
    out = validate({"answers": rows}, p)
    assert sum(x.grounded_label == "Entailment" for x in out) == 16
    assert out[7].grounded_label == "Abstain"
    assert all(x.grounded_label == "Entailment" for i, x in enumerate(out) if i != 7)


def test_legal_paraphrase_not_vetoed_but_financial_exact_checks_unchanged():
    p, rows = fixture(1)
    result = validate({"answers": rows}, p)[0]
    assert result.grounded_label == "Entailment"
    s = p.catalog.source
    assert not assertion_gate(
        s,
        [p.registry.resolve(rows[0]["aliases"][0], scope=p.registry.scope).span_id],
        "Invoice INV-002 has 101 paise damage",
        source_hash=s.source_hash,
        source_version=s.source_version,
        relation="SUPPORT",
        required_atoms=("INV-002", "101"),
    ).admitted
    assert result.canonical_ids


@pytest.mark.parametrize(
    "basis,refs,expected",
    [
        ("NONE", True, "Abstain"),
        ("EXPLICIT_INCOMPATIBILITY", False, "Abstain"),
        ("EXPLICIT_INCOMPATIBILITY", True, "Contradiction"),
    ],
)
def test_explicit_conflict_needs_evidence_not_absence(basis, refs, expected):
    p, rows = fixture(1)
    rows[0].update(predicted_label="Contradiction", relation="CONFLICT", contradiction_basis=basis)
    if not refs:
        rows[0]["aliases"] = []
    assert validate({"answers": rows}, p)[0].grounded_label == expected


def test_plan_failure_is_local_and_not_mentioned_needs_no_positive_proof():
    p, rows = fixture()
    plan = [
        {k: v for k, v in x.items() if k in ("hypothesis_id", "aliases", "relation")} for x in rows
    ]
    plan[7]["aliases"] = ["E999"]
    good, errors = evidence_items({"evidence": plan}, p)
    assert set(errors) == {"H07"}
    out = validate({"answers": rows}, p, plan=good, require_plan=True)
    assert sum(x.grounded_label == "Entailment" for x in out) == 16
    rows[7].update(predicted_label="NotMentioned", relation="NONE", aliases=[])
    assert validate({"answers": rows}, p)[7].grounded_label == "NotMentioned"


def test_alias_collisions_staleness_and_request_scope():
    s = text_source("a", ["Repeated.\nRepeated."])
    a = aliases((s,), list(s.spans), request="r")
    assert a.bindings[0].alias != a.bindings[1].alias
    assert a.resolve("E02", scope=a.scope).start != a.resolve("E01", scope=a.scope).start
    with pytest.raises(GroundingError, match="COLLISION"):
        aliases((s,), [s.spans[0], s.spans[0]], request="r")
    with pytest.raises(GroundingError, match="MISMATCH"):
        a.resolve("E01", scope="wrong")
    with pytest.raises(GroundingError, match="STALE"):
        a.resolve("E01", scope=a.scope, current=(replace(s, source_hash="0" * 64),))
    with pytest.raises(GroundingError, match="SCOPE"):
        a.resolve("E01", scope=a.scope, current=(replace(s, source_id="other"),))


def test_real_document_global_evidence_does_not_require_top_k_membership():
    p, rows = fixture(1)
    aliases_all = {b.alias for b in p.registry.bindings}
    other = next(
        a for a in aliases_all if "Archival" in p.registry.resolve(a, scope=p.registry.scope).text
    )
    wrong = next(a for a in aliases_all if a != other)
    p = replace(p, primary={"H00": (wrong,)})
    rows[0]["aliases"] = [other]
    assert validate({"answers": rows}, p)[0].status == "VALID_ENTAILMENT"
    local = replace(p, selectable=p.primary)
    out = validate({"answers": rows}, local)[0]
    assert out.status == "INVALID_EVIDENCE" and out.reason == "SOURCE_VALID_OUTSIDE_SELECTABLE_POOL"


def test_sentence_list_definition_offsets_and_retrieval():
    s = semantic_source(
        text_source(
            "unit",
            [
                "CONFIDENTIALITY\nThe recipient must safeguard information; "
                "It must not disclose it.\nRETENTION\nArchival copies may survive termination."
            ],
        )
    )
    assert all(
        s.source.resolve(
            x.span_id, expected_hash=s.source.source_hash, expected_version=s.source.source_version
        ).text
        == x.text
        for x in s.source.spans
    )
    assert any("RETENTION" == h for _, h in s.sections)
    assert "Archival" in rank(s, "Can copies be retained after termination?", limit=1)[0].text
    assert "".join(x.text for x in s.source.spans) == s.source.pages[0].text


def test_compressed_candidate_occurrence_geometry_and_split_join():
    text = "Invoice No: INV - 1001\nReference INV-1001"
    tokens = (
        Token("a", 0, 7, (0.1, 0.1, 0.2, 0.2)),
        Token("b", 8, 11, (0.21, 0.1, 0.25, 0.2)),
        Token("c", 12, 15, (0.3, 0.1, 0.4, 0.2)),
        Token("d", 16, 17, (0.41, 0.1, 0.42, 0.2)),
        Token("e", 18, 22, (0.43, 0.1, 0.5, 0.2)),
    )
    s = build("unit", (Page(1, text, tokens),), source_hash="0" * 64)
    c = candidates(s)
    joined = [x for x in c.items if x.value == "INV-1001"]
    assert len({x.span_id for x in joined}) >= 2
    first = next(x for x in joined if x.reason == "PUNCTUATION_JOIN")
    exact = c.source.resolve(first.span_id, expected_hash=s.source_hash, expected_version="1")
    assert exact.text == "INV - 1001" and exact.bbox == (0.3, 0.1, 0.5, 0.2)
    body, lookup = compact(c)
    assert all(not alias.startswith(("sp_", "ca_")) for alias in lookup)
    assert body["complete"] is True


def test_remittance_aliases_resolve_before_unchanged_financial_validation():
    c = catalog(["Invoice I-1 has a disputed damage deduction of INR 1.01."])
    public, book = remittance_packet(payload(c))
    inv = next(x for x in public["invoice_candidates"] if x["value"] == "I-1")
    desc = next(x for x in public["source_spans"] if "deduction" in x["text"])
    money = next(x for x in public["source_spans"] if x["text"] == "INR 1.01")
    model = {
        "invoice_candidate_ids": [inv["candidate_id"]],
        "utr_span_ids": [],
        "claims": [
            {
                "category": "damage",
                "description_span_id": desc["span_id"],
                "amount_paise": 101,
                "amount_span_id": money["span_id"],
                "reason_code_span_id": None,
            }
        ],
        "uncertainty": "review",
        "unparsed_span_ids": [],
    }
    result = resolve_selection(
        RemittanceSelection.model_validate(remittance_selection(model, book)), c
    )
    validate_semantics(result, [c.source.pages[0].text])
    assert result.claims[0].amount_paise == 101
    model["invoice_candidate_ids"] = ["C999"]
    with pytest.raises(GroundingError, match="UNKNOWN_ALIAS"):
        remittance_selection(model, book)


def test_retrieval_coverage_and_oracle_ranges_are_exact_source_intervals():
    from accuracy_development import coverage

    from clearledger.source_spans import make_span

    total, found, complete = coverage([(2, 8), (10, 12)], [(0, 6), (6, 9), (10, 12)])
    assert (total, found, complete) == (8, 8, True)
    s = text_source("oracle", ["An obligation survives. Other facts."])
    span = make_span(s, 1, 0, 22, 0)
    assert span.text == s.pages[0].text[:22]
    assert coverage([(0, 22)], [(span.start, span.end)]) == (22, 22, True)


def test_inline_provider_schema_preserves_strict_constraints():
    from external_eval.accuracy_nli import DecisionResponse, inline_schema

    original = DecisionResponse.model_json_schema()
    expanded = inline_schema(original)
    assert "$defs" not in expanded
    assert expanded["properties"]["answers"]["items"] == original["$defs"]["DecisionRow"]
    assert expanded["additionalProperties"] is False
    assert expanded["properties"]["answers"]["maxItems"] == 17


def test_provider_diagnostic_does_not_retain_message_or_sensitive_paths():
    from accuracy_worker import DevelopmentWorker

    class Response:
        status_code = 400

        def read(self):
            return b""

        def json(self):
            return {
                "error": {
                    "message": "schema too complex PRIVATE_TEXT secret-key-value",
                    "details": [
                        {
                            "fieldViolations": [
                                {
                                    "field": "generation_config.response_schema",
                                    "description": "PRIVATE_TEXT",
                                },
                                {"field": "https://sensitive.example/key"},
                            ]
                        }
                    ],
                }
            }

    worker = object.__new__(DevelopmentWorker)
    worker.safe_error(Response())
    assert worker.provider_diagnostic == {
        "reason": "SCHEMA_COMPLEXITY",
        "http_status": 400,
        "field_paths": ["generation_config.response_schema"],
    }


@pytest.mark.parametrize("kind", ["contract", "invoice"])
def test_new_worker_exact_isolated_startup_item_rejection_and_gold_boundary(tmp_path, kind):
    import json
    import subprocess

    from external_eval.source import sha256, write_json

    root = tmp_path
    inp = root / "inputs/unit.json"
    write_json(
        inp,
        {
            "document_id": "unit",
            "text": "Records may be retained.",
            "hypotheses": [
                {"hypothesis_id": f"H{i:02}", "text": "Copies can be kept."} for i in range(17)
            ],
        },
    )
    job = {
        "job_id": "unit",
        "variant": "unit",
        "kind": "contract",
        "mode": "direct",
        "strategy": "global",
        "k": 5,
        "input": "inputs/unit.json",
        "input_sha256": sha256(inp),
        "hypotheses": [f"H{i:02}" for i in range(17)],
    }
    for folder in ("predictions", "attempts", "logs/metadata"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    cfg = {
        "run_root": str(root),
        "pacing": {"http_interval_seconds": 0},
        "limits": {"generations": 1, "input_tokens": 32768, "output_tokens": 4096},
        "model": "gemini-3.5-flash-lite",
        "jobs": [job],
    }
    if kind == "invoice":
        import dataclasses

        inp.write_text(
            json.dumps(
                {
                    "document_id": "unit",
                    "canonical_source": dataclasses.asdict(
                        text_source("unit", ["Tax invoice\nInvoice no: INV-1001"])
                    ),
                }
            )
        )
        job["kind"] = "invoice"
        job["input_sha256"] = sha256(inp)
    path = root / "config.json"
    write_json(path, cfg)
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
        if 'candidates' in packet:
            c=next(c[0] for c in packet['candidates'] if c[1]=='INV-1001')
            value={'document_class':'INVOICE','candidate_ids':[c,'C999']}
            answer={'finishReason':'STOP','content':{'parts':[{'text':json.dumps(value)}]}}
            return {'candidates':[answer],
                    'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':10,'totalTokenCount':20}}
        alias=packet['evidence'][0]['alias']
        rows=[{'hypothesis_id':h['hypothesis_id'],'predicted_label':'Entailment',
               'aliases':[alias],'relation':'SUPPORT','contradiction_basis':'NONE'}
              for h in packet['hypotheses']]
        rows[7]['aliases']=['E999']
        answer={'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'answers':rows})}]}}
        return {'candidates':[answer],
                'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':10,'totalTokenCount':20}}
base.GeminiHTTP=Fake
from accuracy_worker import main
main()
"""
    out = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        input=json.dumps({"key": "unit-not-real", "config_path": str(path)}),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    saved = json.loads((root / "predictions/unit.json").read_text())
    if kind == "invoice":
        assert saved["output"]["invoice_references"][0]["value"] == "INV-1001"
        assert saved["diagnostics"]["invalid_aliases"] == 1
        return
    answers = saved["output"]["answers"]
    assert sum(a["predicted_label"] == "Entailment" for a in answers) == 16
    assert saved["diagnostics"]["items"][7]["status"] == "INVALID_ALIAS"
    assert "unit-not-real" not in out.stdout + out.stderr
