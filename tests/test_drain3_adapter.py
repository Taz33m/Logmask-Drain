import sys
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

from logmask_drain import drain_adapter
from logmask_drain.cli import app
from logmask_drain.io import load_parsed_jsonl


runner = CliRunner()


class FakeTemplateMinerConfig:
    def __init__(self):
        self.drain_sim_th = 0.4
        self.profiling_enabled = True
        self.parametrize_numeric_tokens = True


class FakeTemplateMiner:
    configs: list[FakeTemplateMinerConfig] = []

    def __init__(self, *, config):
        self.config = config
        self.configs.append(config)

    def add_log_message(self, log_message: str) -> dict:
        if "request_id=" in log_message:
            return {
                "cluster_id": 7,
                "template_mined": "svc request_id=<VAR:REQUEST_ID> status=<*>",
            }
        return {"cluster_id": 8, "template_mined": log_message}


def install_fake_drain3(monkeypatch):
    FakeTemplateMiner.configs = []
    drain3_module = types.ModuleType("drain3")
    drain3_module.TemplateMiner = FakeTemplateMiner
    config_module = types.ModuleType("drain3.template_miner_config")
    config_module.TemplateMinerConfig = FakeTemplateMinerConfig
    monkeypatch.setitem(sys.modules, "drain3", drain3_module)
    monkeypatch.setitem(sys.modules, "drain3.template_miner_config", config_module)
    monkeypatch.setattr(drain_adapter.metadata, "version", lambda package: "0.9.fake")


def fixture_path(name: str):
    return Path(__file__).parent / "fixtures" / "toy" / name


def test_drain3_adapter_uses_optional_dependency_and_parser_config(monkeypatch):
    install_fake_drain3(monkeypatch)
    parser = drain_adapter.get_parser("drain3", similarity_threshold=0.73)

    assignments = parser.parse_all(["svc request_id=<VAR:REQUEST_ID> status=200"], template_id_mode="hash")

    assert parser.engine == "drain3"
    assert parser.engine_version == "0.9.fake"
    assert parser.tokenizer_version == "drain3_default_v1"
    assert assignments[0].template == "svc request_id=<VAR:REQUEST_ID> status=<*>"
    assert assignments[0].template_hash.startswith("sha1:")
    assert assignments[0].template_id.startswith("T")
    assert not assignments[0].template_id.startswith("T000")
    assert FakeTemplateMiner.configs[0].drain_sim_th == 0.73
    assert FakeTemplateMiner.configs[0].profiling_enabled is False
    assert FakeTemplateMiner.configs[0].parametrize_numeric_tokens is False


def test_drain3_sequential_ids_are_readable(monkeypatch):
    install_fake_drain3(monkeypatch)
    parser = drain_adapter.get_parser("drain3")

    assignments = parser.parse_all(
        [
            "svc request_id=<VAR:REQUEST_ID> status=200",
            "other static line",
            "svc request_id=<VAR:REQUEST_ID> status=500",
        ]
    )

    assert [item.template_id for item in assignments] == ["T000001", "T000002", "T000001"]


def test_drain3_missing_optional_dependency_error(monkeypatch):
    def fail_load():
        raise ValueError("engine=drain3 requires the optional dependency")

    monkeypatch.setattr(drain_adapter, "_load_drain3_components", fail_load)

    with pytest.raises(ValueError, match="optional dependency"):
        drain_adapter.get_parser("drain3")


def test_cli_parse_with_drain3_records_engine_metadata(monkeypatch, tmp_path):
    install_fake_drain3(monkeypatch)
    raw = fixture_path("raw.log")
    masks = tmp_path / "masks.json"
    parsed = tmp_path / "parsed.jsonl"

    result = runner.invoke(app, ["synthesize", str(raw), "--backend", "rules", "--out", str(masks)])
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "parse",
            str(raw),
            "--masks",
            str(masks),
            "--engine",
            "drain3",
            "--template-id-mode",
            "hash",
            "--out",
            str(parsed),
        ],
    )

    assert result.exit_code == 0, result.output
    rows = load_parsed_jsonl(parsed)
    assert rows[0].parser.engine == "drain3"
    assert rows[0].parser.engine_version == "0.9.fake"
    assert rows[0].parser.tokenizer_version == "drain3_default_v1"
    assert rows[0].parser.template_id_mode == "hash"
