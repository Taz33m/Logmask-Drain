import pytest

from logmask_drain.io import load_mask_bundle, model_to_data, runtime_mask_sha256
from logmask_drain.mask_bundle import create_mask_bundle
from logmask_drain.models import MaskSpec, MaskValidation
from logmask_drain.template_id import hash_template_id, template_hash


def test_allowed_flags_and_unsupported_flags():
    mask = MaskSpec(
        name="request",
        type="request_id",
        pattern=r"request_id=(\w+)",
        value_group=1,
        replacement="<VAR:REQUEST_ID>",
        priority=10,
        flags=["IGNORECASE", "IGNORECASE"],
    )

    assert mask.type == "REQUEST_ID"
    assert mask.flags == ["IGNORECASE"]

    try:
        MaskSpec(
            name="bad",
            type="BAD",
            pattern="x",
            replacement="<VAR:BAD>",
            flags=["DOTALL"],
        )
    except ValueError as exc:
        assert "DOTALL" in str(exc)
    else:
        raise AssertionError("unsupported flag should fail")


def test_runtime_hash_ignores_validation_metadata():
    base = MaskSpec(
        name="ipv4",
        type="IP",
        pattern="x",
        replacement="<VAR:IP>",
        priority=10,
    )
    with_validation = base.model_copy(
        update={"validation": MaskValidation(status="accepted", matched_span_count=1)}
    )

    assert runtime_mask_sha256([base]) == runtime_mask_sha256([with_validation])


def test_runtime_hash_changes_for_runtime_fields_only():
    base = MaskSpec(
        name="ipv4",
        type="IP",
        pattern="x",
        replacement="<VAR:IP>",
        priority=10,
    )
    changed_pattern = base.model_copy(update={"pattern": "y"})
    changed_replacement = base.model_copy(update={"replacement": "<VAR:OTHER>"})

    assert runtime_mask_sha256([base]) != runtime_mask_sha256([changed_pattern])
    assert runtime_mask_sha256([base]) != runtime_mask_sha256([changed_replacement])


def test_template_hash_is_stable_over_whitespace():
    assert template_hash("a   b") == template_hash("a b")


def test_hash_template_id_is_derived_from_template_hash():
    hash_value = template_hash("User <VAR:ID>")
    assert hash_template_id(hash_value).startswith("T")
    assert hash_template_id(hash_value) == hash_template_id(hash_value)


def test_yaml_mask_bundle_loading_uses_optional_safe_loader(tmp_path):
    yaml = pytest.importorskip("yaml")
    bundle = create_mask_bundle(
        [MaskSpec(name="ip", type="IP", pattern=r"10\.0\.0\.1", replacement="<VAR:IP>")],
        ["from 10.0.0.1"],
        backend="rules",
    )
    path = tmp_path / "masks.yaml"
    path.write_text(yaml.safe_dump(model_to_data(bundle), sort_keys=True), encoding="utf-8")

    loaded = load_mask_bundle(path)

    assert loaded.masks[0].name == "ip"
    assert loaded.masks[0].validation.examples[0].value is None
