"""Drain-style parsing adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from typing import Any

from .template_id import format_template_id, hash_template_id, normalize_template, template_hash


TOKENIZER_VERSION = "whitespace_v1"
DRAIN3_TOKENIZER_VERSION = "drain3_default_v1"
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


@dataclass(frozen=True)
class _Drain3Components:
    template_miner: Any
    template_miner_config: Any
    version: str


def _load_drain3_components() -> _Drain3Components:
    try:
        from drain3 import TemplateMiner
        from drain3.template_miner_config import TemplateMinerConfig
    except ImportError as exc:  # pragma: no cover - exercised through get_parser
        raise ValueError(
            "engine=drain3 requires the optional dependency; install with "
            "`pip install 'logmask-drain[drain3]'`."
        ) from exc

    try:
        version = metadata.version("drain3")
    except metadata.PackageNotFoundError:
        version = "unknown"
    return _Drain3Components(
        template_miner=TemplateMiner,
        template_miner_config=TemplateMinerConfig,
        version=version,
    )


class Drain3Adapter:
    """Adapter for the optional drain3 implementation.

    Logmask applies regex masks before this adapter sees a line. Drain3's own
    numeric parametrization is disabled so mask bundles remain the explicit
    runtime boundary.
    """

    engine = "drain3"
    tokenizer_version = DRAIN3_TOKENIZER_VERSION

    def __init__(self, *, similarity_threshold: float = 0.4):
        self.similarity_threshold = similarity_threshold
        self._components = _load_drain3_components()
        self.engine_version = self._components.version

    def _make_miner(self) -> Any:
        config = self._components.template_miner_config()
        if hasattr(config, "drain_sim_th"):
            config.drain_sim_th = self.similarity_threshold
        if hasattr(config, "profiling_enabled"):
            config.profiling_enabled = False
        if hasattr(config, "parametrize_numeric_tokens"):
            config.parametrize_numeric_tokens = False
        return self._components.template_miner(config=config)

    def parse_all(self, lines: list[str], *, template_id_mode: str = "sequential") -> list[TemplateAssignment]:
        if template_id_mode not in {"sequential", "hash"}:
            raise ValueError("template_id_mode must be 'sequential' or 'hash'")

        miner = self._make_miner()
        cluster_to_index: dict[Any, int] = {}
        assignments: list[TemplateAssignment] = []

        for line in lines:
            result = miner.add_log_message(line)
            template = normalize_template(str(result.get("template_mined") or line))
            hash_value = template_hash(template)

            if template_id_mode == "hash":
                template_id = hash_template_id(hash_value)
            else:
                cluster_key = result.get("cluster_id", template)
                if cluster_key not in cluster_to_index:
                    cluster_to_index[cluster_key] = len(cluster_to_index) + 1
                template_id = format_template_id(cluster_to_index[cluster_key])

            assignments.append(
                TemplateAssignment(
                    template_id=template_id,
                    template_hash=hash_value,
                    template=template,
                )
            )
        return assignments


def get_parser(engine: str = "simple_drain", *, similarity_threshold: float = 0.4) -> SimpleDrain | Drain3Adapter:
    if engine == "drain3":
        return Drain3Adapter(similarity_threshold=similarity_threshold)
    if engine != "simple_drain":
        raise ValueError("engine must be simple_drain or drain3")
    return SimpleDrain(similarity_threshold=similarity_threshold)
