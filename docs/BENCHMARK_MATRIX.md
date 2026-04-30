# Benchmark Matrix

Logmask-Drain v0.7 adds a reproducibility benchmark layer for parser/template
evaluation. It is designed to compare fixed parsing configurations without
turning optional model calls into hidden benchmark dependencies.

## Commands

Plain log file plus labeled templates:

```bash
logmask benchmark-matrix \
  --logs logs.txt \
  --ground-truth templates.csv \
  --methods simple_raw,builtin_simple \
  --out results.json
```

LogHub/LogHub-2k-style structured CSV:

```bash
logmask benchmark-loghub-matrix \
  --structured HDFS_2k.log_structured.csv \
  --methods simple_raw,builtin_simple,drain3_raw,builtin_drain3 \
  --label-source "LogHub-2k structured CSV EventTemplate/EventId" \
  --out results.json
```

The default matrix is:

```text
simple_raw,builtin_simple
```

## Methods

Raw parser baselines:

- `simple_raw`
- `drain3_raw`

Built-in conservative/aggressive masks:

- `builtin_simple`
- `builtin_drain3`

Saved user bundle:

- `bundle_simple`
- `bundle_drain3`

Saved API LLM bundle:

- `api_llm_simple`
- `api_llm_drain3`

Saved local llama.cpp bundle:

- `local_llm_simple`
- `local_llm_drain3`

Saved hybrid bundle:

- `hybrid_api_simple`
- `hybrid_api_drain3`
- `hybrid_local_simple`
- `hybrid_local_drain3`

`bundle_*` methods require `--masks`. LLM and hybrid methods prefer saved
bundles through `--api-llm-masks`, `--local-llm-masks`,
`--hybrid-api-masks`, or `--hybrid-local-masks`. If those are omitted, `--masks`
is used as a fallback.

Optional dependencies such as `drain3` produce `skipped` method rows when they
are unavailable. Use `--fail-on-skip` when CI should fail instead.

## Live Synthesis

Model-backed methods do not call providers by default. If no saved bundle is
available, they are marked `skipped`.

To explicitly run live synthesis during a benchmark:

```bash
logmask benchmark-matrix \
  --logs logs.txt \
  --ground-truth templates.csv \
  --methods api_llm_simple \
  --synthesize-missing \
  --provider openai \
  --model gpt-4.1-mini \
  --out live-results.json
```

Live synthesis is marked with `live_synthesis=true` in the result JSON. Treat
those results as diagnostics, not canonical reproducibility artifacts.

## Metrics

Each method reports:

- `GA_exact`
- `PA_generic`
- `PA_typed`, only when typed template labels are available
- `template_count`
- `singleton_count`
- `singleton_rate`
- `parse_runtime_seconds`
- `runtime_seconds_total`
- `runtime_per_100_logs_seconds`
- `mask_coverage`
- `accepted_mask_count`
- `rejected_mask_count`

`GA_exact` compares exact line-cluster membership. `PA_generic` normalizes
typed placeholders and generic placeholders to `<*>`. `PA_typed` compares typed
templates exactly after whitespace normalization.

## Result JSON

The result JSON records:

- schema version
- Logmask version, Python version, and platform
- dataset metadata and label provenance
- sample metadata and sample hash
- one method result per matrix method

This is a parser-evaluation artifact. It is not a claim of parity with the
DeepParse paper's LogHub-scale results.
