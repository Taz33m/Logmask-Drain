"""Regex safety and usefulness validation."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import regex

from .io import sha256_text
from .masks import compile_mask
from .models import MaskSpec, MaskValidation, RejectedMask, ValidationExample


VALIDATOR_VERSION = "0.1"


@dataclass(frozen=True)
class ValidationResult:
    accepted: MaskSpec | None
    rejected: RejectedMask | None


def has_catastrophic_shape(pattern: str) -> bool:
    """Catch obvious nested broad repeats before execution."""

    suspicious = [
        r"\(\.\*\)[*+{]",
        r"\(\.\+\)[*+{]",
        r"\(\[\^?.*?\][*+]\)[*+{]",
        r"\(\?:\.\*\)[*+{]",
        r"\(\?:\.\+\)[*+{]",
        r"\.\*\.\*",
        r"\.\+\.\+",
    ]
    return any(regex.search(item, pattern) for item in suspicious)


def selected_span(match: regex.Match[str], value_group: int | None) -> tuple[int, int] | None:
    group = 0 if value_group is None else value_group
    if group > match.re.groups:
        raise IndexError(f"value_group {group} does not exist")
    span = match.span(group)
    if span == (-1, -1):
        return None
    return span


def _redacted_example(value: str, include_raw: bool) -> ValidationExample:
    if include_raw:
        return ValidationExample(value=value, length=len(value))
    return ValidationExample(sha256=sha256_text(value), length=len(value), preview=None)


def _reject(mask: MaskSpec, reason: str, warnings: list[str] | None = None) -> ValidationResult:
    validation = MaskValidation(status="rejected", reason=reason, warnings=warnings or [])
    rejected = RejectedMask(name=mask.name, type=mask.type, pattern=mask.pattern, reason=reason)
    return ValidationResult(mask.model_copy(update={"validation": validation}), rejected)


def validate_mask(
    mask: MaskSpec,
    lines: list[str],
    *,
    strict: bool = True,
    include_raw_examples: bool = False,
    timeout_seconds: float = 0.01,
    max_coverage_fraction: float = 0.80,
) -> ValidationResult:
    warnings: list[str] = []

    if strict and mask.replacement != f"<VAR:{mask.type}>":
        return _reject(mask, "replacement/type mismatch")

    if has_catastrophic_shape(mask.pattern):
        return _reject(mask, "known catastrophic regex shape")

    try:
        compiled = compile_mask(mask)
    except regex.error as exc:
        return _reject(mask, f"regex syntax error: {exc}")

    if mask.value_group is not None and mask.value_group > compiled.groups:
        return _reject(mask, f"value_group {mask.value_group} does not exist")

    try:
        empty_match = compiled.search("", timeout=timeout_seconds)
    except TimeoutError:
        return _reject(mask, "regex timed out on empty-string validation")

    if empty_match is not None:
        span = selected_span(empty_match, mask.value_group)
        if span is not None and span[0] == span[1]:
            return _reject(mask, "selected value can match the empty string")

    matched_lines = 0
    span_count = 0
    selected_chars = 0
    values: Counter[str] = Counter()
    examples: list[ValidationExample] = []
    total_chars = sum(len(line) for line in lines) or 1

    for line in lines:
        line_matched = False
        try:
            iterator = compiled.finditer(line, timeout=timeout_seconds)
            for match in iterator:
                try:
                    span = selected_span(match, mask.value_group)
                except IndexError as exc:
                    return _reject(mask, str(exc))
                if span is None:
                    continue
                start, end = span
                if start == end:
                    return _reject(mask, "selected value group produced an empty span")
                value = line[start:end]
                line_matched = True
                span_count += 1
                selected_chars += len(value)
                values[value] += 1
                if len(examples) < 5:
                    examples.append(_redacted_example(value, include_raw_examples))
        except TimeoutError:
            return _reject(mask, "regex timed out on sample validation")

        if line_matched:
            matched_lines += 1

    if strict and span_count == 0:
        return _reject(mask, "mask produced no matches on the validation sample")

    coverage_fraction = selected_chars / total_chars
    if strict and coverage_fraction > max_coverage_fraction:
        return _reject(mask, f"mask covers too much sample text ({coverage_fraction:.2%})")

    matched_line_fraction = matched_lines / len(lines) if lines else 0.0
    if strict and matched_line_fraction > 0.98 and span_count > max(10, len(lines) * 3):
        return _reject(mask, "mask appears over-broad across the validation sample")

    if matched_line_fraction > 0.95:
        warnings.append("mask matches almost every line")

    validation = MaskValidation(
        status="accepted",
        matched_line_fraction=matched_line_fraction,
        matched_span_count=span_count,
        unique_value_count=len(values),
        examples=examples,
        warnings=warnings,
    )
    return ValidationResult(mask.model_copy(update={"validation": validation}), None)


def validate_masks(
    masks: list[MaskSpec],
    lines: list[str],
    *,
    strict: bool = True,
    include_raw_examples: bool = False,
) -> tuple[list[MaskSpec], list[RejectedMask]]:
    accepted: list[MaskSpec] = []
    rejected: list[RejectedMask] = []
    seen_names: set[str] = set()

    for mask in masks:
        if mask.name in seen_names:
            rejected.append(
                RejectedMask(
                    name=mask.name,
                    type=mask.type,
                    pattern=mask.pattern,
                    reason="duplicate mask name",
                )
            )
            continue
        seen_names.add(mask.name)
        result = validate_mask(
            mask,
            lines,
            strict=strict,
            include_raw_examples=include_raw_examples,
        )
        if result.accepted is not None and result.rejected is None:
            accepted.append(result.accepted)
        elif result.rejected is not None:
            rejected.append(result.rejected)

    return accepted, rejected


def entropy(values: Counter[str]) -> float:
    total = sum(values.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in values.values())
