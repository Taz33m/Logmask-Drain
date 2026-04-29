"""Deterministic mask-first line transformation."""

from __future__ import annotations

from dataclasses import dataclass

from .io import runtime_mask_sha256
from .masks import compile_mask, ordered_masks
from .models import MaskBundle, MaskedLine, MaskSpec, VariableSpan
from .regex_validation import selected_span


@dataclass(frozen=True)
class CandidateSpan:
    start: int
    end: int
    mask: MaskSpec
    value: str

    @property
    def length(self) -> int:
        return self.end - self.start


def _overlaps(candidate: CandidateSpan, accepted: list[CandidateSpan]) -> bool:
    return any(not (candidate.end <= item.start or candidate.start >= item.end) for item in accepted)


def resolve_overlaps(candidates: list[CandidateSpan]) -> list[CandidateSpan]:
    ranked = sorted(
        candidates,
        key=lambda item: (-item.mask.priority, -item.length, item.start, item.mask.name),
    )
    accepted: list[CandidateSpan] = []
    for candidate in ranked:
        if not _overlaps(candidate, accepted):
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.start, item.end, item.mask.name))


class Masker:
    def __init__(self, bundle_or_masks: MaskBundle | list[MaskSpec], *, timeout_seconds: float = 0.01):
        if isinstance(bundle_or_masks, MaskBundle):
            self.masks = ordered_masks(bundle_or_masks.masks)
        else:
            self.masks = ordered_masks(bundle_or_masks)
        self.timeout_seconds = timeout_seconds
        self.runtime_hash = runtime_mask_sha256(self.masks)
        self._compiled = [(mask, compile_mask(mask)) for mask in self.masks]

    def mask_line(self, line: str, line_id: int = 0) -> MaskedLine:
        candidates: list[CandidateSpan] = []
        for mask, compiled in self._compiled:
            try:
                for match in compiled.finditer(line, timeout=self.timeout_seconds):
                    span = selected_span(match, mask.value_group)
                    if span is None:
                        continue
                    start, end = span
                    if start == end:
                        continue
                    candidates.append(CandidateSpan(start, end, mask, line[start:end]))
            except TimeoutError:
                continue

        accepted = resolve_overlaps(candidates)
        pieces: list[str] = []
        variables: list[VariableSpan] = []
        cursor = 0
        for span in accepted:
            pieces.append(line[cursor : span.start])
            pieces.append(span.mask.replacement)
            variables.append(
                VariableSpan(
                    type=span.mask.type,
                    value=span.value,
                    start=span.start,
                    end=span.end,
                    mask_name=span.mask.name,
                )
            )
            cursor = span.end
        pieces.append(line[cursor:])
        return MaskedLine(
            line_id=line_id,
            raw=line,
            masked="".join(pieces),
            variables=variables,
            runtime_mask_sha256=self.runtime_hash,
        )

    def mask_lines(self, lines: list[str]) -> list[MaskedLine]:
        return [self.mask_line(line, index) for index, line in enumerate(lines)]

