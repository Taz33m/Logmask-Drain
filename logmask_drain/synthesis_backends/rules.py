"""Built-in conservative and aggressive rule masks."""

from __future__ import annotations

from ..models import MaskSpec


def conservative_masks() -> list[MaskSpec]:
    return [
        MaskSpec(
            name="datetime_iso",
            type="DATETIME",
            pattern=r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b",
            replacement="<VAR:DATETIME>",
            priority=120,
        ),
        MaskSpec(
            name="date_iso",
            type="DATETIME",
            pattern=r"\b\d{4}-\d{2}-\d{2}\b",
            replacement="<VAR:DATETIME>",
            priority=115,
        ),
        MaskSpec(
            name="uuid",
            type="UUID",
            pattern=r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
            replacement="<VAR:UUID>",
            priority=110,
        ),
        MaskSpec(
            name="ipv4",
            type="IP",
            pattern=r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)",
            replacement="<VAR:IP>",
            priority=105,
        ),
        MaskSpec(
            name="ipv6",
            type="IP",
            pattern=r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b",
            replacement="<VAR:IP>",
            priority=104,
        ),
        MaskSpec(
            name="url",
            type="URL",
            pattern=r"\bhttps?://[^\s\"']+",
            replacement="<VAR:URL>",
            priority=100,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="email",
            type="EMAIL",
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            replacement="<VAR:EMAIL>",
            priority=98,
        ),
        MaskSpec(
            name="windows_path",
            type="PATH",
            pattern=r"\b[A-Za-z]:\\(?:[^\\\s]+\\?)+",
            replacement="<VAR:PATH>",
            priority=95,
        ),
        MaskSpec(
            name="absolute_path",
            type="PATH",
            pattern=r"(?<!\S)/(?:[^/\s]+/)*[^/\s]+",
            replacement="<VAR:PATH>",
            priority=94,
        ),
        MaskSpec(
            name="long_hex_hash",
            type="HEX",
            pattern=r"\b(?:0x)?[0-9a-fA-F]{16,}\b",
            replacement="<VAR:HEX>",
            priority=90,
        ),
        MaskSpec(
            name="block_id",
            type="BLOCK_ID",
            pattern=r"\bblk_?-?\d+\b",
            replacement="<VAR:BLOCK_ID>",
            priority=88,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="request_id_assignment",
            type="REQUEST_ID",
            pattern=r"\brequest[_-]?id[=:]\s*([A-Za-z0-9_.:-]+)\b",
            value_group=1,
            replacement="<VAR:REQUEST_ID>",
            priority=86,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="session_id_assignment",
            type="SESSION_ID",
            pattern=r"\bsession[_-]?id[=:]\s*([A-Za-z0-9_.:-]+)\b",
            value_group=1,
            replacement="<VAR:SESSION_ID>",
            priority=84,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="pid_assignment",
            type="PID",
            pattern=r"\bpid[=:]\s*(\d+)\b",
            value_group=1,
            replacement="<VAR:PID>",
            priority=82,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="port_assignment",
            type="PORT",
            pattern=r"\bport[=:]\s*(\d{2,5})\b",
            value_group=1,
            replacement="<VAR:PORT>",
            priority=80,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="duration_with_unit",
            type="DURATION",
            pattern=r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds|m|min|mins|h|hr|hrs)\b",
            replacement="<VAR:DURATION>",
            priority=78,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="quoted_string",
            type="QUOTED_STRING",
            pattern=r"\"[^\"\r\n]{1,200}\"|'[^'\r\n]{1,200}'",
            replacement="<VAR:QUOTED_STRING>",
            priority=70,
        ),
    ]


def aggressive_masks() -> list[MaskSpec]:
    return conservative_masks() + [
        MaskSpec(
            name="float",
            type="FLOAT",
            pattern=r"\b\d+\.\d+\b",
            replacement="<VAR:FLOAT>",
            priority=45,
        ),
        MaskSpec(
            name="number",
            type="NUMBER",
            pattern=r"\b\d+\b",
            replacement="<VAR:NUMBER>",
            priority=40,
        ),
        MaskSpec(
            name="short_hex",
            type="HEX",
            pattern=r"\b(?:0x)?[0-9a-fA-F]{8,15}\b",
            replacement="<VAR:HEX>",
            priority=35,
        ),
        MaskSpec(
            name="username_after_user",
            type="USERNAME",
            pattern=r"\buser(?:name)?\s+([A-Za-z_][A-Za-z0-9_.-]{2,})\b",
            value_group=1,
            replacement="<VAR:USERNAME>",
            priority=34,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="bare_filename",
            type="FILENAME",
            pattern=r"\b[\w.-]+\.(?:log|txt|json|xml|yaml|yml|conf|cfg|ini|py|java|go|js|ts)\b",
            replacement="<VAR:FILENAME>",
            priority=32,
            flags=["IGNORECASE"],
        ),
        MaskSpec(
            name="generic_id",
            type="GENERIC_ID",
            pattern=r"\b[A-Za-z_][A-Za-z0-9_.-]{5,}\b",
            replacement="<VAR:GENERIC_ID>",
            priority=10,
        ),
    ]


def get_rule_masks(rule_mode: str = "conservative") -> list[MaskSpec]:
    if rule_mode == "conservative":
        return conservative_masks()
    if rule_mode == "aggressive":
        return aggressive_masks()
    raise ValueError("rule_mode must be 'conservative' or 'aggressive'")
