from logmask_drain.masking import Masker
from logmask_drain.models import MaskSpec
from logmask_drain.regex_validation import validate_mask
from logmask_drain.synthesis_backends.rules import get_rule_masks


def test_value_group_preserves_static_context():
    mask = MaskSpec(
        name="request_id_assignment",
        type="REQUEST_ID",
        pattern=r"\brequest[_-]?id=([A-Za-z0-9_.:-]+)\b",
        value_group=1,
        replacement="<VAR:REQUEST_ID>",
        priority=80,
        flags=["IGNORECASE"],
    )
    masked = Masker([mask]).mask_line("INFO request_id=abc-123 done", 0)

    assert masked.masked == "INFO request_id=<VAR:REQUEST_ID> done"
    assert masked.variables[0].value == "abc-123"
    assert masked.variables[0].start == 16
    assert masked.variables[0].end == 23


def test_span_invariant_for_all_variables():
    masks = [
        MaskSpec(
            name="request_id_assignment",
            type="REQUEST_ID",
            pattern=r"\brequest[_-]?id=([A-Za-z0-9_.:-]+)\b",
            value_group=1,
            replacement="<VAR:REQUEST_ID>",
            priority=80,
        ),
        MaskSpec(
            name="ipv4",
            type="IP",
            pattern=r"192\.168\.1\.100",
            replacement="<VAR:IP>",
            priority=70,
        ),
    ]
    raw = "INFO request_id=abc-123 from 192.168.1.100"
    masked = Masker(masks).mask_line(raw, 0)

    for variable in masked.variables:
        assert raw[variable.start : variable.end] == variable.value


def test_overlap_resolution_uses_priority_before_length():
    high_priority = MaskSpec(
        name="value",
        type="ID",
        pattern=r"id=(abc)",
        value_group=1,
        replacement="<VAR:ID>",
        priority=100,
    )
    low_priority = MaskSpec(
        name="full",
        type="GENERIC",
        pattern=r"id=abc",
        replacement="<VAR:GENERIC>",
        priority=1,
    )

    masked = Masker([low_priority, high_priority]).mask_line("id=abc", 0)
    assert masked.masked == "id=<VAR:ID>"


def test_overlap_resolution_uses_length_then_earlier_start():
    longer = MaskSpec(
        name="longer",
        type="LONG",
        pattern=r"abcd",
        replacement="<VAR:LONG>",
        priority=10,
    )
    shorter = MaskSpec(
        name="shorter",
        type="SHORT",
        pattern=r"abc",
        replacement="<VAR:SHORT>",
        priority=10,
    )
    masked = Masker([shorter, longer]).mask_line("abcd", 0)
    assert masked.masked == "<VAR:LONG>"

    earlier = MaskSpec(
        name="earlier",
        type="EARLIER",
        pattern=r"abc",
        replacement="<VAR:EARLIER>",
        priority=10,
    )
    later = MaskSpec(
        name="later",
        type="LATER",
        pattern=r"bcd",
        replacement="<VAR:LATER>",
        priority=10,
    )
    masked = Masker([later, earlier]).mask_line("abcd", 0)
    assert masked.masked == "<VAR:EARLIER>d"


def test_log_levels_are_not_masked_by_default():
    masked = Masker(get_rule_masks("conservative")).mask_line("INFO WARN ERROR", 0)
    assert masked.masked == "INFO WARN ERROR"
    assert masked.variables == []


def test_missing_and_empty_value_group_rejected():
    missing_group = MaskSpec(
        name="missing",
        type="ID",
        pattern=r"id=(abc)",
        value_group=2,
        replacement="<VAR:ID>",
    )
    assert validate_mask(missing_group, ["id=abc"], strict=True).rejected is not None

    empty_group = MaskSpec(
        name="empty",
        type="ID",
        pattern=r"id=(abc)?",
        value_group=1,
        replacement="<VAR:ID>",
    )
    assert validate_mask(empty_group, ["id="], strict=True).rejected is not None
