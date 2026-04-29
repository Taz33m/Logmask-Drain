"""Optional API LLM candidate-mask synthesis backend."""

from __future__ import annotations

from typing import Protocol

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
from ..prompts import API_LLM_MASKS_PROMPT_VERSION, api_llm_masks_system_prompt, api_llm_masks_user_prompt
from ..regex_validation import VALIDATOR_VERSION, validate_masks
from .rules import get_rule_masks


class CandidateProvider(Protocol):
    provider_name: str

    def generate_candidates(
        self,
        sample_lines: list[str],
        *,
        model: str,
        prompt_version: str,
        temperature: float,
        max_candidates: int,
        timeout_seconds: float,
        max_retries: int,
    ) -> CandidateMaskBundle:
        """Return parsed candidate masks. Providers must not return runtime bundles."""


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, client=None):
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAI API synthesis requires the optional dependency: "
                    "pip install 'logmask-drain[api-llm]'"
                ) from exc
            client = OpenAI()
        self.client = client

    def generate_candidates(
        self,
        sample_lines: list[str],
        *,
        model: str,
        prompt_version: str,
        temperature: float,
        max_candidates: int,
        timeout_seconds: float,
        max_retries: int,
    ) -> CandidateMaskBundle:
        if prompt_version != API_LLM_MASKS_PROMPT_VERSION:
            raise ValueError(f"unsupported prompt_version: {prompt_version}")
        last_error: Exception | None = None
        for _attempt in range(max_retries + 1):
            try:
                response = self.client.responses.parse(
                    model=model,
                    input=[
                        {"role": "system", "content": api_llm_masks_system_prompt(max_candidates=max_candidates)},
                        {"role": "user", "content": api_llm_masks_user_prompt(sample_lines)},
                    ],
                    temperature=temperature,
                    text_format=CandidateMaskBundle,
                    timeout=timeout_seconds,
                )
                break
            except Exception as exc:  # pragma: no cover - SDK-specific exception hierarchy.
                last_error = exc
        else:
            raise RuntimeError(f"OpenAI candidate-mask synthesis failed: {last_error}") from last_error
        for output in response.output:
            if output.type != "message":
                continue
            for item in output.content:
                if item.type == "refusal":
                    raise RuntimeError(f"OpenAI refused candidate-mask synthesis: {item.refusal}")
                parsed = getattr(item, "parsed", None)
                if parsed is not None:
                    return parsed
        raise RuntimeError("OpenAI response did not contain parsed candidate masks")


def get_api_provider(provider: str) -> CandidateProvider:
    if provider == "openai":
        return OpenAIProvider()
    raise ValueError("v0.3 supports only --provider openai")


def _base_masks_for_mode(base_rules: str) -> list[MaskSpec]:
    if base_rules == "none":
        return []
    if base_rules in {"conservative", "aggressive"}:
        return get_rule_masks(base_rules)
    raise ValueError("--base-rules must be none, conservative, or aggressive")


def synthesize_api_llm_bundle(
    sample_lines: list[str],
    *,
    provider: CandidateProvider,
    model: str,
    prompt_version: str = API_LLM_MASKS_PROMPT_VERSION,
    temperature: float = 0,
    max_candidates: int = 32,
    provider_timeout_seconds: float = 60,
    provider_max_retries: int = 0,
    base_rules: str = "none",
    strict: bool = True,
    include_raw_examples: bool = False,
    allow_new_types: bool = False,
    sampler: str = "manual",
) -> tuple[MaskBundle, dict]:
    base_accepted, base_rejected = validate_masks(
        _base_masks_for_mode(base_rules),
        sample_lines,
        strict=strict,
        include_raw_examples=include_raw_examples,
    )
    candidate_bundle = provider.generate_candidates(
        sample_lines,
        model=model,
        prompt_version=prompt_version,
        temperature=temperature,
        max_candidates=max_candidates,
        timeout_seconds=provider_timeout_seconds,
        max_retries=provider_max_retries,
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
            backend="api-llm",
            provider=provider.provider_name,
            model=model,
            prompt_version=prompt_version,
            temperature=temperature,
            params={
                "base_rules": base_rules,
                "max_candidates": max_candidates,
                "provider_timeout_seconds": provider_timeout_seconds,
                "provider_max_retries": provider_max_retries,
                "schema_version": candidate_bundle.candidate_schema_version,
                "allow_new_types": allow_new_types,
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
        "model": model,
        "prompt_version": prompt_version,
        "base_rules": base_rules,
        "provider_timeout_seconds": provider_timeout_seconds,
        "provider_max_retries": provider_max_retries,
        "base_rule_accept_count": len(base_accepted),
        "base_rule_reject_count": len(base_rejected),
        "accepted_runtime_mask_count": len(accepted),
        "rejected_runtime_mask_count": len(rejected),
        "candidate_validation": model_to_data(candidate_result.summary),
    }
    return bundle, report
