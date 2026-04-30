"""Reproducible benchmark matrix runner."""

from __future__ import annotations

import platform as platform_module
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from .drain_adapter import get_parser
from .io import load_mask_bundle, runtime_mask_sha256, sha256_text
from .mask_bundle import create_mask_bundle, utc_now_iso
from .metrics import (
    grouping_accuracy_exact,
    parsing_accuracy_generic,
    parsing_accuracy_typed,
)
from .models import (
    BenchmarkDatasetMetadata,
    BenchmarkMethodResult,
    BenchmarkRun,
    BenchmarkSampleMetadata,
    MaskBundle,
)
from .pipeline import parse_lines_with_diagnostics
from .reporting import summarize_parsed
from .sampling import sample_lines as choose_sample_lines
from .synthesis_backends.api_llm import (
    DEFAULT_MAX_API_SAMPLE_CHARS,
    DEFAULT_MAX_API_SAMPLE_LINES,
    get_api_provider,
    synthesize_api_llm_bundle,
)
from .synthesis_backends.local_llm import (
    DEFAULT_MAX_LOCAL_SAMPLE_CHARS,
    DEFAULT_MAX_LOCAL_SAMPLE_LINES,
    get_local_provider,
    synthesize_local_llm_bundle,
)
from .synthesis_backends.rules import get_rule_masks


DEFAULT_MATRIX_METHODS = "simple_raw,builtin_simple"


@dataclass(frozen=True)
class MatrixMethodSpec:
    method_id: str
    parser_engine: str
    synthesis_backend: str
    mask_kind: str
    live_base_rules: str = "none"


METHOD_SPECS: dict[str, MatrixMethodSpec] = {
    "simple_raw": MatrixMethodSpec("simple_raw", "simple_drain", "none", "raw"),
    "drain3_raw": MatrixMethodSpec("drain3_raw", "drain3", "none", "raw"),
    "builtin_simple": MatrixMethodSpec("builtin_simple", "simple_drain", "rules", "builtin"),
    "builtin_drain3": MatrixMethodSpec("builtin_drain3", "drain3", "rules", "builtin"),
    "bundle_simple": MatrixMethodSpec("bundle_simple", "simple_drain", "bundle", "bundle"),
    "bundle_drain3": MatrixMethodSpec("bundle_drain3", "drain3", "bundle", "bundle"),
    "api_llm_simple": MatrixMethodSpec("api_llm_simple", "simple_drain", "api-llm", "api_llm"),
    "api_llm_drain3": MatrixMethodSpec("api_llm_drain3", "drain3", "api-llm", "api_llm"),
    "local_llm_simple": MatrixMethodSpec("local_llm_simple", "simple_drain", "local-llm", "local_llm"),
    "local_llm_drain3": MatrixMethodSpec("local_llm_drain3", "drain3", "local-llm", "local_llm"),
    "hybrid_api_simple": MatrixMethodSpec(
        "hybrid_api_simple", "simple_drain", "api-llm", "hybrid_api", live_base_rules="conservative"
    ),
    "hybrid_api_drain3": MatrixMethodSpec(
        "hybrid_api_drain3", "drain3", "api-llm", "hybrid_api", live_base_rules="conservative"
    ),
    "hybrid_local_simple": MatrixMethodSpec(
        "hybrid_local_simple", "simple_drain", "local-llm", "hybrid_local", live_base_rules="conservative"
    ),
    "hybrid_local_drain3": MatrixMethodSpec(
        "hybrid_local_drain3", "drain3", "local-llm", "hybrid_local", live_base_rules="conservative"
    ),
}


@dataclass(frozen=True)
class BundlePaths:
    masks: Path | None = None
    api_llm_masks: Path | None = None
    local_llm_masks: Path | None = None
    hybrid_api_masks: Path | None = None
    hybrid_local_masks: Path | None = None


@dataclass(frozen=True)
class LiveSynthesisOptions:
    synthesize_missing: bool = False
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    local_provider: str = "llama-cpp"
    model_path: Path | None = None
    llama_cli: str = "llama-cli"
    max_candidates: int = 32
    temperature: float = 0
    prompt_version: str | None = None
    provider_timeout_seconds: float = 60
    provider_max_retries: int = 0
    max_api_sample_lines: int = DEFAULT_MAX_API_SAMPLE_LINES
    max_api_sample_chars: int = DEFAULT_MAX_API_SAMPLE_CHARS
    allow_large_api_sample: bool = False
    local_timeout_seconds: float = 120
    ctx_size: int = 4096
    max_tokens: int = 2048
    max_local_sample_lines: int = DEFAULT_MAX_LOCAL_SAMPLE_LINES
    max_local_sample_chars: int = DEFAULT_MAX_LOCAL_SAMPLE_CHARS
    allow_large_local_sample: bool = False
    allow_new_types: bool = False


def parse_matrix_methods(methods: str) -> list[str]:
    parsed = [item.strip() for item in methods.split(",") if item.strip()]
    if not parsed:
        raise ValueError("--methods must include at least one matrix method")
    unknown = sorted(set(parsed) - set(METHOD_SPECS))
    if unknown:
        raise ValueError(f"unknown matrix method(s): {', '.join(unknown)}")
    return parsed


def validate_matrix_bundle_requirements(methods: list[str], paths: BundlePaths) -> None:
    bundle_methods = [method for method in methods if METHOD_SPECS[method].mask_kind == "bundle"]
    if bundle_methods and paths.masks is None:
        raise ValueError("--methods includes bundle_* methods, so --masks is required")


def _sample_metadata(sample: list[str], *, sampler: str, seed: int, sample_path: Path | None) -> BenchmarkSampleMetadata:
    return BenchmarkSampleMetadata(
        sampler=sampler,
        sample_size=len(sample),
        sample_sha256=sha256_text("\n".join(sample)),
        seed=seed,
        sample_path=str(sample_path) if sample_path is not None else None,
    )


def _bundle_path_for_spec(spec: MatrixMethodSpec, paths: BundlePaths) -> Path | None:
    if spec.mask_kind == "bundle":
        return paths.masks
    if spec.mask_kind == "api_llm":
        return paths.api_llm_masks or paths.masks
    if spec.mask_kind == "local_llm":
        return paths.local_llm_masks or paths.masks
    if spec.mask_kind == "hybrid_api":
        return paths.hybrid_api_masks or paths.api_llm_masks or paths.masks
    if spec.mask_kind == "hybrid_local":
        return paths.hybrid_local_masks or paths.local_llm_masks or paths.masks
    return None


def _synthesize_live_bundle(
    spec: MatrixMethodSpec,
    sample: list[str],
    *,
    rule_mode: str,
    options: LiveSynthesisOptions,
    sampler: str,
) -> MaskBundle:
    if spec.synthesis_backend == "rules":
        return create_mask_bundle(
            get_rule_masks(rule_mode),
            sample,
            backend="rules",
            sampler=sampler,
            rule_mode=rule_mode,
            strict=True,
        )
    if spec.synthesis_backend == "api-llm":
        prompt_version = options.prompt_version or "api_llm_masks_v1"
        provider = get_api_provider(options.provider)
        bundle, _report = synthesize_api_llm_bundle(
            sample,
            provider=provider,
            model=options.model,
            prompt_version=prompt_version,
            temperature=options.temperature,
            max_candidates=options.max_candidates,
            provider_timeout_seconds=options.provider_timeout_seconds,
            provider_max_retries=options.provider_max_retries,
            max_api_sample_lines=options.max_api_sample_lines,
            max_api_sample_chars=options.max_api_sample_chars,
            allow_large_api_sample=options.allow_large_api_sample,
            base_rules=spec.live_base_rules,
            strict=True,
            allow_new_types=options.allow_new_types,
            sampler=sampler,
        )
        return bundle
    if spec.synthesis_backend == "local-llm":
        if options.model_path is None:
            raise ValueError("--model-path is required to live-synthesize local LLM benchmark masks")
        prompt_version = options.prompt_version or "local_llm_masks_v1"
        provider = get_local_provider(options.local_provider, llama_cli=options.llama_cli)
        bundle, _report = synthesize_local_llm_bundle(
            sample,
            provider=provider,
            model_path=options.model_path,
            prompt_version=prompt_version,
            temperature=options.temperature,
            max_candidates=options.max_candidates,
            timeout_seconds=options.local_timeout_seconds,
            ctx_size=options.ctx_size,
            max_tokens=options.max_tokens,
            max_local_sample_lines=options.max_local_sample_lines,
            max_local_sample_chars=options.max_local_sample_chars,
            allow_large_local_sample=options.allow_large_local_sample,
            base_rules=spec.live_base_rules,
            strict=True,
            allow_new_types=options.allow_new_types,
            sampler=sampler,
        )
        return bundle
    raise ValueError(f"method {spec.method_id} cannot live-synthesize masks")


def _load_or_create_bundle(
    spec: MatrixMethodSpec,
    sample: list[str],
    *,
    paths: BundlePaths,
    rule_mode: str,
    live_options: LiveSynthesisOptions,
    sampler: str,
) -> tuple[MaskBundle | None, str | None, bool, str | None]:
    if spec.mask_kind == "raw":
        return None, None, False, None
    if spec.mask_kind == "builtin":
        bundle = create_mask_bundle(
            get_rule_masks(rule_mode),
            sample,
            backend="rules",
            sampler=sampler,
            rule_mode=rule_mode,
            strict=True,
        )
        return bundle, "builtin", False, None

    path = _bundle_path_for_spec(spec, paths)
    if path is not None:
        return load_mask_bundle(path), str(path), False, None
    if not live_options.synthesize_missing:
        return (
            None,
            None,
            False,
            f"{spec.method_id} requires a saved mask bundle path or --synthesize-missing",
        )
    bundle = _synthesize_live_bundle(spec, sample, rule_mode=rule_mode, options=live_options, sampler=sampler)
    return bundle, "live_synthesis", True, None


def _singleton_count(clusters: list[str]) -> int:
    counts = Counter(clusters)
    return sum(1 for count in counts.values() if count == 1)


def _passed_result(
    spec: MatrixMethodSpec,
    *,
    templates: list[str],
    clusters: list[str],
    truth_templates: list[str],
    truth_clusters: list[str],
    typed_truth_templates: list[str] | None,
    parse_runtime: float,
    total_runtime: float,
    mask_coverage: float,
    bundle: MaskBundle | None,
    mask_source: str | None,
    live_synthesis: bool,
) -> BenchmarkMethodResult:
    singleton_count = _singleton_count(clusters)
    return BenchmarkMethodResult(
        method_id=spec.method_id,
        status="passed",
        parser_engine=spec.parser_engine,
        synthesis_backend=bundle.generator.backend if bundle is not None else spec.synthesis_backend,
        mask_source=mask_source,
        runtime_mask_sha256=runtime_mask_sha256(bundle) if bundle is not None else None,
        live_synthesis=live_synthesis,
        GA_exact=grouping_accuracy_exact(clusters, truth_clusters),
        PA_generic=parsing_accuracy_generic(templates, truth_templates),
        PA_typed=parsing_accuracy_typed(templates, typed_truth_templates) if typed_truth_templates is not None else None,
        template_count=len(set(clusters)),
        singleton_count=singleton_count,
        singleton_rate=singleton_count / len(clusters) if clusters else 0.0,
        parse_runtime_seconds=parse_runtime,
        runtime_seconds_total=total_runtime,
        runtime_per_100_logs_seconds=total_runtime / max(len(templates), 1) * 100,
        mask_coverage=mask_coverage,
        accepted_mask_count=len(bundle.masks) if bundle is not None else 0,
        rejected_mask_count=len(bundle.rejected_masks) if bundle is not None else 0,
    )


def _status_result(spec: MatrixMethodSpec, status: str, error: str) -> BenchmarkMethodResult:
    return BenchmarkMethodResult(
        method_id=spec.method_id,
        status=status,  # type: ignore[arg-type]
        error=error,
        parser_engine=spec.parser_engine,
        synthesis_backend=spec.synthesis_backend,
    )


def run_benchmark_matrix(
    logs: list[str],
    truth_templates: list[str],
    truth_clusters: list[str],
    *,
    dataset: BenchmarkDatasetMetadata,
    methods: list[str],
    typed_truth_templates: list[str] | None = None,
    paths: BundlePaths | None = None,
    rule_mode: str = "conservative",
    similarity_threshold: float = 0.4,
    template_id_mode: str = "hash",
    sample_size: int = 50,
    sample_mode: str = "entropy_greedy",
    sample: list[str] | None = None,
    sample_path: Path | None = None,
    sample_seed: int = 0,
    live_options: LiveSynthesisOptions | None = None,
    get_time: Callable[[], float] = time.perf_counter,
) -> BenchmarkRun:
    if len(logs) != len(truth_templates) or len(logs) != len(truth_clusters):
        raise ValueError("logs, truth templates, and truth clusters must have the same length")
    if typed_truth_templates is not None and len(typed_truth_templates) != len(logs):
        raise ValueError("typed truth templates must have the same length as logs")
    if template_id_mode not in {"sequential", "hash"}:
        raise ValueError("template_id_mode must be sequential or hash")
    if sample is None:
        sample = choose_sample_lines(logs, k=min(sample_size, len(logs)), mode=sample_mode, seed=sample_seed)
    sampler = sample_mode if sample_path is None else "manual"
    sample_meta = _sample_metadata(sample, sampler=sampler, seed=sample_seed, sample_path=sample_path)
    paths = paths or BundlePaths()
    live_options = live_options or LiveSynthesisOptions()
    validate_matrix_bundle_requirements(methods, paths)

    results: list[BenchmarkMethodResult] = []
    for method in methods:
        spec = METHOD_SPECS[method]
        method_started = get_time()
        try:
            bundle, mask_source, live_synthesis, skip_reason = _load_or_create_bundle(
                spec,
                sample,
                paths=paths,
                rule_mode=rule_mode,
                live_options=live_options,
                sampler=sampler,
            )
            if skip_reason is not None:
                results.append(_status_result(spec, "skipped", skip_reason))
                continue

            parse_started = get_time()
            if bundle is None:
                parser = get_parser(spec.parser_engine, similarity_threshold=similarity_threshold)
                assignments = parser.parse_all(logs, template_id_mode=template_id_mode)
                parse_runtime = get_time() - parse_started
                templates = [assignment.template for assignment in assignments]
                clusters = [assignment.template_hash for assignment in assignments]
                mask_coverage = 0.0
            else:
                parsed, _diagnostics = parse_lines_with_diagnostics(
                    logs,
                    bundle,
                    engine=spec.parser_engine,
                    similarity_threshold=similarity_threshold,
                    template_id_mode=template_id_mode,
                )
                parse_runtime = get_time() - parse_started
                templates = [line.template for line in parsed]
                clusters = [line.template_hash for line in parsed]
                mask_coverage = float(summarize_parsed(parsed)["mask_coverage"])
            total_runtime = get_time() - method_started
            results.append(
                _passed_result(
                    spec,
                    templates=templates,
                    clusters=clusters,
                    truth_templates=truth_templates,
                    truth_clusters=truth_clusters,
                    typed_truth_templates=typed_truth_templates,
                    parse_runtime=parse_runtime,
                    total_runtime=total_runtime,
                    mask_coverage=mask_coverage,
                    bundle=bundle,
                    mask_source=mask_source,
                    live_synthesis=live_synthesis,
                )
            )
        except (RuntimeError, ValueError) as exc:
            message = str(exc)
            optional_or_config_missing = (
                (spec.parser_engine == "drain3" and "optional dependency" in message)
                or "optional dependency" in message
                or "is required" in message
                or "does not exist" in message
                or "llama-cli" in message
            )
            status = "skipped" if optional_or_config_missing else "failed"
            results.append(_status_result(spec, status, message))
        except Exception as exc:  # pragma: no cover - defensive boundary for benchmark matrices.
            results.append(_status_result(spec, "failed", str(exc)))

    return BenchmarkRun(
        created_at=utc_now_iso(),
        logmask_version=__version__,
        python_version=sys.version.split()[0],
        platform=platform_module.platform(),
        dataset=dataset,
        sample=sample_meta,
        methods=results,
    )
