"""End-to-end masking and parsing pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .drain_adapter import get_parser
from .masking import Masker
from .models import MaskBundle, ParsedLine, ParserMetadata


@dataclass(frozen=True)
class ParseDiagnostics:
    runtime_timeout_count: int = 0
    runtime_timeouts_by_mask: dict[str, int] | None = None

    def timeout_summary(self) -> str:
        if not self.runtime_timeout_count:
            return "no runtime regex timeouts"
        masks = self.runtime_timeouts_by_mask or {}
        mask_summary = ", ".join(f"{name}={count}" for name, count in sorted(masks.items()))
        return f"{self.runtime_timeout_count} runtime regex timeout(s)" + (f" ({mask_summary})" if mask_summary else "")


def parse_lines_with_diagnostics(
    lines: list[str],
    bundle: MaskBundle,
    *,
    engine: str = "simple_drain",
    similarity_threshold: float = 0.4,
    template_id_mode: str = "sequential",
    strict_runtime: bool = False,
) -> tuple[list[ParsedLine], ParseDiagnostics]:
    masker = Masker(bundle)
    masked_lines = masker.mask_lines(lines)
    diagnostics = ParseDiagnostics(
        runtime_timeout_count=masker.timeout_count,
        runtime_timeouts_by_mask=dict(sorted(masker.timeouts_by_mask.items())),
    )
    if strict_runtime and diagnostics.runtime_timeout_count:
        raise RuntimeError(
            f"{diagnostics.timeout_summary()}; re-run without --strict-runtime to allow under-masked lines."
        )

    parser = get_parser(engine, similarity_threshold=similarity_threshold)
    assignments = parser.parse_all([line.masked for line in masked_lines], template_id_mode=template_id_mode)
    metadata = ParserMetadata(
        engine=parser.engine,
        engine_version=parser.engine_version,
        similarity_threshold=similarity_threshold,
        tokenizer_version=parser.tokenizer_version,
        template_id_mode=template_id_mode,
        runtime_mask_sha256=masker.runtime_hash,
        runtime_timeout_count=diagnostics.runtime_timeout_count,
        runtime_timeouts_by_mask=diagnostics.runtime_timeouts_by_mask or {},
    )
    parsed: list[ParsedLine] = []
    for masked, assignment in zip(masked_lines, assignments):
        parsed.append(
            ParsedLine(
                line_id=masked.line_id,
                raw=masked.raw,
                masked=masked.masked,
                template_id=assignment.template_id,
                template_hash=assignment.template_hash,
                template=assignment.template,
                parser=metadata,
                variables=masked.variables,
            )
        )
    return parsed, diagnostics


def parse_lines(
    lines: list[str],
    bundle: MaskBundle,
    *,
    engine: str = "simple_drain",
    similarity_threshold: float = 0.4,
    template_id_mode: str = "sequential",
) -> list[ParsedLine]:
    parsed, _diagnostics = parse_lines_with_diagnostics(
        lines,
        bundle,
        engine=engine,
        similarity_threshold=similarity_threshold,
        template_id_mode=template_id_mode,
    )
    return parsed


def parse_raw_lines(
    lines: list[str],
    *,
    engine: str = "simple_drain",
    similarity_threshold: float = 0.4,
    template_id_mode: str = "sequential",
) -> list[str]:
    parser = get_parser(engine, similarity_threshold=similarity_threshold)
    assignments = parser.parse_all(lines, template_id_mode=template_id_mode)
    return [assignment.template for assignment in assignments]
