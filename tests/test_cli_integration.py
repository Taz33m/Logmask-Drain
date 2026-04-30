from pathlib import Path

from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.io import load_json, load_mask_bundle, load_parsed_jsonl


runner = CliRunner()


def fixture_path(name: str) -> Path:
    return Path(__file__).parent / "fixtures" / "toy" / name


def test_cli_synthesize_mask_parse_report_benchmark(tmp_path):
    raw = fixture_path("raw.log")
    truth = fixture_path("templates.csv")
    masks = tmp_path / "masks.json"
    masked = tmp_path / "masked.jsonl"
    parsed = tmp_path / "parsed.jsonl"
    report = tmp_path / "report.json"
    benchmark = tmp_path / "benchmark.json"

    result = runner.invoke(
        app,
        ["synthesize", str(raw), "--backend", "rules", "--out", str(masks)],
    )
    assert result.exit_code == 0, result.output
    bundle = load_mask_bundle(masks)
    assert bundle.masks

    result = runner.invoke(
        app,
        ["validate-masks", str(masks), "--logs", str(raw), "--strict", "--out", str(masks)],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["mask", str(raw), "--masks", str(masks), "--out", str(masked)])
    assert result.exit_code == 0, result.output
    assert masked.read_text(encoding="utf-8")

    result = runner.invoke(app, ["parse", str(raw), "--masks", str(masks), "--out", str(parsed)])
    assert result.exit_code == 0, result.output
    rows = load_parsed_jsonl(parsed)
    assert rows[0].template_hash.startswith("sha1:")
    assert rows[0].parser.runtime_mask_sha256
    assert rows[0].parser.template_id_mode == "sequential"
    for row in rows:
        for variable in row.variables:
            assert row.raw[variable.start : variable.end] == variable.value

    parsed_again = tmp_path / "parsed_again.jsonl"
    result = runner.invoke(app, ["parse", str(raw), "--masks", str(masks), "--out", str(parsed_again)])
    assert result.exit_code == 0, result.output
    assert parsed.read_text(encoding="utf-8") == parsed_again.read_text(encoding="utf-8")

    result = runner.invoke(app, ["report", str(parsed), "--format", "json", "--out", str(report)])
    assert result.exit_code == 0, result.output
    summary = load_json(report)
    assert summary["line_count"] == 4

    default_benchmark = tmp_path / "default_benchmark.json"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--logs",
            str(raw),
            "--ground-truth",
            str(truth),
            "--out",
            str(default_benchmark),
        ],
    )
    assert result.exit_code == 0, result.output
    default_data = load_json(default_benchmark)
    assert {item["method"] for item in default_data["results"]} == {"drain", "builtin"}

    result = runner.invoke(
        app,
        [
            "benchmark",
            "--logs",
            str(raw),
            "--ground-truth",
            str(truth),
            "--methods",
            "bundle",
        ],
    )
    assert result.exit_code != 0
    assert "bundle" in result.output
    assert "masks" in result.output

    result = runner.invoke(
        app,
        [
            "benchmark",
            "--logs",
            str(raw),
            "--ground-truth",
            str(truth),
            "--methods",
            "drain,builtin,bundle",
            "--masks",
            str(masks),
            "--out",
            str(benchmark),
        ],
    )
    assert result.exit_code == 0, result.output
    data = load_json(benchmark)
    assert {item["method"] for item in data["results"]} == {"drain", "builtin", "bundle"}


def test_cli_drift_detects_new_templates(tmp_path):
    raw = fixture_path("raw.log")
    masks = tmp_path / "masks.json"
    old_parsed = tmp_path / "old.jsonl"
    new_logs = tmp_path / "new.log"
    new_parsed = tmp_path / "new.jsonl"
    drift = tmp_path / "drift.json"

    runner.invoke(app, ["synthesize", str(raw), "--backend", "rules", "--out", str(masks)])
    runner.invoke(app, ["parse", str(raw), "--masks", str(masks), "--out", str(old_parsed)])
    new_logs.write_text(
        raw.read_text(encoding="utf-8") + "new static shape without masked values\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["parse", str(new_logs), "--masks", str(masks), "--out", str(new_parsed)])

    result = runner.invoke(app, ["drift", str(old_parsed), str(new_parsed), "--out", str(drift)])
    assert result.exit_code == 0, result.output
    data = load_json(drift)
    assert data["new_template_rate"] > 0


def test_hash_template_id_mode_is_stable_across_input_order(tmp_path):
    raw = fixture_path("raw.log")
    masks = tmp_path / "masks.json"
    parsed = tmp_path / "parsed.jsonl"
    reversed_logs = tmp_path / "reversed.log"
    reversed_parsed = tmp_path / "reversed.jsonl"

    runner.invoke(app, ["synthesize", str(raw), "--backend", "rules", "--out", str(masks)])
    reversed_logs.write_text(
        "\n".join(reversed(raw.read_text(encoding="utf-8").splitlines())) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "parse",
            str(raw),
            "--masks",
            str(masks),
            "--template-id-mode",
            "hash",
            "--out",
            str(parsed),
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "parse",
            str(reversed_logs),
            "--masks",
            str(masks),
            "--template-id-mode",
            "hash",
            "--out",
            str(reversed_parsed),
        ],
    )
    assert result.exit_code == 0, result.output

    mapping = {row.template_hash: row.template_id for row in load_parsed_jsonl(parsed)}
    reversed_mapping = {row.template_hash: row.template_id for row in load_parsed_jsonl(reversed_parsed)}
    assert mapping == reversed_mapping
    assert all(value.startswith("T") and not value.startswith("T000") for value in mapping.values())
