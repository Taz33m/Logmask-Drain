"""Synthetic log generation and CPU-only performance benchmarking."""

from __future__ import annotations

import time
from typing import Any

from .mask_bundle import create_mask_bundle
from .masking import Masker
from .pipeline import parse_lines
from .reporting import summarize_parsed
from .synthesis_backends.rules import get_rule_masks


def synthetic_log_lines(count: int) -> list[str]:
    """Generate deterministic mixed-shape logs for throughput checks."""

    users = ["alice", "bob", "carol", "dave"]
    services = ["auth", "api", "worker", "config"]
    lines: list[str] = []
    for index in range(count):
        user = users[index % len(users)]
        service = services[index % len(services)]
        octet = index % 250 + 1
        request = f"req-{index:08d}"
        session = f"sess-{index:08d}"
        uuid = f"123e4567-e89b-12d3-a456-{index % 1_000_000_000_000:012d}"
        if index % 4 == 0:
            lines.append(
                f"2024-01-15 10:{index % 60:02d}:00 INFO service={service} "
                f"request_id={request} user {user} login from 10.0.0.{octet}"
            )
        elif index % 4 == 1:
            lines.append(
                f"2024/01/15 10:{index % 60:02d}:01 WARN service={service} "
                f"session_id={session} GET https://example.internal/v1/items/{index} "
                f"trace={uuid} took {index % 900 + 1}ms"
            )
        elif index % 4 == 2:
            lines.append(
                f"Jan 15 10:{index % 60:02d}:02 ERROR worker pid={1000 + index} "
                f"port=443 path=/srv/app/releases/{index}/config.json msg=\"retry failed\""
            )
        else:
            lines.append(
                f"ts=170532{index % 10000:04d} INFO config request_id={request} "
                f"loaded C:\\ProgramData\\Logmask\\{index}\\settings.ini status=200 version=2"
            )
    return lines


def _timed(label: str, action) -> tuple[str, Any, float]:
    start = time.perf_counter()
    result = action()
    return label, result, time.perf_counter() - start


def performance_benchmark(count: int, *, rule_mode: str = "conservative") -> dict[str, Any]:
    lines = synthetic_log_lines(count)
    timings: dict[str, float] = {}

    label, bundle, elapsed = _timed(
        "synthesize",
        lambda: create_mask_bundle(
            get_rule_masks(rule_mode),
            lines[: min(50, len(lines))],
            backend="rules",
            sampler="synthetic",
            rule_mode=rule_mode,
            strict=True,
        ),
    )
    timings[label] = elapsed

    masker = Masker(bundle)
    label, masked, elapsed = _timed("mask", lambda: masker.mask_lines(lines))
    timings[label] = elapsed

    label, parsed, elapsed = _timed(
        "parse",
        lambda: parse_lines(lines, bundle, template_id_mode="hash"),
    )
    timings[label] = elapsed

    label, summary, elapsed = _timed("report", lambda: summarize_parsed(parsed))
    timings[label] = elapsed

    stages = {}
    for stage, seconds in timings.items():
        stages[stage] = {
            "seconds": seconds,
            "lines_per_second": count / seconds if seconds else 0.0,
            "runtime_per_100_logs_seconds": seconds / max(count, 1) * 100,
        }

    return {
        "line_count": count,
        "rule_mode": rule_mode,
        "stages": stages,
        "accepted_masks": len(bundle.masks),
        "rejected_masks": len(bundle.rejected_masks),
        "unique_template_count": summary["unique_template_count"],
        "singleton_template_count": summary["singleton_template_count"],
        "mask_coverage": summary["mask_coverage"],
    }
