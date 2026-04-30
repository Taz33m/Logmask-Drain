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


def test_load_loghub_structured_csv_accepts_message_column_and_missing_line_id(tmp_path):
    structured = tmp_path / "message.csv"
    structured.write_text(
        "Message,EventTemplate\nfirst,<*>\nsecond,<*>\n",
        encoding="utf-8",
    )

    dataset = load_loghub_structured_csv(structured)

    assert dataset.content_column == "Message"
    assert dataset.cluster_column is None
    assert dataset.logs == ["first", "second"]
    assert dataset.clusters == ["<*>", "<*>"]


def test_load_loghub_structured_csv_keeps_order_for_duplicate_line_ids(tmp_path):
    structured = tmp_path / "duplicate-line-id.csv"
    structured.write_text(
        "LineId,Content,EventTemplate\n1,second,<*>\n1,first,<*>\n",
        encoding="utf-8",
    )

    dataset = load_loghub_structured_csv(structured)

    assert dataset.logs == ["second", "first"]


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
    by_method = {item["method"]: item for item in data["results"]}
    assert by_method["drain"]["GA_exact"] == 1.0
    assert by_method["drain"]["PA_generic"] == 0.0
    assert by_method["builtin"]["PA_generic"] == 1.0


def test_cli_benchmark_loghub_default_methods_and_missing_bundle_masks(tmp_path):
    out = tmp_path / "default.json"
    result = CliRunner().invoke(
        app,
        [
            "benchmark-loghub",
            "--structured",
            "tests/fixtures/loghub/structured.csv",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert {item["method"] for item in data["results"]} == {"drain", "builtin"}

    result = CliRunner().invoke(
        app,
        [
            "benchmark-loghub",
            "--structured",
            "tests/fixtures/loghub/structured.csv",
            "--methods",
            "bundle",
        ],
    )

    assert result.exit_code != 0
    assert "bundle" in result.output
    assert "masks" in result.output


def test_cli_benchmark_loghub_falls_back_to_template_clusters_when_event_id_absent(tmp_path):
    structured = tmp_path / "no-event-id.csv"
    structured.write_text(
        "LineId,Content,EventTemplate\n"
        "1,User alice logged in,User <*> logged in\n"
        "2,User bob logged in,User <*> logged in\n",
        encoding="utf-8",
    )
    out = tmp_path / "result.json"

    result = CliRunner().invoke(
        app,
        [
            "benchmark-loghub",
            "--structured",
            str(structured),
            "--methods",
            "drain",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["dataset"]["cluster_column"] is None
    assert data["results"][0]["GA_exact"] == 1.0
    assert data["results"][0]["PA_generic"] == 1.0


def test_cli_benchmark_loghub_rejects_missing_columns(tmp_path):
    structured = tmp_path / "bad.csv"
    structured.write_text("LineId,Message\n1,hello\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["benchmark-loghub", "--structured", str(structured)])

    assert result.exit_code != 0
    assert "EventTemplate column" in result.output
