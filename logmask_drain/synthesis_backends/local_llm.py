"""Optional local LLM candidate-mask synthesis backend."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ..candidate_validation import validate_candidate_masks
from ..io import model_to_data, sha256_text
from ..mask_bundle import utc_now_iso
from ..models import (
    BundleValidationSummary,
    CandidateMaskBundle,
    GeneratorMetadata,
    MaskBundle,
    MaskSpec,
    SourceMetadata,
)
from ..prompts import LOCAL_LLM_MASKS_PROMPT_VERSION, local_llm_masks_prompt
from ..regex_validation import VALIDATOR_VERSION, validate_masks
from .rules import get_rule_masks


DEFAULT_MAX_LOCAL_SAMPLE_LINES = 200
DEFAULT_MAX_LOCAL_SAMPLE_CHARS = 100_000


def local_sample_metadata(sample_lines: list[str], *, allow_large_local_sample: bool = False) -> dict[str, int | bool]:
    sample_text = "\n".join(sample_lines)
    return {
        "line_count": len(sample_lines),
        "char_count": len(sample_text),
        "large_sample_override": allow_large_local_sample,
    }


def validate_local_sample_limits(
    sample_lines: list[str],
    *,
    max_local_sample_lines: int = DEFAULT_MAX_LOCAL_SAMPLE_LINES,
    max_local_sample_chars: int = DEFAULT_MAX_LOCAL_SAMPLE_CHARS,
    allow_large_local_sample: bool = False,
) -> dict[str, int | bool]:
    if max_local_sample_lines <= 0:
        raise ValueError("max_local_sample_lines must be positive")
    if max_local_sample_chars <= 0:
        raise ValueError("max_local_sample_chars must be positive")
    metadata = local_sample_metadata(sample_lines, allow_large_local_sample=allow_large_local_sample)
    if allow_large_local_sample:
        return metadata
    line_count = int(metadata["line_count"])
    char_count = int(metadata["char_count"])
    if line_count > max_local_sample_lines or char_count > max_local_sample_chars:
        raise ValueError(
            "Local LLM synthesis would prompt with "
            f"{line_count:,} lines / {char_count:,} chars of logs. "
            f"Limit is {max_local_sample_lines:,} lines / {max_local_sample_chars:,} chars. "
            "Use logmask sample first, or pass --allow-large-local-sample explicitly."
        )
    return metadata


class LocalCandidateProvider(Protocol):
    provider_name: str

    def generate_candidates(
        self,
        sample_lines: list[str],
        *,
        model_path: Path,
        prompt_version: str,
        temperature: float,
        max_candidates: int,
        timeout_seconds: float,
        ctx_size: int,
        max_tokens: int,
    ) -> CandidateMaskBundle:
        """Return parsed candidate masks. Providers must not return runtime bundles."""


def _extract_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    starts = [index for index, char in enumerate(text) if char == "{"]
    if not starts:
        raise ValueError("local LLM response did not contain a JSON object")

    for start in starts:
        in_string = False
        escaped = False
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[start : index + 1])
                    break
    if not objects:
        raise ValueError("local LLM response contained incomplete JSON")
    return objects


def parse_candidate_response(text: str) -> CandidateMaskBundle:
    try:
        return CandidateMaskBundle.model_validate_json(text)
    except (ValidationError, ValueError):
        pass

    last_json_error: Exception | None = None
    last_schema_error: Exception | None = None
    for candidate_json in reversed(_extract_json_objects(text)):
        try:
            data = json.loads(candidate_json)
        except json.JSONDecodeError as exc:
            last_json_error = exc
            continue
        try:
            return CandidateMaskBundle.model_validate(data)
        except ValidationError as exc:
            last_schema_error = exc
    if last_schema_error is not None:
        raise ValueError(f"local LLM response did not match candidate schema: {last_schema_error}") from last_schema_error
    if last_json_error is not None:
        raise ValueError(f"local LLM response did not contain valid JSON: {last_json_error}") from last_json_error
    raise ValueError("local LLM response did not contain candidate-mask JSON")


class LlamaCppProvider:
    provider_name = "llama-cpp"

    def __init__(self, *, llama_cli: str = "llama-cli"):
        self.llama_cli = llama_cli

    def generate_candidates(
        self,
        sample_lines: list[str],
        *,
        model_path: Path,
        prompt_version: str,
        temperature: float,
        max_candidates: int,
        timeout_seconds: float,
        ctx_size: int,
        max_tokens: int,
    ) -> CandidateMaskBundle:
        if prompt_version != LOCAL_LLM_MASKS_PROMPT_VERSION:
            raise ValueError(f"unsupported prompt_version: {prompt_version}")
        if not model_path.exists():
            raise ValueError(f"local model path does not exist: {model_path}")
        executable = shutil.which(self.llama_cli)
        if executable is None:
            raise RuntimeError(
                "local LLM synthesis requires llama.cpp's llama-cli executable; "
                "install llama.cpp or pass --llama-cli /path/to/llama-cli."
            )

        prompt = local_llm_masks_prompt(sample_lines, max_candidates=max_candidates)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".prompt.txt") as prompt_file:
            prompt_file.write(prompt)
            prompt_file.flush()
            command = [
                executable,
                "-m",
                str(model_path),
                "-f",
                prompt_file.name,
                "-n",
                str(max_tokens),
                "-c",
                str(ctx_size),
                "--temp",
                str(temperature),
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"local LLM synthesis timed out after {timeout_seconds:g} seconds") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            message = stderr if stderr else f"llama-cli exited with code {completed.returncode}"
            raise RuntimeError(f"local LLM synthesis failed: {message}")
        return parse_candidate_response(completed.stdout)


def get_local_provider(provider: str, *, llama_cli: str = "llama-cli") -> LocalCandidateProvider:
    if provider == "llama-cpp":
        return LlamaCppProvider(llama_cli=llama_cli)
    raise ValueError("v0.6 supports only --local-provider llama-cpp")


def _base_masks_for_mode(base_rules: str) -> list[MaskSpec]:
    if base_rules == "none":
        return []
    if base_rules in {"conservative", "aggressive"}:
        return get_rule_masks(base_rules)
    raise ValueError("--base-rules must be none, conservative, or aggressive")


def synthesize_local_llm_bundle(
    sample_lines: list[str],
    *,
    provider: LocalCandidateProvider,
    model_path: Path,
    prompt_version: str = LOCAL_LLM_MASKS_PROMPT_VERSION,
    temperature: float = 0,
    max_candidates: int = 32,
    timeout_seconds: float = 120,
    ctx_size: int = 4096,
    max_tokens: int = 2048,
    max_local_sample_lines: int = DEFAULT_MAX_LOCAL_SAMPLE_LINES,
    max_local_sample_chars: int = DEFAULT_MAX_LOCAL_SAMPLE_CHARS,
    allow_large_local_sample: bool = False,
    base_rules: str = "none",
    strict: bool = True,
    include_raw_examples: bool = False,
    allow_new_types: bool = False,
    sampler: str = "manual",
) -> tuple[MaskBundle, dict]:
    local_sample = validate_local_sample_limits(
        sample_lines,
        max_local_sample_lines=max_local_sample_lines,
        max_local_sample_chars=max_local_sample_chars,
        allow_large_local_sample=allow_large_local_sample,
    )
    base_accepted, base_rejected = validate_masks(
        _base_masks_for_mode(base_rules),
        sample_lines,
        strict=strict,
        include_raw_examples=include_raw_examples,
    )
    candidate_bundle = provider.generate_candidates(
        sample_lines,
        model_path=model_path,
        prompt_version=prompt_version,
        temperature=temperature,
        max_candidates=max_candidates,
        timeout_seconds=timeout_seconds,
        ctx_size=ctx_size,
        max_tokens=max_tokens,
    )
    candidates = candidate_bundle.candidates[:max_candidates]
    candidate_result = validate_candidate_masks(
        candidates,
        sample_lines,
        base_masks=base_accepted,
        allow_new_types=allow_new_types,
        strict=strict,
        include_raw_examples=include_raw_examples,
    )
    sample_text = "\n".join(sample_lines)
    accepted = base_accepted + candidate_result.accepted
    rejected = base_rejected + candidate_result.rejected
    bundle = MaskBundle(
        created_at=utc_now_iso(),
        source=SourceMetadata(
            sample_sha256=sha256_text(sample_text),
            sample_size=len(sample_lines),
            sampler=sampler,
        ),
        generator=GeneratorMetadata(
            backend="local-llm",
            provider=provider.provider_name,
            model=model_path.name,
            prompt_version=prompt_version,
            temperature=temperature,
            params={
                "base_rules": base_rules,
                "max_candidates": max_candidates,
                "timeout_seconds": timeout_seconds,
                "ctx_size": ctx_size,
                "max_tokens": max_tokens,
                "local_sample": local_sample,
                "schema_version": candidate_bundle.candidate_schema_version,
                "allow_new_types": allow_new_types,
                "model_path_name": model_path.name,
            },
        ),
        validation=BundleValidationSummary(
            validator_version=VALIDATOR_VERSION,
            strict=strict,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            examples_redacted=not include_raw_examples,
        ),
        candidate_validation=candidate_result.summary,
        masks=accepted,
        rejected_masks=rejected,
    )
    report = {
        **candidate_result.report,
        "provider": provider.provider_name,
        "model": model_path.name,
        "prompt_version": prompt_version,
        "base_rules": base_rules,
        "timeout_seconds": timeout_seconds,
        "ctx_size": ctx_size,
        "max_tokens": max_tokens,
        "local_sample": local_sample,
        "base_rule_accept_count": len(base_accepted),
        "base_rule_reject_count": len(base_rejected),
        "accepted_runtime_mask_count": len(accepted),
        "rejected_runtime_mask_count": len(rejected),
        "candidate_validation": model_to_data(candidate_result.summary),
    }
    return bundle, report
