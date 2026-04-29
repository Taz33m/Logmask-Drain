"""End-to-end masking and parsing pipeline."""

from __future__ import annotations

from .drain_adapter import get_parser
from .masking import Masker
from .models import MaskBundle, ParsedLine, ParserMetadata


def parse_lines(
    lines: list[str],
    bundle: MaskBundle,
    *,
    engine: str = "simple_drain",
    similarity_threshold: float = 0.4,
    template_id_mode: str = "sequential",
) -> list[ParsedLine]:
    masker = Masker(bundle)
    masked_lines = masker.mask_lines(lines)
    parser = get_parser(engine, similarity_threshold=similarity_threshold)
    assignments = parser.parse_all([line.masked for line in masked_lines], template_id_mode=template_id_mode)
    metadata = ParserMetadata(
        engine=parser.engine,
        engine_version=parser.engine_version,
        similarity_threshold=similarity_threshold,
        tokenizer_version=parser.tokenizer_version,
        template_id_mode=template_id_mode,
        runtime_mask_sha256=masker.runtime_hash,
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
