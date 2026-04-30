import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.io import load_json, load_mask_bundle, runtime_mask_sha256
from logmask_drain.models import CandidateMask, CandidateMaskBundle
from logmask_drain.prompts import LOCAL_LLM_MASKS_PROMPT_VERSION, local_llm_masks_prompt
from logmask_drain.synthesis_backends.local_llm import (
    LlamaCppProvider,
    LocalCandidateProvider,
    parse_candidate_response,
    synthesize_local_llm_bundle,
)


class FakeLocalProvider:
    provider_name = "fake-local"

    def __init__(self, bundle: CandidateMaskBundle | None = None, error: Exception | None = None):
        self.bundle = bundle or CandidateMaskBundle()
        self.error = error
        self.calls = []

    def generate_candidates(
        self,
        sample_lines,
        *,
        model_path,
        prompt_version,
        temperature,
        max_candidates,
        timeout_seconds,
        ctx_size,
        max_tokens,
    ):
        self.calls.append(
            {
                "model_path": model_path,
                "prompt_version": prompt_version,
                "temperature": temperature,
                "max_candidates": max_candidates,
                "timeout_seconds": timeout_seconds,
                "ctx_size": ctx_size,
                "max_tokens": max_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return self.bundle


def test_local_llm_accepts_valid_candidate_and_records_metadata(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    provider = FakeLocalProvider(
        CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="trace_id_assignment",
                    type="TRACE_ID",
                    pattern=r"\btrace[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:TRACE_ID>",
                    flags=["IGNORECASE"],
                )
            ]
        )
    )

    bundle, report = synthesize_local_llm_bundle(
        ["INFO trace_id=abc-123 completed"],
        provider=provider,
        model_path=model_path,
    )

    assert bundle.generator.backend == "local-llm"
    assert bundle.generator.provider == "fake-local"
    assert bundle.generator.model == "model.gguf"
    assert bundle.generator.prompt_version == LOCAL_LLM_MASKS_PROMPT_VERSION
    assert bundle.candidate_validation.accepted_count == 1
    assert bundle.masks[0].validation.examples[0].value is None
    assert bundle.generator.params["local_sample"]["line_count"] == 1
    assert report["candidate_validation"]["accepted_count"] == 1
    assert provider.calls[0]["timeout_seconds"] == 120
    assert provider.calls[0]["ctx_size"] == 4096
    assert provider.calls[0]["max_tokens"] == 2048
    assert runtime_mask_sha256(bundle)


def test_local_llm_hybrid_preserves_base_rules_and_adds_accepted_candidates(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    provider = FakeLocalProvider(
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

    bundle, report = synthesize_local_llm_bundle(
        ["2024-01-15 10:30:45 INFO trace_id=abc-123 from 10.0.0.1"],
        provider=provider,
        model_path=model_path,
        base_rules="conservative",
    )

    names = {mask.name for mask in bundle.masks}
    assert "datetime_iso" in names
    assert "ipv4" in names
    assert "trace_id_assignment" in names
    assert report["base_rule_accept_count"] > 0


def test_local_llm_large_sample_fails_before_provider_call(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    provider = FakeLocalProvider()

    with pytest.raises(ValueError, match="Use logmask sample first"):
        synthesize_local_llm_bundle(["line"] * 201, provider=provider, model_path=model_path)

    assert provider.calls == []


def test_local_llm_large_sample_override_records_provenance(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    provider = FakeLocalProvider()

    bundle, report = synthesize_local_llm_bundle(
        ["line"] * 201,
        provider=provider,
        model_path=model_path,
        allow_large_local_sample=True,
    )

    assert provider.calls
    assert bundle.generator.params["local_sample"]["line_count"] == 201
    assert bundle.generator.params["local_sample"]["large_sample_override"] is True
    assert report["local_sample"]["large_sample_override"] is True


def test_parse_candidate_response_extracts_wrapped_json():
    response = """
Some preamble that a small local model should not have produced.
{"candidate_schema_version":"0.1","candidates":[{"name":"trace","type":"TRACE_ID","pattern":"\\\\btrace=([A-Za-z0-9]+)\\\\b","value_group":1,"replacement":"<VAR:TRACE_ID>"}]}
trailing text
"""

    bundle = parse_candidate_response(response)

    assert bundle.candidates[0].name == "trace"


def test_parse_candidate_response_prefers_last_valid_object_when_prompt_is_echoed():
    response = """
Echoed prompt example:
{"candidate_schema_version":"0.1","candidates":[{"name":"example","type":"REQUEST_ID","pattern":"request_id=([A-Za-z0-9]+)","value_group":1,"replacement":"<VAR:REQUEST_ID>"}]}
Actual answer:
{"candidate_schema_version":"0.1","candidates":[{"name":"trace","type":"TRACE_ID","pattern":"trace_id=([A-Za-z0-9]+)","value_group":1,"replacement":"<VAR:TRACE_ID>"}]}
"""

    bundle = parse_candidate_response(response)

    assert bundle.candidates[0].name == "trace"


def test_parse_candidate_response_rejects_malformed_json():
    with pytest.raises(ValueError, match="JSON"):
        parse_candidate_response("no useful object here")


def test_llama_cpp_provider_runs_cli_and_parses_candidates(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    seen = {}

    def fake_run(command, *, check, capture_output, text, timeout):
        seen["command"] = command
        seen["timeout"] = timeout
        prompt_path = Path(command[command.index("-f") + 1])
        assert "Propose at most 5 candidate masks." in prompt_path.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"candidate_schema_version":"0.1","candidates":[]}',
            stderr="",
        )

    monkeypatch.setattr("logmask_drain.synthesis_backends.local_llm.shutil.which", lambda executable: "/fake/llama-cli")
    monkeypatch.setattr("logmask_drain.synthesis_backends.local_llm.subprocess.run", fake_run)

    provider = LlamaCppProvider(llama_cli="llama-cli")
    bundle = provider.generate_candidates(
        ["INFO completed"],
        model_path=model_path,
        prompt_version=LOCAL_LLM_MASKS_PROMPT_VERSION,
        temperature=0,
        max_candidates=5,
        timeout_seconds=9,
        ctx_size=2048,
        max_tokens=512,
    )

    assert bundle.candidates == []
    assert seen["command"][:4] == ["/fake/llama-cli", "-m", str(model_path), "-f"]
    assert "--temp" in seen["command"]
    assert seen["timeout"] == 9


def test_llama_cpp_provider_missing_executable_message(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    monkeypatch.setattr("logmask_drain.synthesis_backends.local_llm.shutil.which", lambda executable: None)

    with pytest.raises(RuntimeError, match="llama-cli"):
        LlamaCppProvider().generate_candidates(
            ["INFO completed"],
            model_path=model_path,
            prompt_version=LOCAL_LLM_MASKS_PROMPT_VERSION,
            temperature=0,
            max_candidates=5,
            timeout_seconds=9,
            ctx_size=2048,
            max_tokens=512,
        )


def test_local_prompt_snapshot_contains_json_and_safety_instructions():
    prompt = local_llm_masks_prompt(["INFO trace_id=abc"], max_candidates=3)

    assert LOCAL_LLM_MASKS_PROMPT_VERSION == "local_llm_masks_v1"
    assert '"candidate_schema_version": "0.1"' in prompt
    assert "Propose at most 3 candidate masks." in prompt
    assert "Do not create masks for log levels" in prompt
    assert "Return one JSON object only" in prompt


def test_cli_local_llm_writes_bundle_and_candidate_report(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    provider = FakeLocalProvider(
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
    monkeypatch.setattr("logmask_drain.cli.get_local_provider", lambda provider_name, llama_cli="llama-cli": provider)
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
            "local-llm",
            "--model-path",
            str(model_path),
            "--candidate-report",
            str(report),
            "--local-timeout-seconds",
            "8",
            "--ctx-size",
            "2048",
            "--max-tokens",
            "512",
            "--out",
            str(masks),
        ],
    )

    assert result.exit_code == 0, result.output
    bundle = load_mask_bundle(masks)
    data = load_json(report)
    assert bundle.generator.backend == "local-llm"
    assert bundle.generator.provider == "fake-local"
    assert bundle.candidate_validation.accepted_count == 1
    assert data["timeout_seconds"] == 8
    assert data["ctx_size"] == 2048
    assert data["max_tokens"] == 512
    assert provider.calls[0]["prompt_version"] == LOCAL_LLM_MASKS_PROMPT_VERSION


def test_cli_local_llm_large_sample_fails_before_provider_lookup(monkeypatch, tmp_path):
    called = False

    def fail_if_called(provider_name: str, llama_cli: str = "llama-cli") -> LocalCandidateProvider:
        nonlocal called
        called = True
        return FakeLocalProvider()

    monkeypatch.setattr("logmask_drain.cli.get_local_provider", fail_if_called)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model", encoding="utf-8")
    sample = tmp_path / "huge.log"
    sample.write_text("\n".join(f"line {index}" for index in range(201)) + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "synthesize",
            str(sample),
            "--backend",
            "local-llm",
            "--model-path",
            str(model_path),
            "--out",
            str(tmp_path / "masks.json"),
        ],
    )

    assert result.exit_code != 0
    assert "Use logmask sample first" in result.output
    assert called is False


def test_cli_local_llm_requires_model_path(tmp_path):
    sample = tmp_path / "sample.log"
    sample.write_text("INFO completed\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["synthesize", str(sample), "--backend", "local-llm", "--out", str(tmp_path / "masks.json")],
    )

    assert result.exit_code != 0
    assert "model-path" in result.output
