from pathlib import Path

from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.io import load_json, load_mask_bundle, load_parsed_jsonl
from logmask_drain.masking import Masker
from logmask_drain.synthesis_backends.rules import get_rule_masks


runner = CliRunner()


def fixture_path(name: str) -> Path:
    return Path(__file__).parent / "fixtures" / "realistic" / name


def test_conservative_masks_cover_realistic_values_without_broad_numbers_or_log_levels():
    lines = fixture_path("logs.txt").read_text(encoding="utf-8").splitlines()
    masked = Masker(get_rule_masks("conservative")).mask_lines(lines)
    rendered = "\n".join(line.masked for line in masked)

    assert "<VAR:DATETIME>" in rendered
    assert "<VAR:REQUEST_ID>" in rendered
    assert "<VAR:SESSION_ID>" in rendered
    assert "<VAR:UUID>" in rendered
    assert "<VAR:URL>" in rendered
    assert "<VAR:EMAIL>" in rendered
    assert "<VAR:PATH>" in rendered
    assert "<VAR:QUOTED_STRING>" in rendered
    assert "path=<VAR:PATH>" in rendered
    assert "INFO" in rendered and "WARN" in rendered and "ERROR" in rendered
    assert "status=200" in rendered
    assert "version=2" in rendered


def test_realistic_cli_report_additive_fields(tmp_path):
    logs = fixture_path("logs.txt")
    sample = fixture_path("sample.txt")
    masks = tmp_path / "masks.json"
    parsed = tmp_path / "parsed.jsonl"
    report = tmp_path / "report.json"

    result = runner.invoke(
        app,
        ["synthesize", str(sample), "--backend", "rules", "--out", str(masks)],
    )
    assert result.exit_code == 0, result.output
    assert load_mask_bundle(masks).masks

    result = runner.invoke(
        app,
        [
            "parse",
            str(logs),
            "--masks",
            str(masks),
            "--template-id-mode",
            "hash",
            "--out",
            str(parsed),
        ],
    )
    assert result.exit_code == 0, result.output
    rows = load_parsed_jsonl(parsed)
    assert len(rows) == 8

    result = runner.invoke(app, ["report", str(parsed), "--format", "json", "--out", str(report)])
    assert result.exit_code == 0, result.output
    summary = load_json(report)
    assert summary["mask_coverage_by_type"]
    assert "DATETIME" in summary["mask_coverage_by_type"]
    assert "top_unmasked_high_cardinality_tokens" in summary
    assert "singleton_template_examples" in summary
    assert "unmasked_high_cardinality_token_rate" in summary
    assert "recommendations" in summary
    assert summary["recommendations"]
    high_cardinality_tokens = {item["token"] for item in summary["top_unmasked_high_cardinality_tokens"]}
    assert all("<VAR:" not in token for token in high_cardinality_tokens)


def test_perf_benchmark_cli_is_deterministic_and_reports_throughput(tmp_path):
    out = tmp_path / "perf.json"
    result = runner.invoke(app, ["perf-benchmark", "--lines", "64", "--out", str(out)])

    assert result.exit_code == 0, result.output
    payload = load_json(out)
    result_data = payload["results"][0]
    assert result_data["line_count"] == 64
    for stage in ["synthesize", "mask", "parse", "report"]:
        assert result_data["stages"][stage]["lines_per_second"] > 0
        assert result_data["stages"][stage]["runtime_per_100_logs_seconds"] >= 0
