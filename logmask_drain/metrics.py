"""Benchmark metrics for log parsing."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import regex


PLACEHOLDER_PATTERNS = [
    regex.compile(r"<VAR:[A-Za-z0-9_]+>"),
    regex.compile(r"<\*>"),
    regex.compile(r"<[^>\s]+>"),
    regex.compile(r"\{[A-Za-z0-9_]+\}"),
]


def normalize_generic_template(template: str) -> str:
    normalized = template
    for pattern in PLACEHOLDER_PATTERNS:
        normalized = pattern.sub("<*>", normalized)
    normalized = regex.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_typed_template(template: str) -> str:
    return regex.sub(r"\s+", " ", template).strip()


def parsing_accuracy_generic(predicted: list[str], truth: list[str]) -> float:
    if len(predicted) != len(truth):
        raise ValueError("predicted and truth lengths differ")
    if not truth:
        return 0.0
    correct = 0
    for predicted_template, truth_template in zip(predicted, truth):
        if normalize_generic_template(predicted_template) == normalize_generic_template(truth_template):
            correct += 1
    return correct / len(truth)


def parsing_accuracy_typed(predicted: list[str], truth: list[str]) -> float:
    if len(predicted) != len(truth):
        raise ValueError("predicted and truth lengths differ")
    if not truth:
        return 0.0
    correct = 0
    for predicted_template, truth_template in zip(predicted, truth):
        if normalize_typed_template(predicted_template) == normalize_typed_template(truth_template):
            correct += 1
    return correct / len(truth)


def grouping_accuracy_exact(predicted_clusters: list[str], truth_clusters: list[str]) -> float:
    if len(predicted_clusters) != len(truth_clusters):
        raise ValueError("predicted and truth lengths differ")
    if not truth_clusters:
        return 0.0

    predicted_sets: dict[str, set[int]] = defaultdict(set)
    truth_sets: dict[str, set[int]] = defaultdict(set)
    for index, (predicted, truth) in enumerate(zip(predicted_clusters, truth_clusters)):
        predicted_sets[predicted].add(index)
        truth_sets[truth].add(index)

    correct = 0
    for index, (predicted, truth) in enumerate(zip(predicted_clusters, truth_clusters)):
        if predicted_sets[predicted] == truth_sets[truth]:
            correct += 1
    return correct / len(truth_clusters)


def _span_data(span: Any) -> Mapping[str, Any]:
    if isinstance(span, Mapping):
        return span
    if hasattr(span, "model_dump"):
        return span.model_dump(mode="json")
    raise TypeError("span must be a mapping or Pydantic model")


def _span_key(span: Any, *, typed: bool) -> tuple[Any, ...]:
    data = _span_data(span)
    base = (int(data["start"]), int(data["end"]))
    if typed:
        return (*base, str(data["type"]))
    return base


def variable_span_f1(
    predicted: list[list[Any]],
    truth: list[list[Any]],
    *,
    typed: bool = True,
) -> dict[str, float | int]:
    """Exact variable-span precision/recall/F1.

    The metric compares per-line `(start, end, type)` tuples by default. Set
    `typed=False` to compare only exact character boundaries.
    """

    if len(predicted) != len(truth):
        raise ValueError("predicted and truth lengths differ")

    predicted_count = 0
    truth_count = 0
    true_positive = 0

    for predicted_line, truth_line in zip(predicted, truth):
        predicted_keys = {_span_key(span, typed=typed) for span in predicted_line}
        truth_keys = {_span_key(span, typed=typed) for span in truth_line}
        predicted_count += len(predicted_keys)
        truth_count += len(truth_keys)
        true_positive += len(predicted_keys & truth_keys)

    if predicted_count == 0 and truth_count == 0:
        precision = recall = f1 = 1.0
    else:
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / truth_count if truth_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "predicted_count": predicted_count,
        "truth_count": truth_count,
    }
