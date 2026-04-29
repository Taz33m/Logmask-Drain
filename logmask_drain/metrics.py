"""Benchmark metrics for log parsing."""

from __future__ import annotations

from collections import defaultdict

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

