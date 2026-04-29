"""Template ID and stable hash helpers."""

from __future__ import annotations

from .io import sha1_text


def normalize_template(template: str) -> str:
    return " ".join(template.split())


def template_hash(template: str) -> str:
    return "sha1:" + sha1_text(normalize_template(template))


def format_template_id(index: int) -> str:
    return f"T{index:06d}"


def hash_template_id(hash_value: str, *, length: int = 8) -> str:
    digest = hash_value.split(":", 1)[-1]
    return "T" + digest[:length].upper()
