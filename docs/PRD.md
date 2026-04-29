# Product Requirements Document: Logmask-Drain

## Summary

Logmask-Drain is a CPU-first, deterministic log parsing tool inspired by the
DeepParse architecture: synthesize or load regex masks offline, validate them,
cache them as a reproducible bundle, then parse logs online through a
mask-first Drain-style execution path.

The product goal is not to reproduce the DeepParse authors' fine-tuned
DeepSeek artifact. The goal is to make the architecture practical for local,
auditable, no-GPU environments.

## Users and Jobs

- SREs and platform engineers need stable log templates for alerting,
  dashboards, and incident analysis.
- Security engineers need local parsing that does not upload sensitive logs.
- Researchers need a small, inspectable baseline for mask-first log parsing.
- Tool builders need deterministic JSONL output, stable template hashes, and
  testable mask bundles.

## Current Product State

- `v0.1.1` is released and tagged.
- `main` is now on the `0.2.0` development line.
- The parser supports rule-based masks, strict validation, span-preserving
  masking, `simple_drain`, stable template hashes, hash-derived template IDs,
  reporting, drift, diffing, benchmarking, and synthetic performance checks.
- CI runs on Python 3.11, 3.12, and 3.13.

## Goals for v0.2

- Prove the parser on more realistic log shapes without adding LLM synthesis.
- Make performance visible through deterministic synthetic benchmarks.
- Improve report usefulness for tuning masks and spotting drift.
- Keep all behavior local, CPU-only, and reproducible.

## Requirements

- The CLI must remain installable as `logmask` from the package wheel.
- Parsing the same logs with the same bundle and parser config must remain
  deterministic.
- Reports must expose template cardinality, singleton templates, variable
  counts, mask coverage, mask coverage by type, and unmasked high-cardinality
  tokens.
- Reports must include deterministic recommendations that turn report signals
  into next tuning actions.
- Conservative rules must not mask broad numbers, generic IDs, or log levels by
  default.
- CI must run tests, build artifacts, validate metadata, and run a fresh-wheel
  CLI smoke test.
- Performance checks must report lines/sec and runtime per 100 logs for
  `synthesize`, `mask`, `parse`, and `report`.

## Non-Goals

- No API LLM synthesis in v0.2.
- No local llama.cpp or Transformers backend in v0.2.
- No LogBERT reproduction in v0.2.
- No PyPI publishing unless requested separately.

## Success Metrics

- CI passes on Python 3.11, 3.12, and 3.13.
- Realistic fixture tests pass and preserve conservative-mode invariants.
- `logmask perf-benchmark --lines 10000` completes locally.
- Report JSON contains additive fields needed for mask tuning.
- No regression in toy benchmark behavior: raw Drain may group correctly while
  mask-first methods recover exact generic templates.

## Roadmap

### v0.2

- Harden realistic fixtures and reporting.
- Add deterministic performance checks.
- Add lightweight documentation for mask tuning.
- Add report-driven tuning recommendations.

### v0.3

- Add optional API LLM candidate-mask synthesis.
- Keep LLM output as untrusted candidate JSON.
- Require validator acceptance before runtime use.

### Later

- Add LogHub-compatible loaders.
- Add typed parsing metrics and span F1.
- Add optional `drain3` adapter.
- Explore local model backends only after validator and benchmark coverage are
  strong.
