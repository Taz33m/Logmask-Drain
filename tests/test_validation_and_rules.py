from logmask_drain.regex_validation import validate_mask
from logmask_drain.synthesis_backends.rules import get_rule_masks
from logmask_drain.models import MaskSpec, MaskValidation, ValidationExample


def test_validation_rejects_catastrophic_empty_and_broad_masks():
    catastrophic = MaskSpec(
        name="bad",
        type="BAD",
        pattern=r"(.+)+",
        replacement="<VAR:BAD>",
    )
    assert validate_mask(catastrophic, ["abc"], strict=True).rejected is not None

    empty = MaskSpec(
        name="empty",
        type="BAD",
        pattern=r".*",
        replacement="<VAR:BAD>",
    )
    assert validate_mask(empty, ["abc"], strict=True).rejected is not None

    broad = MaskSpec(
        name="broad",
        type="BAD",
        pattern=r"\S+",
        replacement="<VAR:BAD>",
    )
    assert validate_mask(broad, ["a b c d e f"] * 5, strict=True).rejected is not None


def test_redacted_examples_are_default():
    mask = MaskSpec(
        name="ip",
        type="IP",
        pattern=r"192\.168\.1\.100",
        replacement="<VAR:IP>",
    )
    result = validate_mask(mask, ["from 192.168.1.100"], strict=True)
    example = result.accepted.validation.examples[0]

    assert example.value is None
    assert example.sha256 is not None
    assert example.preview is None

    raw_result = validate_mask(mask, ["from 192.168.1.100"], strict=True, include_raw_examples=True)
    raw_example = raw_result.accepted.validation.examples[0]
    assert raw_example.value == "192.168.1.100"
    assert raw_example.preview is None


def test_existing_validation_examples_with_preview_still_load():
    validation = MaskValidation(
        status="accepted",
        examples=[ValidationExample(sha256="abc", length=4, preview="sec...")],
    )

    assert validation.examples[0].preview == "sec..."


def test_strict_validation_rejects_replacement_type_mismatch():
    mask = MaskSpec(
        name="ip",
        type="IP",
        pattern=r"10\.0\.0\.1",
        replacement="<VAR:ID>",
    )

    result = validate_mask(mask, ["from 10.0.0.1"], strict=True)
    assert result.rejected.reason == "replacement/type mismatch"


def test_conservative_rules_exclude_broad_masks_and_log_levels():
    names = {mask.name for mask in get_rule_masks("conservative")}
    types = {mask.type for mask in get_rule_masks("conservative")}

    assert "number" not in names
    assert "generic_id" not in names
    assert "LOG_LEVEL" not in types
