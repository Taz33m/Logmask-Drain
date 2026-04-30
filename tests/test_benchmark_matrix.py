from pathlib import Path

from typer.testing import CliRunner

from logmask_drain.cli import app
from logmask_drain.io import load_json
from logmask_drain.models import CandidateMask, CandidateMaskBundle


runner = CliRunner()


def toy_path(name: str) -> str:
    return str(Path("tests/fixtures/toy") / name)


def matrix_path(name: str) -> str:
    return str(Path("tests/fixtures/benchmark_matrix") / name)


class FakeApiProvider:
    provider_name = "fake-api"

    def generate_candidates(self, *_args, **_kwargs):
        return CandidateMaskBundle(
            candidates=[
                CandidateMask(
                    name="request_id_assignment",
                    type="REQUEST_ID",
                    pattern=r"\brequest[_-]?id=([A-Za-z0-9_.:-]+)\b",
                    value_group=1,
                    replacement="<VAR:REQUEST_ID>",
                    priority=86,
                    flags=["IGNORECASE"],
                )
            ]
        )


def test_cli_benchmark_matrix_default_outputs_schema_and_typed_pa(tmp_path):
    out = tmp_path / "matrix.json"

    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            matrix_path("templates_typed.csv"),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["schema_version"] == "0.1"
    assert data["dataset"]["format"] == "plain_csv"
    assert data["dataset"]["typed_template_column"] == "typed_template"
    assert data["sample"]["sampler"] == "entropy_greedy"
    by_method = {item["method_id"]: item for item in data["methods"]}
    assert set(by_method) == {"simple_raw", "builtin_simple"}
    assert by_method["simple_raw"]["status"] == "passed"
    assert by_method["builtin_simple"]["status"] == "passed"
    assert by_method["simple_raw"]["PA_typed"] == 0.0
    assert by_method["builtin_simple"]["PA_typed"] == 1.0
    assert by_method["builtin_simple"]["runtime_per_100_logs_seconds"] is not None


def test_cli_benchmark_matrix_requires_masks_for_bundle_methods():
    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            toy_path("templates.csv"),
            "--methods",
            "bundle_simple",
        ],
    )

    assert result.exit_code != 0
    assert "bundle" in result.output
    assert "masks" in result.output


def test_cli_benchmark_matrix_skips_missing_drain3_and_fail_on_skip(monkeypatch, tmp_path):
    def missing_parser(engine: str, **_kwargs):
        if engine == "drain3":
            raise ValueError("engine=drain3 requires the optional dependency")
        raise AssertionError(engine)

    monkeypatch.setattr("logmask_drain.benchmarking.get_parser", missing_parser)
    out = tmp_path / "drain3.json"
    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            toy_path("templates.csv"),
            "--methods",
            "drain3_raw",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["methods"][0]["status"] == "skipped"

    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            toy_path("templates.csv"),
            "--methods",
            "drain3_raw",
            "--fail-on-skip",
        ],
    )

    assert result.exit_code == 1


def test_cli_benchmark_matrix_llm_methods_do_not_call_provider_without_live_synthesis(monkeypatch, tmp_path):
    def provider_should_not_be_called(_provider_name: str):
        raise AssertionError("provider should not be called")

    monkeypatch.setattr("logmask_drain.benchmarking.get_api_provider", provider_should_not_be_called)
    out = tmp_path / "llm-skipped.json"
    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            toy_path("templates.csv"),
            "--methods",
            "api_llm_simple",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["methods"][0]["status"] == "skipped"
    assert data["methods"][0]["live_synthesis"] is False


def test_cli_benchmark_matrix_live_api_synthesis_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr("logmask_drain.benchmarking.get_api_provider", lambda _provider: FakeApiProvider())
    out = tmp_path / "llm-live.json"

    result = runner.invoke(
        app,
        [
            "benchmark-matrix",
            "--logs",
            toy_path("raw.log"),
            "--ground-truth",
            toy_path("templates.csv"),
            "--methods",
            "api_llm_simple",
            "--synthesize-missing",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    method = data["methods"][0]
    assert method["status"] == "passed"
    assert method["live_synthesis"] is True
    assert method["mask_source"] == "live_synthesis"
    assert method["accepted_mask_count"] == 1


def test_cli_benchmark_loghub_matrix_uses_event_id_and_typed_templates(tmp_path):
    out = tmp_path / "loghub-matrix.json"

    result = runner.invoke(
        app,
        [
            "benchmark-loghub-matrix",
            "--structured",
            matrix_path("loghub_typed.csv"),
            "--methods",
            "simple_raw,builtin_simple",
            "--label-source",
            "typed fixture",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    data = load_json(out)
    assert data["dataset"]["format"] == "loghub_structured_csv"
    assert data["dataset"]["cluster_column"] == "EventId"
    assert data["dataset"]["typed_template_column"] == "TypedEventTemplate"
    by_method = {item["method_id"]: item for item in data["methods"]}
    assert by_method["simple_raw"]["GA_exact"] == 1.0
    assert by_method["builtin_simple"]["PA_typed"] == 1.0
