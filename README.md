<div align="center">

<img src="assets/logo.png" alt="Logmask-Drain logo" width="230">

# Logmask-Drain

**CPU-first log parsing with validated regex mask bundles and deterministic Drain-style templates.**

> Use the model once. Parse locally forever.

<p>
  <a href="https://github.com/Taz33m/Logmask-Drain/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/Taz33m/Logmask-Drain/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version 0.7.0" src="https://img.shields.io/badge/version-0.7.0-blue">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="CPU first" src="https://img.shields.io/badge/CPU--first-success">
  <img alt="Network free default" src="https://img.shields.io/badge/network--free-default-success">
  <img alt="LLM optional" src="https://img.shields.io/badge/LLM-optional-7C3AED">
</p>

<p>
  <a href="https://youtu.be/2YwAi0M_Jps"><b>Watch the 90-second demo</b></a>
  ·
  <a href="https://arxiv.org/abs/2604.20553"><b>DeepParse paper</b></a>
  ·
  <a href="docs/BENCHMARK_MATRIX.md"><b>Benchmark matrix</b></a>
  ·
  <a href="docs/ROADMAP.md"><b>Roadmap</b></a>
</p>

</div>

Logmask-Drain turns unstable values such as request IDs, IPs, paths, UUIDs,
and timestamps into typed placeholders before Drain-style parsing. The same
event becomes one stable template instead of many fragmented ones.

## 10-Second Example

Raw logs:

```text
INFO user=alice request_id=abc123 ip=10.0.4.9 path=/api/v1/users status=200
INFO user=bob   request_id=xyz789 ip=10.0.4.12 path=/api/v1/users status=200
```

Mask-first parsing:

```text
INFO user=<VAR:USERNAME> request_id=<VAR:REQUEST_ID> ip=<VAR:IP> path=<VAR:PATH> status=200
```

Deterministic JSONL output:

```json
{
  "template_hash": "sha1:...",
  "template": "INFO user=<VAR:USERNAME> request_id=<VAR:REQUEST_ID> ip=<VAR:IP> path=<VAR:PATH> status=200"
}
```

Default workflow: **no GPU, no model download, no API key, and no network
access at runtime.**

## Install

From GitHub:

```bash
python -m pip install "git+https://github.com/Taz33m/Logmask-Drain.git"
```

From a local checkout:

```bash
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install ".[api-llm]"   # OpenAI API candidate-mask synthesis
python -m pip install ".[drain3]"    # optional Drain3 parser adapter
python -m pip install ".[yaml]"      # YAML mask-bundle loading
```

## Quickstart

```bash
logmask synthesize sample.txt \
  --backend rules \
  --rule-mode conservative \
  --out masks.json

logmask validate-masks masks.json \
  --logs sample.txt \
  --strict

logmask parse logs.txt \
  --masks masks.json \
  --template-id-mode hash \
  --out parsed.jsonl

logmask report parsed.jsonl
```

Run `logmask --help` for the full CLI.

## Why It Exists

Raw log parsers often split one event into many templates because values look
like structure. Per-line LLM parsing can recover intent, but it is expensive,
non-deterministic, and awkward for private operational logs.

Logmask-Drain takes the middle path:

- synthesize or load reusable masks offline,
- validate every regex locally,
- preserve static context such as `request_id=`,
- replace only values with typed placeholders,
- parse future logs locally from a saved bundle.

## DeepParse Connection

Logmask-Drain is an architecture-first implementation of the core idea behind
**DeepParse: Hybrid Log Parsing with LLM-Synthesized Regex Masks**
([arXiv:2604.20553](https://arxiv.org/abs/2604.20553)):

```text
raw logs -> sample representative lines -> synthesize/load candidate masks
         -> validate locally -> save masks.json
         -> mask-first parsing -> deterministic JSONL templates
```

The LLM path never produces trusted runtime configuration directly. It produces
candidate masks. The local validator decides what survives.

## What It Is Not

Logmask-Drain is not the DeepParse authors' official artifact. It does not:

- ship the paper authors' fine-tuned DeepSeek-R1 checkpoint,
- reproduce the full paper-scale benchmark,
- include the LogBERT downstream anomaly-detection case study.

It implements the practical product boundary:

> fixed masks in, deterministic templates out.

## Mask Bundle Contract

Mask bundles are the reproducible boundary between offline synthesis and online
parsing. Runtime-relevant fields are canonically hashed as
`runtime_mask_sha256`, so parsing output can be audited and compared across
machines.

```json
{
  "name": "request_id_assignment",
  "type": "REQUEST_ID",
  "pattern": "\\brequest[_-]?id=([A-Za-z0-9_.:-]+)\\b",
  "value_group": 1,
  "replacement": "<VAR:REQUEST_ID>",
  "priority": 80,
  "enabled": true,
  "flags": ["IGNORECASE"]
}
```

With `value_group`, Logmask-Drain keeps the key and masks only the value:

```text
request_id=abc123 -> request_id=<VAR:REQUEST_ID>
```

## Safety Boundary

Strict validation rejects masks that are unsafe, broken, empty, too broad, or
semantically harmful for log parsing. This includes:

- unsupported regex flags,
- invalid `value_group` references,
- empty selected spans,
- catastrophic-looking regex structures,
- over-broad full-line captures,
- masks that hide log levels by default,
- duplicate match-equivalent masks,
- placeholder/type mismatches,
- excessive sample character coverage.

Validation examples are redacted by default. Raw examples require explicit
opt-in.

## Optional LLM Synthesis

Rules are the default and require no network. API and local LLM backends are
optional candidate generators that still pass through the same local validator.

API example:

```bash
python -m pip install ".[api-llm]"

logmask synthesize sample.txt \
  --backend api-llm \
  --provider openai \
  --model gpt-4.1-mini \
  --max-api-sample-lines 100 \
  --max-api-sample-chars 50000 \
  --candidate-report candidates.json \
  --out masks.llm.json
```

Local llama.cpp example:

```bash
logmask synthesize sample.txt \
  --backend local-llm \
  --local-provider llama-cpp \
  --llama-cli llama-cli \
  --model-path ./models/mask-synth.gguf \
  --candidate-report local-candidates.json \
  --out masks.local.json
```

Oversized API samples are rejected by default so a production log file is not
sent to a provider by accident. Use `logmask sample` first, or pass
`--allow-large-api-sample` only after reviewing the data.

## Parser Engines

`simple_drain` is the default parser engine. It is deterministic and has no
optional dependencies.

```bash
logmask parse logs.txt \
  --masks masks.json \
  --engine simple_drain \
  --template-id-mode hash \
  --out parsed.jsonl
```

Drain3 is optional:

```bash
python -m pip install ".[drain3]"

logmask parse logs.txt \
  --masks masks.json \
  --engine drain3 \
  --template-id-mode hash \
  --out parsed.drain3.jsonl
```

Template strings and hashes may differ by engine. Parsed JSONL records parser
metadata so results remain auditable.

## Benchmarking

Toy benchmark:

```bash
logmask benchmark \
  --logs tests/fixtures/toy/logs.txt \
  --ground-truth tests/fixtures/toy/templates.csv \
  --methods drain,builtin
```

Benchmark matrix:

```bash
logmask benchmark-matrix \
  --logs logs.txt \
  --ground-truth templates.csv \
  --methods simple_raw,builtin_simple,bundle_simple \
  --masks masks.json \
  --out matrix-results.json
```

LogHub-style structured CSV benchmark:

```bash
logmask benchmark-loghub-matrix \
  --structured HDFS_2k.log_structured.csv \
  --methods simple_raw,builtin_simple,drain3_raw,builtin_drain3 \
  --label-source "LogHub-2k structured CSV EventTemplate/EventId" \
  --out loghub-matrix.json
```

Logmask-Drain does not bundle LogHub data and does not make paper-scale
accuracy claims. The benchmark layer exists to make parser/template behavior
inspectable and reproducible.

Reported metrics include `GA_exact`, `PA_generic`, nullable `PA_typed`,
template count, singleton rate, runtime, mask coverage, and accepted/rejected
mask counts.

## Documentation

| Document | Description |
| --- | --- |
| [Product Requirements](docs/PRD.md) | Scope, non-goals, and release philosophy. |
| [Benchmark Matrix](docs/BENCHMARK_MATRIX.md) | Reproducibility benchmark schema and method IDs. |
| [LogHub Benchmarks](docs/LOGHUB_BENCHMARKS.md) | LogHub-style CSV contract and credibility notes. |
| [Local LLM](docs/LOCAL_LLM.md) | llama.cpp synthesis workflow. |
| [Mask Tuning](docs/MASK_TUNING.md) | Operational mask tuning guidance. |
| [Engineering Review](docs/REVIEW.md) | Current review notes and risks. |
| [Roadmap](docs/ROADMAP.md) | Planned milestones. |
| [PyPI Checklist](docs/PYPI_RELEASE_CHECKLIST.md) | Release checklist. |
| [Security Policy](SECURITY.md) | Supported versions, sensitive artifacts, and reporting guidance. |

## Development

```bash
python -m pip install -e ".[dev]" build twine
python -m pytest -q
python -m build
python -m twine check dist/*
```

Live provider tests are opt-in:

```bash
LOGMASK_RUN_LIVE_LLM_TESTS=1 python -m pytest tests/test_live_api_llm.py -q
LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS=1 python -m pytest tests/test_live_local_llm.py -q
```

## License

MIT. See [LICENSE](LICENSE).

## Citation And Attribution

Logmask-Drain is inspired by the DeepParse paper's offline synthesis /
deterministic execution split:

```bibtex
@misc{deepparse2026,
  title         = {DeepParse: Hybrid Log Parsing with LLM-Synthesized Regex Masks},
  year          = {2026},
  eprint        = {2604.20553},
  archivePrefix = {arXiv}
}
```

Please cite the paper for the research idea and this repository for this
implementation.
