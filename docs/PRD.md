# Product Requirements Document: Logmask-Drain

## Summary

Logmask-Drain is a CPU-first, deterministic log parsing tool inspired by the
DeepParse architecture: synthesize or load regex masks offline, validate them,
cache them as a reproducible bundle, then parse logs online through a mask-first
Drain-style execution path.

The product goal is not to reproduce the DeepParse authors' fine-tuned
DeepSeek artifact. The goal is to make the architecture practical for local,
auditable, no-GPU environments where mask bundles are explicit runtime
artifacts.

## Users and Jobs

- SREs and platform engineers need stable log templates for alerting,
  dashboards, and incident analysis.
- Security engineers need local parsing that does not upload sensitive logs by
  default.
- Researchers need a small, inspectable baseline for mask-first log parsing.
- Tool builders need deterministic JSONL output, stable template hashes, typed
  variable spans, and testable mask bundles.

## Current Product State

- Latest release: `v0.6.1`.
- Default workflow remains CPU-only, network-free, and model-free.
- Rule-based synthesis, strict regex validation, span-preserving masking,
  `simple_drain`, stable template hashes, hash-derived template IDs, reporting,
  drift, diffing, benchmarking, and synthetic performance checks are complete.
- Optional API LLM synthesis exists, but LLM output is candidate JSON only and
  cannot enter a runtime bundle until local validation accepts it.
- Optional local llama.cpp synthesis exists through an external `llama-cli`,
  again as candidate JSON only.
- Optional `drain3` parsing exists behind `--engine drain3`; `simple_drain`
  remains the default.
- LogHub-compatible structured CSV benchmarking exists with explicit label
  provenance and no bundled datasets.
- CI runs tests, builds artifacts, checks metadata, and performs fresh-wheel
  smoke tests on Python 3.11, 3.12, and 3.13.

## Product Boundary

Logmask-Drain implements the DeepParse-style architecture, not the full paper
artifact. The required product boundary is:

1. Offline sampling and mask-bundle generation.
2. Strict local validation and provenance for every accepted mask.
3. Deterministic mask-first parsing from a saved bundle.
4. Auditable JSONL output with stable template hashes and extracted spans.
5. Evaluation and operational reports that avoid overclaiming benchmark results.

## Requirements

- The CLI must remain installable as `logmask` from the package wheel.
- Parsing the same logs with the same bundle and parser config must remain
  deterministic.
- Rules must remain the default synthesis backend and require no network,
  model download, API key, or GPU.
- LLM-generated masks, whether API or local, must never bypass strict local
  validation.
- Saved bundles must not include raw sampled logs or raw LLM responses by
  default.
- Conservative rules must not mask broad numbers, generic IDs, or log levels by
  default.
- Reports must expose template cardinality, singleton templates, variable
  counts, mask coverage, mask coverage by type, unmasked high-cardinality
  tokens, runtime timeout metadata, and deterministic recommendations.
- Benchmarks must report GA_exact and PA_generic. Typed and span metrics may be
  reported when typed/span ground truth is available.
- CI must run tests, build artifacts, validate metadata, and run fresh-wheel CLI
  smoke tests.
- Performance checks must report lines/sec and runtime per 100 logs for
  `synthesize`, `mask`, `parse`, and `report`.

## Non-Goals

- No DeepSeek-R1 fine-tuning reproduction.
- No per-dataset model training.
- No LogBERT reproduction.
- No claim of parity with the paper's LogHub-scale numbers.
- No bundled LogHub datasets.
- No PyPI publishing unless requested separately.

## Success Metrics

- CI passes on Python 3.11, 3.12, and 3.13.
- Realistic fixture tests pass and preserve conservative-mode invariants.
- `logmask perf-benchmark --lines 10000` completes locally.
- Report JSON contains additive fields needed for mask tuning.
- API LLM tests use mocked providers and require no network by default.
- Live API tests are opt-in with `LOGMASK_RUN_LIVE_LLM_TESTS=1`.
- Live local LLM tests are opt-in with `LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS=1` and
  require an explicit `LOGMASK_LLAMA_MODEL` path.
- No regression in toy benchmark behavior: raw Drain may group correctly while
  mask-first methods recover exact generic templates.
- Optional parser/model integrations are isolated behind explicit flags or
  extras and do not affect the default rules path.

## Release Status

- `v0.1.1`: deterministic mask-first parser foundation. Complete.
- `v0.2.0`: realistic fixtures, performance checks, and report hardening.
  Complete.
- `v0.3.0`/`v0.3.1`: optional API LLM candidate-mask synthesis and hardening.
  Complete.
- `v0.4.0`/`v0.4.1`: LogHub-compatible harness and privacy/UX hardening.
  Complete.
- `v0.5.0`: optional `drain3` parser adapter. Complete.
- `v0.6.0`: optional local llama.cpp candidate-mask synthesis. Complete.
- `v0.6.1`: documentation refresh and initial typed/span metrics. Complete.

## Current Hardening Target: v0.6.1

- Refresh product docs so they match the implemented v0.6 architecture.
- Add local LLM operational docs and an opt-in live local LLM smoke test.
- Add initial typed-template and variable-span metrics.
- Add PyPI-readiness documentation without publishing to PyPI.

## Roadmap

### v0.7

- Evaluation credibility release.
- Add PA_typed reporting where typed ground truth exists.
- Add span-F1 reporting where span ground truth exists.
- Add more benchmark fixtures with explicit label provenance.
- Improve benchmark JSON schemas and public comparison caveats.

### v0.8

- Operational resynthesis and drift workflows.
- Better mask-bundle diffing, resynthesis reports, and change-risk summaries.
- Optional production-oriented runtime warning aggregation.

### v1.0

- Freeze public JSON contracts for mask bundles and parsed JSONL.
- Publish a stable compatibility policy.
- Consider PyPI publishing after the privacy, docs, and benchmark caveats are
  complete.
