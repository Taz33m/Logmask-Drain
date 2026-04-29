"""Validation gate for LLM-proposed mask candidates."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import regex

from .io import model_to_data
from .masks import compile_mask
from .models import (
    CandidateMask,
    CandidateValidationSummary,
    MaskSpec,
    RejectedMask,
)
from .regex_validation import selected_span, validate_mask


KNOWN_CANDIDATE_TYPES = {
    "DATETIME",
    "UUID",
    "IP",
    "URL",
    "EMAIL",
    "PATH",
    "HEX",
    "BLOCK_ID",
    "REQUEST_ID",
    "SESSION_ID",
    "TRACE_ID",
    "SPAN_ID",
    "PID",
    "PORT",
    "DURATION",
    "QUOTED_STRING",
    "NUMBER",
    "GENERIC_ID",
}
LOG_LEVEL_TYPES = {"LOG_LEVEL", "LEVEL", "SEVERITY"}
LOG_LEVEL_VALUES = {"TRACE", "DEBUG", "INFO", "WARN", "WARNING", "ERROR", "FATAL", "CRITICAL"}
PLACEHOLDER = re.compile(r"^<VAR:([A-Z0-9_]+)>$")
STATIC_KEY = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]*\s*[=:]")
FULL_LINE_PATTERNS = {".*", ".+", "^.*$", "^.+$"}


@dataclass(frozen=True)
class CandidateValidationResult:
    accepted: list[MaskSpec]
    rejected: list[RejectedMask]
    summary: CandidateValidationSummary
    report: dict[str, Any]


def _runtime_signature(mask: MaskSpec) -> tuple[Any, ...]:
    return (
        mask.type,
        mask.pattern,
        tuple(sorted(mask.flags)),
        mask.value_group,
        mask.replacement,
    )


def candidate_to_mask(candidate: CandidateMask) -> MaskSpec:
    return MaskSpec(
        name=candidate.name,
        type=candidate.type,
        pattern=candidate.pattern,
        value_group=candidate.value_group,
        replacement=candidate.replacement,
        priority=candidate.priority,
        enabled=True,
        flags=candidate.flags,
    )


def _reject(candidate: CandidateMask, reason: str) -> RejectedMask:
    return RejectedMask(name=candidate.name, type=candidate.type, pattern=candidate.pattern, reason=reason)


def _selected_values(mask: MaskSpec, lines: list[str], *, timeout_seconds: float = 0.01) -> list[str] | None:
    try:
        compiled = compile_mask(mask)
    except regex.error:
        return None

    values: list[str] = []
    for line in lines:
        try:
            for match in compiled.finditer(line, timeout=timeout_seconds):
                try:
                    span = selected_span(match, mask.value_group)
                except IndexError:
                    return None
                if span is None:
                    continue
                start, end = span
                if start != end:
                    values.append(line[start:end])
        except TimeoutError:
            return None
    return values


def _selected_spans(mask: MaskSpec, lines: list[str], *, timeout_seconds: float = 0.01) -> list[tuple[int, int, int]] | None:
    try:
        compiled = compile_mask(mask)
    except regex.error:
        return None

    spans: list[tuple[int, int, int]] = []
    for line_index, line in enumerate(lines):
        try:
            for match in compiled.finditer(line, timeout=timeout_seconds):
                try:
                    span = selected_span(match, mask.value_group)
                except IndexError:
                    return None
                if span is None:
                    continue
                start, end = span
                if start != end:
                    spans.append((line_index, start, end))
        except TimeoutError:
            return None
    return spans


def _overlap_count(mask: MaskSpec, other_masks: list[MaskSpec], lines: list[str]) -> int:
    candidate_spans = _selected_spans(mask, lines)
    if candidate_spans is None:
        return 0
    other_spans: list[tuple[int, int, int]] = []
    for other in other_masks:
        spans = _selected_spans(other, lines)
        if spans:
            other_spans.extend(spans)
    count = 0
    for line_index, start, end in candidate_spans:
        for other_line_index, other_start, other_end in other_spans:
            if line_index == other_line_index and not (end <= other_start or start >= other_end):
                count += 1
                break
    return count


def _precheck_candidate(candidate: CandidateMask, *, allow_new_types: bool) -> str | None:
    placeholder = PLACEHOLDER.match(candidate.replacement)
    if placeholder is None:
        return "invalid_placeholder"
    if placeholder.group(1) != candidate.type:
        return "placeholder_type_mismatch"
    if candidate.type in LOG_LEVEL_TYPES:
        return "log_level_mask"
    if not allow_new_types and candidate.type not in KNOWN_CANDIDATE_TYPES:
        return "unknown_type"
    if candidate.pattern.strip() in FULL_LINE_PATTERNS:
        return "broad_full_line_capture"
    if regex.search(r"\^\s*\.\*", candidate.pattern) or regex.search(r"\.\*\s*\$", candidate.pattern):
        return "broad_full_line_capture"
    return None


def _postcheck_mask(mask: MaskSpec, lines: list[str]) -> str | None:
    values = _selected_values(mask, lines)
    if values is None:
        return None
    if values and all(value.upper() in LOG_LEVEL_VALUES for value in values):
        return "log_level_mask"
    if any(STATIC_KEY.search(value) for value in values):
        return "selected_value_contains_static_key"
    return None


def validate_candidate_masks(
    candidates: list[CandidateMask],
    lines: list[str],
    *,
    base_masks: list[MaskSpec] | None = None,
    allow_new_types: bool = False,
    strict: bool = True,
    include_raw_examples: bool = False,
) -> CandidateValidationResult:
    accepted: list[MaskSpec] = []
    rejected: list[RejectedMask] = []
    reason_counts: Counter[str] = Counter()
    report_candidates: list[dict[str, Any]] = []
    rejection_examples: dict[str, list[dict[str, Any]]] = {}
    seen_names = {mask.name for mask in base_masks or []}
    seen_signatures = {_runtime_signature(mask) for mask in base_masks or []}
    previous_masks = list(base_masks or [])

    for candidate in candidates:
        candidate_report = model_to_data(candidate)
        candidate_report.pop("examples_observed", None)

        reason = _precheck_candidate(candidate, allow_new_types=allow_new_types)
        mask = candidate_to_mask(candidate)

        if reason is None and mask.name in seen_names:
            reason = "duplicate_name"
        if reason is None and _runtime_signature(mask) in seen_signatures:
            reason = "duplicate_runtime_equivalent"

        if reason is None:
            validation = validate_mask(
                mask,
                lines,
                strict=strict,
                include_raw_examples=include_raw_examples,
                max_coverage_fraction=0.50,
            )
            if validation.rejected is not None:
                reason = validation.rejected.reason
                mask = validation.accepted or mask
            else:
                mask = validation.accepted or mask

        if reason is None:
            candidate_report["overlap_count"] = _overlap_count(mask, previous_masks, lines)
            reason = _postcheck_mask(mask, lines)

        if reason is None:
            accepted.append(mask)
            previous_masks.append(mask)
            seen_names.add(mask.name)
            seen_signatures.add(_runtime_signature(mask))
            candidate_report["status"] = "accepted"
            candidate_report["validation"] = model_to_data(mask.validation)
        else:
            rejected_mask = _reject(candidate, reason)
            rejected.append(rejected_mask)
            reason_counts[reason] += 1
            candidate_report["status"] = "rejected"
            candidate_report["reason"] = reason
            rejection_examples.setdefault(reason, [])
            if len(rejection_examples[reason]) < 5:
                rejection_examples[reason].append(
                    {
                        "name": candidate.name,
                        "type": candidate.type,
                        "pattern": candidate.pattern,
                    }
                )

        report_candidates.append(candidate_report)

    summary = CandidateValidationSummary(
        candidate_count=len(candidates),
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        rejection_reasons=dict(sorted(reason_counts.items())),
    )
    report = {
        "candidate_schema_version": "0.1",
        "candidate_validation": model_to_data(summary),
        "rejection_examples": rejection_examples,
        "candidates": report_candidates,
    }
    return CandidateValidationResult(accepted=accepted, rejected=rejected, summary=summary, report=report)
