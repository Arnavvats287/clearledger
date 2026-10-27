"""Pure scorers; gold is explicit input and never exposed to predictor preparation."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .contracts import ContractOutput, ContractPacket, DocileOutput, DocilePacket, Edge
from .source import locate, normalized, quote_box

CLASSES = ("Entailment", "Contradiction", "NotMentioned")
PREDICTED = (*CLASSES, "Abstain", "ProviderFailure")
Interval = tuple[int, int]


def union(intervals: Iterable[Interval]) -> list[Interval]:
    result: list[Interval] = []
    for start, end in sorted(intervals):
        if not 0 <= start < end:
            raise ValueError("INVALID_INTERVAL")
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def overlap_counts(gold: Iterable[Interval], predicted: Iterable[Interval]) -> Counter[str]:
    left, right = union(gold), union(predicted)
    i, j, overlap = 0, 0, 0
    while i < len(left) and j < len(right):
        overlap += max(0, min(left[i][1], right[j][1]) - max(left[i][0], right[j][0]))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return Counter(
        tp=overlap,
        fp=sum(b - a for a, b in right) - overlap,
        fn=sum(b - a for a, b in left) - overlap,
    )


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


@dataclass(frozen=True)
class GoldNli:
    document_id: str
    hypothesis_id: str
    label: str
    evidence: tuple[Interval, ...]


def score_contract(
    packets: dict[str, ContractPacket],
    outputs: list[ContractOutput],
    gold: list[GoldNli],
) -> dict[str, Any]:
    expected = {(p.document_id, h.hypothesis_id) for p in packets.values() for h in p.hypotheses}
    gold_keys = [(g.document_id, g.hypothesis_id) for g in gold]
    if set(gold_keys) != expected or len(gold_keys) != len(expected):
        raise ValueError("GOLD_COVERAGE_MISMATCH")
    documents: dict[str, ContractOutput] = {}
    output: ContractOutput | None
    for output in outputs:
        if output.document_id not in packets or output.document_id in documents:
            raise ValueError("UNKNOWN_OR_DUPLICATE_OUTPUT")
        if any((output.document_id, a.hypothesis_id) not in expected for a in output.answers):
            raise ValueError("UNKNOWN_HYPOTHESIS")
        if output.metadata.failure != "NONE" and any(
            a.predicted_label not in {"Abstain", "ProviderFailure"} for a in output.answers
        ):
            raise ValueError("FAILURE_WITH_SUCCESSFUL_ANSWERS")
        documents[output.document_id] = output
    matrix = {g: dict.fromkeys(PREDICTED, 0) for g in CLASSES}
    evidence: Counter[str] = Counter()
    joint: Counter[str] = Counter()
    quotes: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for item in gold:
        if item.label not in CLASSES:
            raise ValueError("INVALID_GOLD_LABEL")
        packet = packets[item.document_id]
        if any(not 0 <= a < b <= len(packet.text) for a, b in item.evidence):
            raise ValueError("INVALID_GOLD_RANGE")
        output = documents.get(item.document_id)
        answer = (
            next((a for a in output.answers if a.hypothesis_id == item.hypothesis_id), None)
            if output
            else None
        )
        label = (
            answer.predicted_label
            if answer
            else (
                "ProviderFailure" if output and output.metadata.failure == "PROVIDER" else "Abstain"
            )
        )
        matrix[item.label][label] += 1
        counts["missing_answers"] += answer is None
        counts["answered"] += label in CLASSES
        counts["correct"] += label == item.label
        counts["abstentions"] += label == "Abstain"
        counts["provider_failures"] += label == "ProviderFailure"
        counts["fallback_pairs"] += bool(output and output.metadata.fallback)
        if output and output.metadata.failure != "NONE":
            counts[f"failure:{output.metadata.failure}"] += 1
        counts["assertive_predictions"] += label in CLASSES[:2]
        counts["unsupported_conclusions"] += label in CLASSES[:2] and label != item.label
        intervals: list[Interval] = []
        if answer:
            for quote in answer.evidence_quotes:
                result = locate(packet.text, quote)
                quotes[result.status] += 1
                intervals.extend(result.intervals)
                if item.label == "NotMentioned":
                    counts["quotes_on_gold_notmentioned"] += 1
        if item.label in CLASSES[:2]:
            evidence.update(overlap_counts(item.evidence, intervals))
            joint.update(overlap_counts(item.evidence, intervals if label == item.label else []))
    per_class: dict[str, dict[str, Any]] = {}
    for class_label in CLASSES:
        tp = matrix[class_label][class_label]
        fp = sum(matrix[g][class_label] for g in CLASSES if g != class_label)
        fn = sum(matrix[class_label].values()) - tp
        per_class[class_label] = prf(tp, fp, fn)
    return {
        "pairs": len(gold),
        "accuracy": ratio(counts["correct"], len(gold)),
        "macro_f1": sum(float(per_class[c]["f1"] or 0) for c in CLASSES) / len(CLASSES),
        "macro_zero_support_rule": "Undefined class F1 contributes zero; per-class value is null",
        "per_class": per_class,
        "confusion_gold_rows_prediction_columns": matrix,
        "answered_only_accuracy": ratio(counts["correct"], counts["answered"]),
        "counts": counts,
        "quote_status": quotes,
        "quote_validity": ratio(quotes["VALID"], sum(quotes.values())),
        "unsupported_conclusion_rate": ratio(
            counts["unsupported_conclusions"], counts["assertive_predictions"]
        ),
        "evidence_character_overlap": prf(evidence["tp"], evidence["fp"], evidence["fn"]),
        "joint_correct_label_evidence": prf(joint["tp"], joint["fp"], joint["fn"]),
    }


@dataclass(frozen=True)
class GoldInvoice:
    document_id: str
    is_invoice: bool
    references: tuple[str, ...]


def kile_predictions(
    packet: DocilePacket, output: DocileOutput
) -> tuple[list[dict[str, Any]], Counter[str]]:
    if packet.document_id != output.document_id:
        raise ValueError("DOCUMENT_ID_MISMATCH")
    predictions = []
    counts: Counter[str] = Counter()
    seen = set()
    for reference in output.invoice_references:
        value = normalized(reference.value)
        if value in seen:
            counts["duplicate_fields"] += 1
            continue
        seen.add(value)
        result = quote_box(packet, reference.quote, reference.page)
        if not value or value not in normalized(reference.quote.text):
            counts["VALUE_NOT_IN_QUOTE"] += 1
        elif result["status"] != "VALID":
            counts[result["status"]] += 1
        else:
            counts["VALID"] += 1
            predictions.append(
                {
                    "fieldtype": "document_id",
                    "text": value,
                    "page": result["page"],
                    "bbox": result["bbox"],
                    "score": reference.confidence or 0.0,
                }
            )
    return predictions, counts


def score_docile(
    packets: dict[str, DocilePacket],
    outputs: list[DocileOutput],
    gold: list[GoldInvoice],
) -> dict[str, Any]:
    if {g.document_id for g in gold} != set(packets) or len(gold) != len(packets):
        raise ValueError("GOLD_COVERAGE_MISMATCH")
    documents: dict[str, DocileOutput] = {}
    output: DocileOutput | None
    for output in outputs:
        if output.document_id not in packets or output.document_id in documents:
            raise ValueError("UNKNOWN_OR_DUPLICATE_OUTPUT")
        if output.metadata.failure != "NONE" and output.invoice_references:
            raise ValueError("FAILURE_WITH_FIELDS")
        documents[output.document_id] = output
    counts: Counter[str] = Counter()
    quote_status: Counter[str] = Counter()
    for item in gold:
        expected = {normalized(v) for v in item.references} if item.is_invoice else set()
        output = documents.get(item.document_id)
        emitted = {normalized(r.value) for r in output.invoice_references} if output else set()
        supported = set()
        if output:
            located, statuses = kile_predictions(packets[item.document_id], output)
            supported = {p["text"] for p in located}
            quote_status.update(statuses)
            counts[f"failure:{output.metadata.failure}"] += output.metadata.failure != "NONE"
        correct = expected & supported
        counts.update(tp=len(correct), fp=len(emitted - correct), fn=len(expected - correct))
        counts["exact_set_match"] += (
            emitted == expected and supported == emitted and output is not None
        )
        counts["covered_documents"] += bool(emitted)
        counts["abstained_documents"] += not emitted
        counts["missing_outputs"] += output is None
        counts["non_invoice_documents"] += not item.is_invoice
        counts["non_invoice_false_emissions"] += len(emitted) if not item.is_invoice else 0
        counts["emitted_fields"] += len(emitted)
        counts["unsupported_fields"] += len(emitted - correct)
    return {
        "documents": len(gold),
        "invoice_id": prf(counts["tp"], counts["fp"], counts["fn"]),
        "exact_set_match": ratio(counts["exact_set_match"], len(gold)),
        "coverage": ratio(counts["covered_documents"], len(gold)),
        "unsupported_field_rate": ratio(counts["unsupported_fields"], counts["emitted_fields"]),
        "quote_status": quote_status,
        "counts": counts,
        "quote_validity": ratio(
            quote_status["VALID"],
            sum(value for key, value in quote_status.items() if key != "duplicate_fields"),
        ),
        "warning": "Custom source-grounded ID score, not official full DocILE score",
    }


def score_edges(
    gold: Iterable[Edge], predictions: Iterable[Edge], abstentions: set[str] | None = None
) -> dict[str, Any]:
    gold_list = [(edge.txn_id, edge.line_id) for edge in gold]
    predicted_list = [(edge.txn_id, edge.line_id) for edge in predictions]
    gold_set, predicted_set = set(gold_list), set(predicted_list)
    if len(gold_set) != len(gold_list):
        raise ValueError("DUPLICATE_GOLD_EDGE")
    abstentions = abstentions or set()
    if any(txn in abstentions for txn, _ in predicted_set):
        raise ValueError("PREDICTION_AND_ABSTENTION_CONFLICT")
    return {
        **prf(
            len(gold_set & predicted_set),
            len(predicted_set - gold_set),
            len(gold_set - predicted_set),
        ),
        "duplicate_prediction_count": len(predicted_list) - len(predicted_set),
        "abstention_count": len(abstentions),
        "missed_edges_for_abstained_transactions": sum(t in abstentions for t, _ in gold_set),
        "scope": "Independent ledger-to-processor graph scorer, not ClearLedger AR accuracy",
    }
