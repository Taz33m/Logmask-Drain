import pytest
from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.io import load_json, load_mask_bundle, runtime_mask_sha256
from logmask_drain.models import CandidateMask, CandidateMaskBundle
from logmask_drain.prompts import API_LLM_MASKS_PROMPT_VERSION, api_llm_masks_system_prompt
from logmask_drain.synthesis_backends.api_llm import CandidateProvider, synthesize_api_llm_bundle


class FakeProvider:
    provider_name = "fake"

    def __init__(self, bundle: CandidateMaskBundle | None = None, error: Exception | None = None):
        self.bundle = bundle or CandidateMaskBundle()
        self.error = error
        self.calls = []

    def generate_candidates(
        self,
        sample_lines,
        *,
        model,
        prompt_version,
        temperature,
        max_candidates,
        timeout_seconds,
        max_retries,
    ):
        self.calls.append(
            {
                "model": model,
                "prompt_version": prompt_version,
                "temperature": temperature,
                "max_candidates": max_candidates,
                "timeout_seconds": timeout_seconds,
                "max_retries": max_retries,
            }
        )
        if self.error is not None:
            raise self.error
        return self.bundle


def test_api_llm_accepts_valid_candidate_and_records_metadata():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_id_assignment",
                    type="TRACE_ID",
                    pattern=r"\btrace[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                    priority=82,
                    flags=["IGNORECASE"],
                )
            ]
        )
    )

    bundle, report = synthesize_api_llm_bundle(
        ["INFO trace_id=abc-123 completed"],
        provider=provider,
        model="test-model",
    )

    assert bundle.generator.backend == "api-llm"
    assert bundle.generator.provider == "fake"
    assert bundle.generator.model == "test-model"
    assert bundle.generator.prompt_version == "api_llm_masks_v1"
    assert bundle.candidate_validation.accepted_count == 1
    assert report["candidate_validation"]["accepted_count"] == 1
    assert report["candidates"][0]["overlap_count"] == 0
    assert bundle.masks[0].validation.examples[0].value is None
    assert provider.calls[0]["timeout_seconds"] == 60
    assert provider.calls[0]["max_retries"] == 0
    assert runtime_mask_sha256(bundle)


def test_api_llm_rejects_malformed_provider_response():
    provider = FakeProvider(error=ValueError("malformed candidate JSON"))

    with pytest.raises(ValueError, match="malformed candidate JSON"):
        synthesize_api_llm_bundle(["INFO trace_id=abc-123"], provider=provider, model="test-model")


def test_api_llm_rejects_unsafe_overbroad_and_log_level_candidates():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(name="bad_regex", type="TRACE_ID", pattern=r"(.+)+", replacement="<VAR:TRACE_ID>"),
                CandidateMask(name="full_line", type="GENERIC_ID", pattern=r".+", replacement="<VAR:GENERIC_ID>"),
                CandidateMask(name="level", type="LOG_LEVEL", pattern=r"\bINFO\b", replacement="<VAR:LOG_LEVEL>"),
            ]
        )
    )

    bundle, report = synthesize_api_llm_bundle(["INFO trace_id=abc-123"], provider=provider, model="test-model")

    assert not bundle.masks
    reasons = {item["reason"] for item in report["candidates"]}
    assert "known catastrophic regex shape" in reasons
    assert "broad_full_line_capture" in reasons
    assert "log_level_mask" in reasons
    assert report["rejection_examples"]["log_level_mask"][0]["name"] == "level"


def test_api_llm_rejects_unknown_type_unless_allowed():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="custom_assignment",
                    type="CUSTOM_THING",
                    pattern=r"\bcustom=([A-Za-z0-9_-]+)\b",
                    value_group=1,
                    replacement="<VAR:CUSTOM_THING>",
                )
            ]
        )
    )

    rejected_bundle, _ = synthesize_api_llm_bundle(["custom=abc"], provider=provider, model="test-model")
    accepted_bundle, _ = synthesize_api_llm_bundle(
        ["custom=abc"],
        provider=provider,
        model="test-model",
        allow_new_types=True,
    )

    assert not rejected_bundle.masks
    assert accepted_bundle.masks[0].type == "CUSTOM_THING"


def test_api_llm_duplicate_runtime_equivalent_against_base_rules_is_rejected():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="another_ipv4",
                    type="IP",
                    pattern=r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)",
                    replacement="<VAR:IP>",
                    priority=105,
                )
            ]
        )
    )

    bundle, report = synthesize_api_llm_bundle(
        ["INFO from 10.0.0.1"],
        provider=provider,
        model="test-model",
        base_rules="conservative",
    )

    assert any(mask.name == "ipv4" for mask in bundle.masks)
    candidate = report["candidates"][0]
    assert candidate["status"] == "rejected"
    assert candidate["reason"] == "duplicate_runtime_equivalent"


def test_api_llm_hybrid_adds_only_accepted_llm_candidates_to_base_rules():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_id_assignment",
                    type="TRACE_ID",
                    pattern=r"\btrace[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                    flags=["IGNORECASE"],
                ),
                CandidateMask(name="log_level", type="LOG_LEVEL", pattern=r"\bINFO\b", replacement="<VAR:LOG_LEVEL>"),
            ]
        )
    )

    bundle, report = synthesize_api_llm_bundle(
        ["2024-01-15 10:30:45 INFO trace_id=abc-123 from 10.0.0.1"],
        provider=provider,
        model="test-model",
        base_rules="conservative",
    )

    names = {mask.name for mask in bundle.masks}
    assert "datetime_iso" in names
    assert "ipv4" in names
    assert "trace_id_assignment" in names
    assert "log_level" not in names
    assert report["candidate_validation"]["accepted_count"] == 1
    assert report["candidate_validation"]["rejected_count"] == 1


def test_api_llm_same_response_has_stable_runtime_hash():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_id_assignment",
                    type="TRACE_ID",
                    pattern=r"\btrace[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                )
            ]
        )
    )

    first, _ = synthesize_api_llm_bundle(["trace_id=abc"], provider=provider, model="test-model")
    second, _ = synthesize_api_llm_bundle(["trace_id=abc"], provider=provider, model="test-model")

    assert runtime_mask_sha256(first) == runtime_mask_sha256(second)


def test_api_llm_provider_timeout_retry_metadata_is_recorded():
    provider = FakeProvider(CandidateMaskBundle())

    bundle, report = synthesize_api_llm_bundle(
        ["INFO completed"],
        provider=provider,
        model="test-model",
        provider_timeout_seconds=12.5,
        provider_max_retries=2,
    )

    assert provider.calls[0]["timeout_seconds"] == 12.5
    assert provider.calls[0]["max_retries"] == 2
    assert bundle.generator.params["provider_timeout_seconds"] == 12.5
    assert bundle.generator.params["provider_max_retries"] == 2
    assert report["provider_timeout_seconds"] == 12.5
    assert report["provider_max_retries"] == 2


def test_api_llm_rejects_adversarial_placeholder_key_and_duplicate_names():
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_bad_placeholder",
                    type="TRACE_ID",
                    pattern=r"\btrace_id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:REQUEST_ID>",
                ),
                CandidateMask(
                    name="trace_includes_key",
                    type="TRACE_ID",
                    pattern=r"\btrace_id=[A-Za-z0-9_.:-]+\b",
                    replacement="<VAR:TRACE_ID>",
                ),
                CandidateMask(
                    name="trace_dupe",
                    type="TRACE_ID",
                    pattern=r"\btrace_id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                ),
                CandidateMask(
                    name="trace_dupe",
                    type="SPAN_ID",
                    pattern=r"\bspan_id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:SPAN_ID>",
                ),
            ]
        )
    )

    bundle, report = synthesize_api_llm_bundle(
        ["INFO trace_id=abc-123 span_id=def-456"],
        provider=provider,
        model="test-model",
    )

    reasons = [item["reason"] for item in report["candidates"] if item["status"] == "rejected"]
    assert "placeholder_type_mismatch" in reasons
    assert "selected_value_contains_static_key" in reasons
    assert "duplicate_name" in reasons
    assert [mask.name for mask in bundle.masks] == ["trace_dupe"]


def test_prompt_snapshot_contains_safety_instructions():
    prompt = api_llm_masks_system_prompt(max_candidates=7)

    assert API_LLM_MASKS_PROMPT_VERSION == "api_llm_masks_v1"
    assert "Propose at most 7 candidate masks." in prompt
    assert "preserve the key and use value_group" in prompt
    assert "Do not create masks for log levels" in prompt
    assert "Do not include raw sensitive examples" in prompt


def test_cli_api_llm_writes_bundle_and_candidate_report(monkeypatch, tmp_path):
    provider = FakeProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_id_assignment",
                    type="TRACE_ID",
                    pattern=r"\btrace[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                )
            ]
        )
    )
    monkeypatch.setattr("logmask_drain.cli.get_api_provider", lambda provider_name: provider)
    sample = tmp_path / "sample.log"
    masks = tmp_path / "masks.json"
    report = tmp_path / "candidates.json"
    sample.write_text("INFO trace_id=abc-123 completed\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "synthesize",
            str(sample),
            "--backend",
            "api-llm",
            "--provider",
            "openai",
            "--model",
            "test-model",
            "--candidate-report",
            str(report),
            "--provider-timeout-seconds",
            "9",
            "--provider-max-retries",
            "1",
            "--out",
            str(masks),
        ],
    )

    assert result.exit_code == 0, result.output
    bundle = load_mask_bundle(masks)
    data = load_json(report)
    assert bundle.generator.provider == "fake"
    assert bundle.candidate_validation.accepted_count == 1
    assert data["candidates"][0]["status"] == "accepted"
    assert "examples_observed" not in data["candidates"][0]
    assert data["provider_timeout_seconds"] == 9
    assert data["provider_max_retries"] == 1


def test_cli_api_llm_missing_optional_dependency_message(monkeypatch, tmp_path):
    def raise_missing(provider_name: str) -> CandidateProvider:
        raise RuntimeError("OpenAI API synthesis requires the optional dependency")

    monkeypatch.setattr("logmask_drain.cli.get_api_provider", raise_missing)
    sample = tmp_path / "sample.log"
    sample.write_text("INFO trace_id=abc-123 completed\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["synthesize", str(sample), "--backend", "api-llm", "--out", str(tmp_path / "masks.json")],
    )

    assert result.exit_code != 0
    assert "optional dependency" in result.output


def test_cli_candidate_schema_exports_pydantic_schema(tmp_path):
    out = tmp_path / "candidate-schema.json"

    result = CliRunner().invoke(app, ["candidate-schema", "--out", str(out)])

    assert result.exit_code == 0, result.output
    schema = load_json(out)
    assert schema["title"] == "CandidateMaskBundle"
    assert "candidates" in schema["properties"]
