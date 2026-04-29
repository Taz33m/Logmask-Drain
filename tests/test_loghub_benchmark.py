from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.datasets import load_loghub_structured_csv
from logmask_drain.io import load_json


def test_load_loghub_structured_csv_uses_explicit_columns_and_sorts_line_ids():
    dataset = load_loghub_structured_csv("tests/fixtures/loghub/structured.csv", label_source="fixture")

    assert dataset.label_source == "fixture"
    assert dataset.content_column == "Content"
    assert dataset.template_column == "EventTemplate"
    assert dataset.cluster_column == "EventId"
    assert dataset.logs[0].endswith("10.0.0.1")
    assert dataset.clusters == ["E1", "E1", "E2", "E2"]


def test_cli_benchmark_loghub_writes_label_provenance(tmp_path):
    masks = tmp_path / "masks.json"
    result = CliRunner().invoke(
        app,
        [
            "synthesize",
            "tests/fixtures/loghub/structured.csv",
            "--backend",
            "rules",
            "--out",
            str(masks),
        ],
    )
    assert result.exit_code == 0, result.output

    out = tmp_path / "loghub-benchmark.json"
    result = CliRunner().invoke(
        app,
        [
            "benchmark-loghub",
            "--structured",
            "tests/fixtures/loghub/structured.csv",
            "--methods",
            "drain,builtin,bundle",
            "--masks",
            str(masks),
            "--label-source",
            "fixture labels",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["dataset"]["format"] == "loghub_structured_csv"
    assert data["dataset"]["label_source"] == "fixture labels"
    assert data["dataset"]["cluster_column"] == "EventId"
    assert {item["method"] for item in data["results"]} == {"drain", "builtin", "bundle"}


def test_cli_benchmark_loghub_rejects_missing_columns(tmp_path):
    structured = tmp_path / "bad.csv"
    structured.write_text("LineId,Message\n1,hello\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["benchmark-loghub", "--structured", str(structured)])

    assert result.exit_code != 0
    assert "EventTemplate column" in result.output
