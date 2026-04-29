"""Drain-style parsing adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

from .template_id import format_template_id, hash_template_id, normalize_template, template_hash


TOKENIZER_VERSION = "whitespace_v1"
SIMPLE_DRAIN_VERSION = "0.1"


def tokenize_whitespace_v1(line: str) -> list[str]:
    return line.split()


@dataclass
class TemplateAssignment:
    template_id: str
    template_hash: str
    template: str


@dataclass
class _Cluster:
    index: int
    template_tokens: list[str]
    line_indices: list[int] = field(default_factory=list)

    def template(self) -> str:
        return normalize_template(" ".join(self.template_tokens))


class SimpleDrain:
    """Small deterministic Drain-like parser for CPU-only v0.1 use."""

    engine = "simple_drain"
    engine_version = SIMPLE_DRAIN_VERSION
    tokenizer_version = TOKENIZER_VERSION

    def __init__(self, *, similarity_threshold: float = 0.4):
        self.similarity_threshold = similarity_threshold
        self._clusters_by_length: dict[int, list[_Cluster]] = {}
        self._clusters: list[_Cluster] = []

    @staticmethod
    def _similarity(template_tokens: list[str], tokens: list[str]) -> float:
        if len(template_tokens) != len(tokens):
            return 0.0
        if not tokens:
            return 1.0
        matches = 0
        for left, right in zip(template_tokens, tokens):
            if left == right or left == "<*>":
                matches += 1
        return matches / len(tokens)

    @staticmethod
    def _merge(template_tokens: list[str], tokens: list[str]) -> list[str]:
        merged: list[str] = []
        for left, right in zip(template_tokens, tokens):
            if left == right:
                merged.append(left)
            elif left == "<*>":
                merged.append(left)
            else:
                merged.append("<*>")
        return merged

    def _best_cluster(self, tokens: list[str]) -> _Cluster | None:
        candidates = self._clusters_by_length.get(len(tokens), [])
        best: _Cluster | None = None
        best_score = -1.0
        for cluster in candidates:
            score = self._similarity(cluster.template_tokens, tokens)
            if score > best_score:
                best = cluster
                best_score = score
        if best is not None and best_score >= self.similarity_threshold:
            return best
        return None

    def parse_all(self, lines: list[str], *, template_id_mode: str = "sequential") -> list[TemplateAssignment]:
        if template_id_mode not in {"sequential", "hash"}:
            raise ValueError("template_id_mode must be 'sequential' or 'hash'")

        line_to_cluster: list[_Cluster] = []
        for line_index, line in enumerate(lines):
            tokens = tokenize_whitespace_v1(line)
            cluster = self._best_cluster(tokens)
            if cluster is None:
                cluster = _Cluster(index=len(self._clusters) + 1, template_tokens=tokens)
                self._clusters.append(cluster)
                self._clusters_by_length.setdefault(len(tokens), []).append(cluster)
            else:
                cluster.template_tokens = self._merge(cluster.template_tokens, tokens)
            cluster.line_indices.append(line_index)
            line_to_cluster.append(cluster)

        assignments: list[TemplateAssignment] = []
        for cluster in line_to_cluster:
            template = cluster.template()
            hash_value = template_hash(template)
            if template_id_mode == "hash":
                template_id = hash_template_id(hash_value)
            else:
                template_id = format_template_id(cluster.index)
            assignments.append(
                TemplateAssignment(
                    template_id=template_id,
                    template_hash=hash_value,
                    template=template,
                )
            )
        return assignments


def get_parser(engine: str = "simple_drain", *, similarity_threshold: float = 0.4) -> SimpleDrain:
    if engine != "simple_drain":
        try:
            __import__("drain3")
        except ImportError as exc:
            raise ValueError("engine 'drain3' requested but optional dependency is not installed") from exc
        raise ValueError("drain3 adapter is not implemented in v0.1; use simple_drain")
    return SimpleDrain(similarity_threshold=similarity_threshold)
