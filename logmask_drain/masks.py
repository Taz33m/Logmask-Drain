"""Mask ordering and regex compilation utilities."""

from __future__ import annotations

import regex

from .models import MaskSpec


FLAG_VALUES = {
    "IGNORECASE": regex.IGNORECASE,
    "MULTILINE": regex.MULTILINE,
    "ASCII": regex.ASCII,
}


def flags_to_regex_value(flags: list[str]) -> int:
    value = 0
    for flag in flags:
        value |= FLAG_VALUES[flag]
    return value


def compile_mask(mask: MaskSpec) -> regex.Pattern[str]:
    return regex.compile(mask.pattern, flags_to_regex_value(mask.flags))


def ordered_masks(masks: list[MaskSpec]) -> list[MaskSpec]:
    return sorted(
        (mask for mask in masks if mask.enabled),
        key=lambda item: (-item.priority, item.name, item.pattern),
    )

