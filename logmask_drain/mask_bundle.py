"""Mask bundle construction helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from .io import sha256_text
from .models import BundleValidationSummary, GeneratorMetadata, MaskBundle, MaskSpec, SourceMetadata
from .regex_validation import VALIDATOR_VERSION, validate_masks


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_mask_bundle(
    masks: list[MaskSpec],
    sample_lines: list[str],
    *,
    backend: str,
    sampler: str = "manual",
    rule_mode: str | None = None,
    strict: bool = True,
    include_raw_examples: bool = False,
    corpus_text: str | None = None,
) -> MaskBundle:
    sample_text = "\n".join(sample_lines)
    accepted, rejected = validate_masks(
        masks,
        sample_lines,
        strict=strict,
        include_raw_examples=include_raw_examples,
    )
    params = {}
    if rule_mode is not None:
        params["rule_mode"] = rule_mode
    return MaskBundle(
        created_at=utc_now_iso(),
        source=SourceMetadata(
            sample_sha256=sha256_text(sample_text),
            sample_size=len(sample_lines),
            sampler=sampler,
            corpus_sha256=sha256_text(corpus_text) if corpus_text is not None else None,
        ),
        generator=GeneratorMetadata(
            backend=backend,
            model=None,
            prompt_version=None,
            temperature=0,
            params=params,
        ),
        validation=BundleValidationSummary(
            validator_version=VALIDATOR_VERSION,
            strict=strict,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            examples_redacted=not include_raw_examples,
        ),
        masks=accepted,
        rejected_masks=rejected,
    )

