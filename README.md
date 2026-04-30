# Logmask-Drain

Logmask-Drain is a CPU-first implementation of the DeepParse architectural idea:
offline mask-bundle generation plus deterministic mask-first Drain-style parsing.

It is **not** a reproduction of the DeepParse paper's fine-tuned DeepSeek-R1
checkpoint, LogHub-scale benchmark, or LogBERT downstream case study. The goal
is a local, reproducible parser boundary: fixed masks in, deterministic
templates out.

The default path is intentionally local and lightweight:

```bash
logmask synthesize sample.txt --backend rules --rule-mode conservative --out masks.json
logmask validate-masks masks.json --logs sample.txt --strict
logmask mask logs.txt --masks masks.json --out masked.jsonl
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
logmask report parsed.jsonl
logmask perf-benchmark --lines 10000 --lines 100000
```

No GPU, model download, API key, or network access is required.

## What the Current Release Includes

- Rule-based conservative and aggressive mask synthesis.
- Optional API LLM candidate-mask synthesis behind strict local validation.
- API LLM candidate reports, schema export, provider timeout, and retry knobs.
- Optional local llama.cpp candidate-mask synthesis behind the same strict
  validation boundary.
- Strict regex validation with timeout, empty-match, over-broadness, and
  catastrophic-pattern checks.
- Context-preserving `value_group` replacement.
- Deterministic overlap resolution.
- Original span preservation for extracted values.
- Stable `template_hash` and optional hash-derived `template_id`.
- `runtime_mask_sha256` for reproducible parsing metadata.
- `simple_drain` fallback parser.
- Optional `drain3` parser adapter. `simple_drain` remains the default.
- JSONL output, report, inspect, drift, diff, sample, and benchmark commands.
- GitHub Actions CI on Python 3.11, 3.12, and 3.13.
- Fresh-wheel install smoke tests.
- Realistic fixtures with mixed timestamp formats, UUIDs, request/session IDs,
  paths, URLs, quoted strings, interleaved services, and static numeric values
  that conservative mode should preserve.
- Report fields for mask coverage by type, singleton template examples,
  unmasked high-cardinality tokens, and deterministic recommendations.
- Synthetic performance benchmarks for `synthesize`, `mask`, `parse`, and
  `report`.
- LogHub-compatible structured CSV benchmark harness with explicit label
  provenance.

## Optional API LLM Synthesis

API LLM synthesis is opt-in. The LLM proposes candidate masks only; candidates
must pass the same local safety gate before they can enter a saved runtime
bundle.

Install the optional dependency when using the API backend:

```bash
pip install "logmask-drain[api-llm]"
```

Generate LLM candidates:

```bash
logmask synthesize sample.txt \
  --backend api-llm \
  --provider openai \
  --model gpt-4.1-mini \
  --provider-timeout-seconds 60 \
  --provider-max-retries 1 \
  --max-api-sample-lines 100 \
  --max-api-sample-chars 50000 \
  --candidate-report candidates.json \
  --out masks.llm.json
```

API synthesis refuses oversized samples by default. Use `logmask sample` first,
or pass `--allow-large-api-sample` explicitly when you have reviewed what will
be sent to the provider.

Export the candidate-mask schema used for API LLM structured outputs:

```bash
logmask candidate-schema --out candidate-schema.json
```

Hybrid mode is explicit:

```bash
logmask synthesize sample.txt \
  --backend api-llm \
  --provider openai \
  --model gpt-4.1-mini \
  --base-rules conservative \
  --out masks.hybrid.json
```

The default `rules` backend remains network-free.

## Optional Local LLM Synthesis

Local LLM synthesis is opt-in and uses an external `llama-cli` executable from
llama.cpp. The local model proposes candidate masks only; candidates still pass
the same local validation gate before they can enter a runtime bundle.

```bash
logmask synthesize sample.txt \
  --backend local-llm \
  --local-provider llama-cpp \
  --llama-cli llama-cli \
  --model-path ./models/mask-synth.gguf \
  --max-local-sample-lines 200 \
  --max-local-sample-chars 100000 \
  --candidate-report local-candidates.json \
  --out masks.local.json
```

Local synthesis refuses oversized prompts by default. Use `logmask sample`
first, or pass `--allow-large-local-sample` explicitly when you have reviewed
the prompt size.

Hybrid local mode is explicit:

```bash
logmask synthesize sample.txt \
  --backend local-llm \
  --model-path ./models/mask-synth.gguf \
  --base-rules conservative \
  --out masks.local-hybrid.json
```

## Optional Drain3 Parser

`simple_drain` is the default parser engine. To compare against the real
`drain3` implementation, install the optional extra:

```bash
pip install "logmask-drain[drain3]"
```

Then parse with:

```bash
logmask parse logs.txt \
  --masks masks.json \
  --engine drain3 \
  --template-id-mode hash \
  --out parsed.drain3.jsonl
```

Logmask still applies the saved mask bundle before the parser sees any line.
The `drain3` adapter disables Drain3-side numeric parametrization so runtime
masks remain the explicit parsing boundary. Template strings and hashes may
differ between `simple_drain` and `drain3`; parsed JSONL records
`parser.engine` and `parser.engine_version` for auditability.

## Toy Benchmark

The included toy fixture is intentionally constructed to demonstrate
variable-boundary failures:

| method | GA_exact | PA_generic |
| --- | ---: | ---: |
| drain | 1.0 | 0.0 |
| builtin | 1.0 | 1.0 |
| bundle | 1.0 | 1.0 |

Real-world accuracy requires evaluation on representative logs.

## Throughput Checks

Run deterministic synthetic throughput checks with:

```bash
logmask perf-benchmark --lines 10000 --lines 100000 --out perf.json
```

## LogHub-Compatible Benchmarks

Use structured CSV files with explicit label provenance:

```bash
logmask benchmark-loghub \
  --structured HDFS_2k.log_structured.csv \
  --methods drain,builtin,bundle \
  --masks masks.json \
  --label-source "LogHub structured CSV EventTemplate/EventId" \
  --out loghub-results.json
```

Logmask-Drain does not bundle LogHub datasets or make LogHub-scale accuracy
claims. See [docs/LOGHUB_BENCHMARKS.md](docs/LOGHUB_BENCHMARKS.md) for the
benchmark contract and reporting caveats.

See [docs/PRD.md](docs/PRD.md) for the product direction and
[docs/REVIEW.md](docs/REVIEW.md) for the current engineering review. For
operational mask tuning, see [docs/MASK_TUNING.md](docs/MASK_TUNING.md). For
LogHub-compatible evaluation, see
[docs/LOGHUB_BENCHMARKS.md](docs/LOGHUB_BENCHMARKS.md). For local model
operations, see [docs/LOCAL_LLM.md](docs/LOCAL_LLM.md). For roadmap and release
planning, see [docs/ROADMAP.md](docs/ROADMAP.md) and
[docs/PYPI_RELEASE_CHECKLIST.md](docs/PYPI_RELEASE_CHECKLIST.md).

## Template IDs

Sequential IDs are readable but order-dependent:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode sequential --out parsed.jsonl
```

Hash IDs are stable across shards and input ordering:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
```
