"""Command-line interface for logmask-drain."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .datasets import load_ground_truth_templates
from .drain_adapter import get_parser
from .io import (
    bundle_sha256,
    load_mask_bundle,
    load_parsed_jsonl,
    read_lines,
    runtime_mask_projection,
    runtime_mask_sha256,
    save_json,
    save_mask_bundle,
    write_jsonl,
    write_lines,
)
from .mask_bundle import create_mask_bundle
from .masking import Masker
from .metrics import grouping_accuracy_exact, normalize_generic_template, parsing_accuracy_generic
from .models import BundleValidationSummary, CandidateMaskBundle, MaskBundle
from .performance import performance_benchmark
from .pipeline import parse_lines
from .regex_validation import VALIDATOR_VERSION, validate_masks as validate_mask_specs
from .reporting import drift_report, summarize_parsed
from .sampling import sample_lines
from .prompts import API_LLM_MASKS_PROMPT_VERSION
from .synthesis_backends.api_llm import get_api_provider, synthesize_api_llm_bundle
from .synthesis_backends.rules import get_rule_masks


app = typer.Typer(no_args_is_help=True, help="CPU-first regex mask-bundle log parser.")
console = Console()


def _parse_methods(methods: str) -> list[str]:
    parsed = [item.strip() for item in methods.split(",") if item.strip()]
    allowed = {"drain", "builtin", "bundle"}
    unknown = set(parsed) - allowed
    if unknown:
        raise typer.BadParameter(f"unknown method(s): {', '.join(sorted(unknown))}")
    return parsed


def _print_summary(summary: dict) -> None:
    table = Table(title="Logmask Report")
    table.add_column("Metric")
    table.add_column("Value")
    for key in [
        "line_count",
        "unique_template_count",
        "singleton_template_count",
        "template_entropy",
        "mask_coverage",
    ]:
        value = summary[key]
        if isinstance(value, float):
            rendered = f"{value:.6f}"
        else:
            rendered = str(value)
        table.add_row(key, rendered)
    console.print(table)

    vars_table = Table(title="Variables by Type")
    vars_table.add_column("Type")
    vars_table.add_column("Count", justify="right")
    for key, value in summary["variables_by_type"].items():
        vars_table.add_row(key, str(value))
    console.print(vars_table)

    coverage_table = Table(title="Mask Coverage by Type")
    coverage_table.add_column("Type")
    coverage_table.add_column("Count", justify="right")
    coverage_table.add_column("Coverage", justify="right")
    for key, value in summary["mask_coverage_by_type"].items():
        coverage_table.add_row(key, str(value["count"]), f"{value['coverage']:.6f}")
    console.print(coverage_table)

    top_table = Table(title="Top Templates")
    top_table.add_column("Count", justify="right")
    top_table.add_column("Hash")
    top_table.add_column("Template")
    for item in summary["top_templates"]:
        top_table.add_row(str(item["count"]), item["template_hash"], item["template"])
    console.print(top_table)

    singleton_table = Table(title="Singleton Template Examples")
    singleton_table.add_column("Line", justify="right")
    singleton_table.add_column("Hash")
    singleton_table.add_column("Template")
    for item in summary["singleton_template_examples"]:
        singleton_table.add_row(str(item["line_id"]), item["template_hash"], item["template"])
    console.print(singleton_table)

    token_table = Table(title="Top Unmasked High-Cardinality Tokens")
    token_table.add_column("Token")
    token_table.add_column("Count", justify="right")
    for item in summary["top_unmasked_high_cardinality_tokens"]:
        token_table.add_row(item["token"], str(item["count"]))
    console.print(token_table)

    recommendation_table = Table(title="Recommendations")
    recommendation_table.add_column("Severity")
    recommendation_table.add_column("Code")
    recommendation_table.add_column("Message")
    for item in summary["recommendations"]:
        recommendation_table.add_row(item["severity"], item["code"], item["message"])
    console.print(recommendation_table)


@app.command()
def synthesize(
    sample: Path = typer.Argument(..., help="Plain-text sample log file."),
    backend: str = typer.Option("rules", "--backend", help="rules or api-llm."),
    rule_mode: str = typer.Option("conservative", "--rule-mode", help="conservative or aggressive."),
    provider: str = typer.Option("openai", "--provider", help="API LLM provider for --backend api-llm."),
    model: str = typer.Option("gpt-4.1-mini", "--model", help="API LLM model for --backend api-llm."),
    base_rules: str = typer.Option(
        "none",
        "--base-rules",
        help="none, conservative, or aggressive base masks for --backend api-llm.",
    ),
    candidate_report: Optional[Path] = typer.Option(
        None,
        "--candidate-report",
        help="Optional JSON report of accepted/rejected LLM candidates.",
    ),
    allow_new_types: bool = typer.Option(
        False,
        "--allow-new-types",
        help="Allow LLM candidates to introduce mask types outside the known registry.",
    ),
    max_candidates: int = typer.Option(32, "--max-candidates", help="Maximum LLM candidates to request/use."),
    temperature: float = typer.Option(0, "--temperature", help="API LLM generation temperature."),
    prompt_version: str = typer.Option(API_LLM_MASKS_PROMPT_VERSION, "--prompt-version"),
    provider_timeout_seconds: float = typer.Option(
        60,
        "--provider-timeout-seconds",
        help="Per API request timeout for --backend api-llm.",
    ),
    provider_max_retries: int = typer.Option(
        0,
        "--provider-max-retries",
        help="Provider request retry count for --backend api-llm.",
    ),
    out: Path = typer.Option(..., "--out", help="Output mask bundle JSON."),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Reject unsafe/useless masks."),
    include_raw_examples: bool = typer.Option(
        False,
        "--include-raw-examples",
        help="Store raw validation examples instead of redacted examples.",
    ),
) -> None:
    lines = read_lines(sample)
    if backend == "rules":
        masks = get_rule_masks(rule_mode)
        bundle = create_mask_bundle(
            masks,
            lines,
            backend="rules",
            sampler="manual",
            rule_mode=rule_mode,
            strict=strict,
            include_raw_examples=include_raw_examples,
        )
    elif backend == "api-llm":
        if max_candidates <= 0:
            raise typer.BadParameter("--max-candidates must be positive")
        if provider_timeout_seconds <= 0:
            raise typer.BadParameter("--provider-timeout-seconds must be positive")
        if provider_max_retries < 0:
            raise typer.BadParameter("--provider-max-retries must be zero or positive")
        try:
            api_provider = get_api_provider(provider)
            bundle, report = synthesize_api_llm_bundle(
                lines,
                provider=api_provider,
                model=model,
                prompt_version=prompt_version,
                temperature=temperature,
                max_candidates=max_candidates,
                provider_timeout_seconds=provider_timeout_seconds,
                provider_max_retries=provider_max_retries,
                base_rules=base_rules,
                strict=strict,
                include_raw_examples=include_raw_examples,
                allow_new_types=allow_new_types,
            )
        except (RuntimeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        if candidate_report is not None:
            save_json(candidate_report, report)
    else:
        raise typer.BadParameter("--backend must be rules or api-llm")
    save_mask_bundle(out, bundle)
    console.print(
        f"Wrote {out} with {len(bundle.masks)} accepted mask(s), "
        f"{len(bundle.rejected_masks)} rejected mask(s)."
    )


@app.command("validate-masks")
def validate_masks_command(
    masks: Path = typer.Argument(..., help="Mask bundle JSON."),
    logs: Path = typer.Option(..., "--logs", help="Sample logs for validation."),
    strict: bool = typer.Option(True, "--strict/--no-strict"),
    include_raw_examples: bool = typer.Option(False, "--include-raw-examples"),
    out: Optional[Path] = typer.Option(None, "--out", help="Optional validated bundle output path."),
) -> None:
    bundle = load_mask_bundle(masks)
    lines = read_lines(logs)
    accepted, rejected = validate_mask_specs(
        bundle.masks,
        lines,
        strict=strict,
        include_raw_examples=include_raw_examples,
    )
    validated = bundle.model_copy(
        update={
            "masks": accepted,
            "rejected_masks": bundle.rejected_masks + rejected,
            "validation": BundleValidationSummary(
                validator_version=VALIDATOR_VERSION,
                strict=strict,
                accepted_count=len(accepted),
                rejected_count=len(bundle.rejected_masks) + len(rejected),
                examples_redacted=not include_raw_examples,
            ),
        }
    )
    if out is not None:
        save_mask_bundle(out, validated)
    console.print(
        f"Accepted {len(accepted)} mask(s); rejected {len(bundle.rejected_masks) + len(rejected)} mask(s)."
    )
    if strict and rejected:
        raise typer.Exit(code=1)


@app.command()
def mask(
    logs: Path = typer.Argument(..., help="Plain-text log file."),
    masks: Path = typer.Option(..., "--masks", help="Mask bundle JSON."),
    out: Path = typer.Option(..., "--out", help="Masked JSONL output."),
) -> None:
    bundle = load_mask_bundle(masks)
    masker = Masker(bundle)
    rows = masker.mask_lines(read_lines(logs))
    write_jsonl(out, rows)
    console.print(f"Wrote {len(rows)} masked line(s) to {out}.")


@app.command()
def parse(
    logs: Path = typer.Argument(..., help="Plain-text log file."),
    masks: Path = typer.Option(..., "--masks", help="Mask bundle JSON."),
    out: Path = typer.Option(..., "--out", help="Parsed JSONL output."),
    engine: str = typer.Option("simple_drain", "--engine"),
    similarity_threshold: float = typer.Option(0.4, "--similarity-threshold"),
    template_id_mode: str = typer.Option(
        "sequential",
        "--template-id-mode",
        help="sequential or hash. Hash mode is stable across input order/shards.",
    ),
) -> None:
    if template_id_mode not in {"sequential", "hash"}:
        raise typer.BadParameter("--template-id-mode must be sequential or hash")
    bundle = load_mask_bundle(masks)
    rows = parse_lines(
        read_lines(logs),
        bundle,
        engine=engine,
        similarity_threshold=similarity_threshold,
        template_id_mode=template_id_mode,
    )
    write_jsonl(out, rows)
    console.print(f"Wrote {len(rows)} parsed line(s) to {out}.")


@app.command()
def report(
    parsed: Path = typer.Argument(..., help="Parsed JSONL from logmask parse."),
    format: str = typer.Option("text", "--format", help="text or json."),
    out: Optional[Path] = typer.Option(None, "--out", help="Optional report output path."),
) -> None:
    rows = load_parsed_jsonl(parsed)
    summary = summarize_parsed(rows)
    if format == "json":
        if out is not None:
            save_json(out, summary)
        else:
            console.print_json(json.dumps(summary))
    elif format == "text":
        _print_summary(summary)
        if out is not None:
            save_json(out, summary)
    else:
        raise typer.BadParameter("--format must be text or json")


@app.command()
def sample(
    logs: Path = typer.Argument(..., help="Plain-text log file."),
    k: int = typer.Option(50, "--k"),
    mode: str = typer.Option("entropy_greedy", "--mode"),
    normalize_mode: str = typer.Option("digits_hex", "--normalize-mode"),
    out: Path = typer.Option(..., "--out"),
    seed: int = typer.Option(0, "--seed"),
) -> None:
    chosen = sample_lines(
        read_lines(logs),
        k=k,
        mode=mode,
        normalize_mode=normalize_mode,
        seed=seed,
    )
    write_lines(out, chosen)
    console.print(f"Wrote {len(chosen)} sampled line(s) to {out}.")


def _templates_for_method(
    method: str,
    logs: list[str],
    *,
    masks_path: Optional[Path],
    rule_mode: str,
    similarity_threshold: float,
) -> tuple[list[str], list[str], float]:
    started = time.perf_counter()
    if method == "drain":
        parser = get_parser("simple_drain", similarity_threshold=similarity_threshold)
        assignments = parser.parse_all(logs)
        elapsed = time.perf_counter() - started
        return [item.template for item in assignments], [item.template_hash for item in assignments], elapsed
    if method == "builtin":
        bundle = create_mask_bundle(
            get_rule_masks(rule_mode),
            logs,
            backend="rules",
            sampler="benchmark",
            rule_mode=rule_mode,
            strict=True,
        )
        parsed = parse_lines(logs, bundle, similarity_threshold=similarity_threshold)
        elapsed = time.perf_counter() - started
        return [item.template for item in parsed], [item.template_hash for item in parsed], elapsed
    if method == "bundle":
        if masks_path is None:
            raise typer.BadParameter("--masks is required when methods include bundle")
        bundle = load_mask_bundle(masks_path)
        parsed = parse_lines(logs, bundle, similarity_threshold=similarity_threshold)
        elapsed = time.perf_counter() - started
        return [item.template for item in parsed], [item.template_hash for item in parsed], elapsed
    raise AssertionError(method)


@app.command()
def benchmark(
    logs: Path = typer.Option(..., "--logs"),
    ground_truth: Path = typer.Option(..., "--ground-truth"),
    methods: str = typer.Option("drain,builtin,bundle", "--methods"),
    masks: Optional[Path] = typer.Option(None, "--masks"),
    rule_mode: str = typer.Option("conservative", "--rule-mode"),
    similarity_threshold: float = typer.Option(0.4, "--similarity-threshold"),
    out: Optional[Path] = typer.Option(None, "--out"),
) -> None:
    raw_logs = read_lines(logs)
    truth = load_ground_truth_templates(ground_truth)
    if len(raw_logs) != len(truth):
        raise typer.BadParameter("logs and ground truth contain different numbers of rows")

    truth_generic = [normalize_generic_template(item) for item in truth]
    results = []
    for method in _parse_methods(methods):
        predicted_templates, predicted_clusters, elapsed = _templates_for_method(
            method,
            raw_logs,
            masks_path=masks,
            rule_mode=rule_mode,
            similarity_threshold=similarity_threshold,
        )
        predicted_generic = [normalize_generic_template(item) for item in predicted_templates]
        results.append(
            {
                "method": method,
                "GA_exact": grouping_accuracy_exact(predicted_generic, truth_generic),
                "PA_generic": parsing_accuracy_generic(predicted_templates, truth),
                "runtime_seconds": elapsed,
                "runtime_per_100_logs_seconds": elapsed / max(len(raw_logs), 1) * 100,
                "template_count": len(set(predicted_clusters)),
                "singleton_count": sum(1 for key in set(predicted_clusters) if predicted_clusters.count(key) == 1),
            }
        )

    if out is not None:
        save_json(out, {"results": results})

    table = Table(title="Benchmark")
    for column in ["method", "GA_exact", "PA_generic", "runtime_per_100_logs_seconds", "template_count", "singleton_count"]:
        table.add_column(column)
    for item in results:
        table.add_row(
            item["method"],
            f"{item['GA_exact']:.6f}",
            f"{item['PA_generic']:.6f}",
            f"{item['runtime_per_100_logs_seconds']:.6f}",
            str(item["template_count"]),
            str(item["singleton_count"]),
        )
    console.print(table)


@app.command("perf-benchmark")
def perf_benchmark(
    lines: list[int] = typer.Option(
        [10_000],
        "--lines",
        help="Synthetic line count. Repeat for multiple counts, e.g. --lines 10000 --lines 100000.",
    ),
    rule_mode: str = typer.Option("conservative", "--rule-mode"),
    out: Optional[Path] = typer.Option(None, "--out"),
) -> None:
    results = [performance_benchmark(count, rule_mode=rule_mode) for count in lines]
    payload = {"results": results}
    if out is not None:
        save_json(out, payload)

    table = Table(title="Performance Benchmark")
    table.add_column("Lines", justify="right")
    table.add_column("Stage")
    table.add_column("Seconds", justify="right")
    table.add_column("Lines/Sec", justify="right")
    table.add_column("Sec/100 Logs", justify="right")
    for result in results:
        for stage, values in result["stages"].items():
            table.add_row(
                str(result["line_count"]),
                stage,
                f"{values['seconds']:.6f}",
                f"{values['lines_per_second']:.2f}",
                f"{values['runtime_per_100_logs_seconds']:.6f}",
            )
    console.print(table)


@app.command()
def inspect(
    parsed: Path = typer.Argument(..., help="Parsed JSONL from logmask parse."),
    out: Optional[Path] = typer.Option(None, "--out"),
) -> None:
    summary = summarize_parsed(load_parsed_jsonl(parsed))
    if out is not None:
        save_json(out, summary)
    _print_summary(summary)


@app.command()
def drift(
    old: Path = typer.Argument(..., help="Older parsed JSONL."),
    new: Path = typer.Argument(..., help="Newer parsed JSONL."),
    out: Optional[Path] = typer.Option(None, "--out"),
) -> None:
    report_data = drift_report(load_parsed_jsonl(old), load_parsed_jsonl(new))
    if out is not None:
        save_json(out, report_data)
    console.print_json(json.dumps(report_data))


@app.command("diff-masks")
def diff_masks(
    old: Path = typer.Argument(...),
    new: Path = typer.Argument(...),
    out: Optional[Path] = typer.Option(None, "--out"),
) -> None:
    old_bundle = load_mask_bundle(old)
    new_bundle = load_mask_bundle(new)
    old_projection = {item["name"]: item for item in runtime_mask_projection(old_bundle)}
    new_projection = {item["name"]: item for item in runtime_mask_projection(new_bundle)}
    old_names = set(old_projection)
    new_names = set(new_projection)
    changed = sorted(
        name for name in old_names & new_names if old_projection[name] != new_projection[name]
    )
    diff = {
        "old_runtime_mask_sha256": runtime_mask_sha256(old_bundle),
        "new_runtime_mask_sha256": runtime_mask_sha256(new_bundle),
        "added": sorted(new_names - old_names),
        "removed": sorted(old_names - new_names),
        "changed": changed,
    }
    if out is not None:
        save_json(out, diff)
    console.print_json(json.dumps(diff))


@app.command("hash-bundle")
def hash_bundle(masks: Path = typer.Argument(...)) -> None:
    bundle = load_mask_bundle(masks)
    console.print_json(
        json.dumps(
            {
                "bundle_sha256": bundle_sha256(bundle),
                "runtime_mask_sha256": runtime_mask_sha256(bundle),
            }
        )
    )


@app.command("candidate-schema")
def candidate_schema(out: Optional[Path] = typer.Option(None, "--out", help="Optional JSON schema output path.")) -> None:
    schema = CandidateMaskBundle.model_json_schema()
    if out is not None:
        save_json(out, schema)
    console.print_json(json.dumps(schema))


if __name__ == "__main__":
    app()
