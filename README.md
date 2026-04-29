# Logmask-Drain

Logmask-Drain is a CPU-first implementation of the DeepParse architectural idea:
offline mask-bundle generation plus deterministic mask-first Drain-style parsing.

It is **not** a reproduction of the DeepParse paper's fine-tuned DeepSeek-R1
checkpoint, LogHub-scale benchmark, or LogBERT downstream case study. The goal
of v0.1 is a local, reproducible parser boundary: fixed masks in, deterministic
templates out.

The v0.1 path is intentionally local and lightweight:

```bash
logmask synthesize sample.txt --backend rules --rule-mode conservative --out masks.json
logmask validate-masks masks.json --logs sample.txt --strict
logmask mask logs.txt --masks masks.json --out masked.jsonl
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
logmask report parsed.jsonl
logmask perf-benchmark --lines 10000 --lines 100000
```

No GPU, model download, API key, or network access is required.

## What v0.1 Includes

- Rule-based conservative and aggressive mask synthesis.
- Strict regex validation with timeout, empty-match, over-broadness, and
  catastrophic-pattern checks.
- Context-preserving `value_group` replacement.
- Deterministic overlap resolution.
- Original span preservation for extracted values.
- Stable `template_hash` and optional hash-derived `template_id`.
- `runtime_mask_sha256` for reproducible parsing metadata.
- `simple_drain` fallback parser.
- JSONL output, report, inspect, drift, diff, sample, and benchmark commands.
- Synthetic performance benchmarks for `synthesize`, `mask`, `parse`, and
  `report`.

## Toy Benchmark

The included toy fixture is intentionally constructed to demonstrate
variable-boundary failures:

| method | GA_exact | PA_generic |
| --- | ---: | ---: |
| drain | 1.0 | 0.0 |
| builtin | 1.0 | 1.0 |
| bundle | 1.0 | 1.0 |

Real-world accuracy requires evaluation on representative logs.

## v0.2 Development Focus

The current development line adds real-log hardening without introducing LLM
synthesis:

- GitHub Actions CI on Python 3.11, 3.12, and 3.13.
- Fresh-wheel install smoke tests.
- Realistic fixtures with mixed timestamp formats, UUIDs, request/session IDs,
  paths, URLs, quoted strings, interleaved services, and static numeric values
  that conservative mode should preserve.
- Report fields for mask coverage by type, singleton template examples, and
  unmasked high-cardinality tokens.
- Synthetic throughput checks:

```bash
logmask perf-benchmark --lines 10000 --lines 100000 --out perf.json
```

See [docs/PRD.md](docs/PRD.md) for the product direction and
[docs/REVIEW.md](docs/REVIEW.md) for the current engineering review. For
operational mask tuning, see [docs/MASK_TUNING.md](docs/MASK_TUNING.md).

## Template IDs

Sequential IDs are readable but order-dependent:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode sequential --out parsed.jsonl
```

Hash IDs are stable across shards and input ordering:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
```
