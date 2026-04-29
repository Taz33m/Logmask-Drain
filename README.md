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

## Toy Benchmark

The included toy fixture is intentionally constructed to demonstrate
variable-boundary failures:

| method | GA_exact | PA_generic |
| --- | ---: | ---: |
| drain | 1.0 | 0.0 |
| builtin | 1.0 | 1.0 |
| bundle | 1.0 | 1.0 |

Real-world accuracy requires evaluation on representative logs.

## Template IDs

Sequential IDs are readable but order-dependent:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode sequential --out parsed.jsonl
```

Hash IDs are stable across shards and input ordering:

```bash
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
```
