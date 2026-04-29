"""Pydantic models for mask bundles and parser output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_FLAGS = {"IGNORECASE", "MULTILINE", "ASCII"}
AllowedFlag = Literal["IGNORECASE", "MULTILINE", "ASCII"]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields to keep artifacts explicit."""

    model_config = ConfigDict(extra="forbid")


class ValidationExample(StrictModel):
    sha256: str | None = None
    length: int
    preview: str | None = None
    value: str | None = None


class MaskValidation(StrictModel):
    status: Literal["accepted", "rejected", "unvalidated"] = "unvalidated"
    matched_line_fraction: float = 0.0
    matched_span_count: int = 0
    unique_value_count: int = 0
    examples: list[ValidationExample] = Field(default_factory=list)
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class MaskSpec(StrictModel):
    name: str
    type: str
    pattern: str
    value_group: int | None = None
    replacement: str
    priority: int = 0
    enabled: bool = True
    flags: list[AllowedFlag] = Field(default_factory=list)
    validation: MaskValidation | None = None

    @field_validator("name", "type", "pattern", "replacement")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("type")
    @classmethod
    def _normalize_type(cls, value: str) -> str:
        return value.upper()

    @field_validator("value_group")
    @classmethod
    def _non_negative_group(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("value_group must be null or a non-negative integer")
        return value

    @field_validator("flags")
    @classmethod
    def _valid_flags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for flag in value:
            if flag not in ALLOWED_FLAGS:
                raise ValueError(f"unsupported regex flag: {flag}")
            if flag not in seen:
                seen.add(flag)
                normalized.append(flag)
        return normalized


class SourceMetadata(StrictModel):
    sample_sha256: str
    sample_size: int
    sampler: str
    corpus_sha256: str | None = None


class GeneratorMetadata(StrictModel):
    backend: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    temperature: float | None = 0
    params: dict[str, Any] = Field(default_factory=dict)


class BundleValidationSummary(StrictModel):
    validator_version: str = "0.1"
    strict: bool = True
    accepted_count: int = 0
    rejected_count: int = 0
    examples_redacted: bool = True


class RejectedMask(StrictModel):
    name: str
    type: str | None = None
    pattern: str
    reason: str


class CandidateValidationSummary(StrictModel):
    candidate_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    rejection_reasons: dict[str, int] = Field(default_factory=dict)


class MaskBundle(StrictModel):
    version: str = "0.1"
    created_at: str
    source: SourceMetadata
    generator: GeneratorMetadata
    validation: BundleValidationSummary
    candidate_validation: CandidateValidationSummary | None = None
    masks: list[MaskSpec] = Field(default_factory=list)
    rejected_masks: list[RejectedMask] = Field(default_factory=list)


class CandidateMask(StrictModel):
    name: str
    type: str
    pattern: str
    value_group: int | None = None
    replacement: str
    priority: int = 0
    flags: list[AllowedFlag] = Field(default_factory=list)
    rationale: str | None = None
    examples_observed: list[str] = Field(default_factory=list)

    @field_validator("name", "type", "pattern", "replacement")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("type")
    @classmethod
    def _normalize_type(cls, value: str) -> str:
        return value.upper()

    @field_validator("value_group")
    @classmethod
    def _non_negative_group(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("value_group must be null or a non-negative integer")
        return value

    @field_validator("flags")
    @classmethod
    def _valid_flags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for flag in value:
            if flag not in ALLOWED_FLAGS:
                raise ValueError(f"unsupported regex flag: {flag}")
            if flag not in seen:
                seen.add(flag)
                normalized.append(flag)
        return normalized


class CandidateMaskBundle(StrictModel):
    candidate_schema_version: str = "0.1"
    candidates: list[CandidateMask] = Field(default_factory=list)


class VariableSpan(StrictModel):
    type: str
    value: str
    start: int
    end: int
    mask_name: str


class MaskedLine(StrictModel):
    line_id: int
    raw: str
    masked: str
    variables: list[VariableSpan] = Field(default_factory=list)
    runtime_mask_sha256: str


class ParserMetadata(StrictModel):
    engine: str
    engine_version: str
    similarity_threshold: float
    tokenizer_version: str
    template_id_mode: str = "sequential"
    runtime_mask_sha256: str


class ParsedLine(StrictModel):
    line_id: int
    raw: str
    masked: str
    template_id: str
    template_hash: str
    template: str
    parser: ParserMetadata
    variables: list[VariableSpan] = Field(default_factory=list)
