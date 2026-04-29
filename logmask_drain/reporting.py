"""Reports, inspection summaries, and drift signals."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .models import ParsedLine


def _entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counter.values())


def summarize_parsed(lines: list[ParsedLine]) -> dict[str, Any]:
    template_counts = Counter(line.template_hash for line in lines)
    template_text = {line.template_hash: line.template for line in lines}
    template_line_id: dict[str, int] = {}
    variables_by_type: Counter[str] = Counter()
    masked_chars_by_type: Counter[str] = Counter()
    unmasked_tokens: Counter[str] = Counter()
    masked_chars = 0
    raw_chars = 0
    for line in lines:
        raw_chars += len(line.raw)
        template_line_id.setdefault(line.template_hash, line.line_id)
        for variable in line.variables:
            variables_by_type[variable.type] += 1
            span_length = variable.end - variable.start
            masked_chars += span_length
            masked_chars_by_type[variable.type] += span_length
        for token in line.masked.split():
            if token.startswith("<VAR:"):
                continue
            unmasked_tokens[token] += 1
    top_templates = [
        {
            "template_hash": template_hash,
            "template": template_text[template_hash],
            "count": count,
        }
        for template_hash, count in template_counts.most_common(10)
    ]
    mask_coverage_by_type = {
        key: {
            "count": variables_by_type[key],
            "masked_chars": masked_chars_by_type[key],
            "coverage": masked_chars_by_type[key] / raw_chars if raw_chars else 0.0,
        }
        for key in sorted(variables_by_type)
    }
    singleton_template_examples = [
        {
            "line_id": template_line_id[template_hash],
            "template_hash": template_hash,
            "template": template_text[template_hash],
        }
        for template_hash, count in sorted(template_counts.items(), key=lambda item: (template_line_id[item[0]], item[0]))
        if count == 1
    ][:10]
    singleton_unmasked_tokens = sorted(token for token, count in unmasked_tokens.items() if count == 1)
    return {
        "line_count": len(lines),
        "unique_template_count": len(template_counts),
        "singleton_template_count": sum(1 for count in template_counts.values() if count == 1),
        "variables_by_type": dict(sorted(variables_by_type.items())),
        "mask_coverage": masked_chars / raw_chars if raw_chars else 0.0,
        "mask_coverage_by_type": mask_coverage_by_type,
        "unmasked_high_cardinality_token_rate": unmasked_high_cardinality_token_rate(lines),
        "top_unmasked_high_cardinality_tokens": [
            {"token": token, "count": unmasked_tokens[token]} for token in singleton_unmasked_tokens[:10]
        ],
        "singleton_template_examples": singleton_template_examples,
        "top_templates": top_templates,
        "template_entropy": _entropy(template_counts),
    }


def _distribution(lines: list[ParsedLine]) -> Counter[str]:
    return Counter(line.template_hash for line in lines)


def _jensen_shannon(left: Counter[str], right: Counter[str]) -> float:
    keys = set(left) | set(right)
    left_total = sum(left.values()) or 1
    right_total = sum(right.values()) or 1
    left_probs = {key: left[key] / left_total for key in keys}
    right_probs = {key: right[key] / right_total for key in keys}
    mid_probs = {key: (left_probs[key] + right_probs[key]) / 2 for key in keys}

    def kl(p: dict[str, float], q: dict[str, float]) -> float:
        total = 0.0
        for key, value in p.items():
            if value > 0 and q[key] > 0:
                total += value * math.log2(value / q[key])
        return total

    return (kl(left_probs, mid_probs) + kl(right_probs, mid_probs)) / 2


def unmasked_high_cardinality_token_rate(lines: list[ParsedLine]) -> float:
    counts: Counter[str] = Counter()
    total = 0
    for line in lines:
        for token in line.masked.split():
            if token.startswith("<VAR:"):
                continue
            counts[token] += 1
            total += 1
    if total == 0:
        return 0.0
    high_cardinality = sum(count for token, count in counts.items() if count == 1)
    return high_cardinality / total


def drift_report(old: list[ParsedLine], new: list[ParsedLine]) -> dict[str, Any]:
    old_summary = summarize_parsed(old)
    new_summary = summarize_parsed(new)
    old_hashes = set(_distribution(old))
    new_hashes = _distribution(new)
    new_template_lines = sum(count for key, count in new_hashes.items() if key not in old_hashes)
    variable_keys = set(old_summary["variables_by_type"]) | set(new_summary["variables_by_type"])
    variable_delta = {
        key: new_summary["variables_by_type"].get(key, 0) - old_summary["variables_by_type"].get(key, 0)
        for key in sorted(variable_keys)
    }
    return {
        "new_template_rate": new_template_lines / len(new) if new else 0.0,
        "singleton_template_rate_old": old_summary["singleton_template_count"] / len(old) if old else 0.0,
        "singleton_template_rate_new": new_summary["singleton_template_count"] / len(new) if new else 0.0,
        "template_entropy_delta": new_summary["template_entropy"] - old_summary["template_entropy"],
        "variable_distribution_delta": variable_delta,
        "mask_coverage_delta": new_summary["mask_coverage"] - old_summary["mask_coverage"],
        "unmasked_high_cardinality_token_rate_old": unmasked_high_cardinality_token_rate(old),
        "unmasked_high_cardinality_token_rate_new": unmasked_high_cardinality_token_rate(new),
        "template_frequency_jsd": _jensen_shannon(_distribution(old), _distribution(new)),
    }
