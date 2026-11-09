"""Freeze and run the additive TRAIN/DEV contradiction experiment."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from external_eval.accuracy_nli import packet
from external_eval.contracts import ContractPacket
from external_eval.contradiction import RUBRIC, VARIANT_INSTRUCTIONS, VARIANTS, decision, schema
from external_eval.gemini_http import MODEL
from external_eval.source import load_json, sha256, write_json
from external_phase2 import key

from clearledger.source_semantics import semantic_source
from clearledger.source_spans import digest, text_source

ROOT = Path(__file__).resolve().parents[1]
TRAIN_SHA256 = "dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5"
NEGATION = re.compile(r"\b(?:shall|may|must|will|does|do)\s+not\b|\bprohibit\w*\b", re.I)
EXCEPTION = re.compile(r"\b(?:except|unless|provided that|other than|only if)\b", re.I)


def lexical(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{5,}", text.lower()))


def demonstrations(
    train: Path, excluded: set[str], excluded_texts: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if train.name != "train.json" or sha256(train) != TRAIN_SHA256:
        raise ValueError("UNVERIFIED_TRAIN_SOURCE")
    dataset = load_json(train)
    choices: dict[str, list[tuple[str, dict[str, Any], dict[str, Any]]]] = {}
    for doc in dataset["documents"]:
        identifier, text = str(doc["id"]), doc["text"]
        if identifier in excluded or digest(text) in excluded_texts:
            continue
        if len(doc["annotation_sets"]) != 1:
            continue
        snippets = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if 70 <= len(s.strip()) <= 350
        ]
        for h, annotation in doc["annotation_sets"][0]["annotations"].items():
            hypothesis = dataset["labels"][h]["hypothesis"]
            label = annotation["choice"]
            intervals = [tuple(doc["spans"][i]) for i in annotation["spans"]]
            source = [text[a:b] for a, b in intervals]
            if any(not 0 <= a < b <= len(text) for a, b in intervals):
                raise ValueError("INVALID_TRAIN_EVIDENCE_RANGE")
            if label == "NotMentioned":
                terms = lexical(hypothesis)
                for category, minimum, maximum in (("absence", 0, 0), ("lexical-overlap", 3, 100)):
                    match = next(
                        (s for s in snippets if minimum <= len(lexical(s) & terms) <= maximum), None
                    )
                    if match:
                        add_example(choices, category, identifier, h, hypothesis, label, [match])
            elif source and sum(map(len, source)) <= 900:
                joined = " ".join(source)
                if label == "Entailment":
                    add_example(choices, "entailment", identifier, h, hypothesis, label, source)
                elif label == "Contradiction":
                    if NEGATION.search(joined):
                        add_example(choices, "negation", identifier, h, hypothesis, label, source)
                    if EXCEPTION.search(joined):
                        add_example(choices, "exception", identifier, h, hypothesis, label, source)
    examples, manifest = [], []
    seen = set(excluded)
    for category in ("entailment", "negation", "exception", "absence", "lexical-overlap"):
        eligible = sorted(choices.get(category, []), key=lambda row: row[0])
        chosen = next((row for row in eligible if row[2]["document_id"] not in seen), None)
        if chosen is None:
            raise ValueError("MISSING_TRAIN_DEMONSTRATION_CATEGORY")
        _, example, identity = chosen
        seen.add(identity["document_id"])
        examples.append(example)
        manifest.append(identity)
    return examples, manifest


def add_example(
    choices: dict[str, list[tuple[str, dict[str, Any], dict[str, Any]]]],
    category: str,
    identifier: str,
    hypothesis_id: str,
    hypothesis: str,
    label: str,
    source: list[str],
) -> None:
    refs = [f"DEMO{i + 1}" for i in range(len(source))]
    identity = {"document_id": identifier, "hypothesis_id": hypothesis_id, "category": category}
    example = {
        "hypothesis": hypothesis,
        "source": dict(zip(refs, source, strict=True)),
        "answer": decision("DEMO-H", label, refs if label != "NotMentioned" else []),
    }
    choices.setdefault(category, []).append(
        (digest(["contradiction-v1", identity]), example, identity)
    )


def prepare(prior: Path, train: Path, root: Path) -> None:
    seal = load_json(prior / "development-seal.json")
    if seal["scope"] != "TRAIN_DEV_ONLY" or any(
        sha256(prior / f) != h for f, h in seal["files"].items()
    ):
        raise ValueError("PRIOR_DEVELOPMENT_SEAL_CHANGED")
    baseline = prior / "baseline"
    reference = load_json(baseline / "config/campaign.json")
    jobs = [j for j in reference["jobs"] if j["variant"] == f"nli-global-minimal-{j['split']}"]
    if [sum(j["split"] == s for j in jobs) for s in ("dev", "train")] != [3, 8] or len(jobs) != 11:
        raise ValueError("REFERENCE_COHORT_CHANGED")
    excluded, excluded_texts = set(), set()
    sanity_rows = []
    packets = []
    for job in jobs:
        path = Path(job["input"])
        if path.parent != Path("inputs/contract") or not path.name.startswith(job["split"] + "-"):
            raise ValueError("REFERENCE_PACKET_SCOPE")
        if sha256(baseline / path) != job["input_sha256"] or len(job["hypotheses"]) != 17:
            raise ValueError("REFERENCE_PACKET_CHANGED")
        raw = load_json(baseline / path)
        ContractPacket.model_validate(raw)
        excluded.add(raw["document_id"])
        excluded_texts.add(digest(raw["text"]))
        packets.append((job, raw))
        if job["split"] == "train":
            sanity_rows.extend(load_json(baseline / "scorer-only/contract" / path.name))
    examples, identities = demonstrations(train, excluded, excluded_texts)
    sanity: list[dict[str, Any]] = []
    for label, count in (("Contradiction", 18), ("Entailment", 9), ("NotMentioned", 9)):
        rows = sorted(
            (r for r in sanity_rows if r["label"] == label),
            key=lambda r: digest(["sanity-v1", r["document_id"], r["hypothesis_id"]]),
        )
        if len(rows) < count or (label == "Contradiction" and len(rows) != count):
            raise ValueError("TRAIN_SANITY_DENOMINATOR_CHANGED")
        sanity.extend(
            {k: r[k] for k in ("document_id", "hypothesis_id", "label")} for r in rows[:count]
        )
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "scorer-only/predeclared.json", {"examples": identities, "sanity": sanity})
    prompts = {name: RUBRIC + VARIANT_INSTRUCTIONS[name] for name in VARIANTS}
    prompts["few-shot"] += (
        " These independent TRAIN demonstrations illustrate the rubric. Their DEMO aliases are "
        "illustrative only. Use only the current request's aliases in your answers. "
        + json.dumps(examples, ensure_ascii=False, separators=(",", ":"))
    )
    matrix = []
    for job, raw in packets:
        write_json(root / job["input"], raw)
        frozen = load_json(baseline / "predictions" / f"{job['job_id']}.json")
        for name in VARIANTS:
            variant = f"nli-{name}-{job['split']}"
            matrix.append(
                {
                    **job,
                    "job_id": f"{variant}-{raw['document_id']}",
                    "variant": variant,
                    "formulation": name,
                    "input_sha256": sha256(root / job["input"]),
                    "packet_sha256": frozen["selection_configuration"]["synthesis_packet_sha256"],
                }
            )
    synthetic = load_json(baseline / "inputs/control/legal.json")
    synth_path = "inputs/control/legal.json"
    write_json(root / synth_path, synthetic)
    source = semantic_source(text_source(synthetic["document_id"], [synthetic["text"]]))
    view = packet(source, synthetic["hypotheses"], request="synthetic", strategy="global", k=20)
    controls = [
        {
            "job_id": "control-" + name,
            "variant": "control-" + name,
            "kind": "contract",
            "mode": "direct",
            "strategy": "global",
            "k": 20,
            "formulation": name,
            "input": synth_path,
            "input_sha256": sha256(root / synth_path),
            "hypotheses": [h["hypothesis_id"] for h in synthetic["hypotheses"]],
            "packet_sha256": digest(view.payload),
        }
        for name in VARIANTS
    ]
    code = {
        *map(Path, reference["code_hashes"]),
        Path(__file__),
        ROOT / "scripts/contradiction_worker.py",
        ROOT / "scripts/external_eval/contradiction.py",
    }
    config = {
        "protocol": "contradiction-development-1",
        "run_root": str(root),
        "model": MODEL,
        "thinking": "MINIMAL",
        "simple_provider_shape": True,
        "request_spec": {},
        "retry_policy": "DEVELOPMENT_TRANSIENT_2",
        "pacing": {"http_interval_seconds": 10},
        "limits": {"generations": 68, "input_tokens": 2_300_000, "output_tokens": 280_000},
        "jobs": matrix,
        "controls": controls,
        "prompts": prompts,
        "prompt_hashes": {n: digest(p) for n, p in prompts.items()},
        "schema_hashes": {n: digest(schema(n)) for n in VARIANTS},
        "examples_sha256": digest([identities, examples]),
        "scorer_manifest_sha256": sha256(root / "scorer-only/predeclared.json"),
        "reference_seal_sha256": sha256(prior / "development-seal.json"),
        "selection_rule": {
            "min_train_contradiction_gain": 0.05,
            "max_macro_f1_loss": 0.02,
            "min_grounded_coverage": 0.95,
            "max_unsupported_rate": 0.25,
            "max_input_and_output_token_ratio": 1.5,
        },
        "code_hashes": {str(path): sha256(path) for path in sorted(code)},
    }
    path = root / "config/campaign.json"
    write_json(path, config)
    path.with_suffix(".sha256").write_text(sha256(path) + "\n", encoding="ascii")
    print(
        f"Frozen {len(matrix)} jobs, five disjoint TRAIN examples and "
        f"{len(sanity)} TRAIN sanity pairs"
    )


def run(root: Path, *, control: bool) -> None:
    path = root / "config/campaign.json"
    identity = sha256(path)
    if identity != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("CONFIG_HASH_MISMATCH")
    config = load_json(path)
    if any(sha256(Path(p)) != h for p, h in config["code_hashes"].items()):
        raise ValueError("CODE_CHANGED")
    admission = root / "config/admission.json"
    if not control and load_json(admission) != {"config_sha256": identity, "status": "PASS"}:
        raise ValueError("SYNTHETIC_ADMISSION_REQUIRED")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    worker = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "scripts/contradiction_worker.py")],
        input=json.dumps({"config_path": str(path), "control": control, "key": key()}),
        text=True,
        encoding="utf8",
        env=env,
        stderr=subprocess.DEVNULL,
    )
    if worker.returncode:
        raise ValueError("DEVELOPMENT_WORKER_FAILED_NO_RETRY")
    if control:
        for job in config["controls"]:
            row = load_json(root / "predictions" / f"{job['job_id']}.json")
            items = row["diagnostics"].get("items", [])
            if (
                row["metadata"]["status"] != "SUCCESS"
                or len(items) != 3
                or any(not item["status"].startswith("VALID_") for item in items)
            ):
                raise ValueError("SYNTHETIC_FORMULATION_ADMISSION_FAILED")
        write_json(admission, {"config_sha256": identity, "status": "PASS"})
        print("Four exact formulation controls passed. No corpus inference yet.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--train", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.prior is None or args.train is None:
            parser.error("prepare needs --prior and --train")
        prepare(args.prior.resolve(), args.train.resolve(), args.root.resolve())
    else:
        run(args.root.resolve(), control=args.action == "preflight")
