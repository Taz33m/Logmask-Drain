# Changelog

## v0.3.0 (unreleased)

Optional API LLM candidate-mask synthesis behind a hard safety boundary.

### Added

- Optional `api-llm` synthesis backend with OpenAI provider support.
- Candidate-mask schema, provider abstraction, and `api_llm_masks_v1` prompt.
- LLM candidate validation gate with known-type, placeholder, log-level,
  duplicate, over-broad, full-line, static-key, timeout, and regex safety
  checks.
- `--candidate-report`, `--base-rules`, `--allow-new-types`,
  `--max-candidates`, `--temperature`, and `--prompt-version` for
  `logmask synthesize --backend api-llm`.
- Top-level `candidate_validation` provenance in API-generated mask bundles.
- Optional `api-llm` package extra for OpenAI SDK installation.
- Mocked API LLM tests and opt-in live API smoke test hook.

### Changed

- Package version is now `0.3.0`.
- Rules remain the default synthesis backend and still require no network.

## v0.2.0 - 2026-04-29

Real-log validation and performance hardening.

### Added

- GitHub Actions CI for Python 3.11, 3.12, and 3.13.
- Fresh-wheel install smoke test in CI.
- Realistic fixtures covering mixed timestamp formats, UUIDs, request/session
  IDs, paths, URLs, quoted strings, interleaved services, and conservative-mode
  static numeric preservation.
- `logmask perf-benchmark` for deterministic synthetic throughput checks.
- Report fields for mask coverage by type, singleton template examples,
  unmasked high-cardinality tokens, and high-cardinality token rate.
- Conservative masks for slash datetimes, syslog-style datetimes, and
  contextual epoch timestamp assignments.
- Conservative contextual path assignment mask.
- Product requirements and engineering review docs.
- Mask tuning guide with contextual-mask examples.
- v0.2 release checklist with a local 10k-line throughput snapshot.
- Report `recommendations` for deterministic tuning hints.

### Changed

- Package version is now `0.2.0`.
- High-cardinality token reporting now ignores contextual placeholder tokens
  such as `request_id=<VAR:REQUEST_ID>`.

### Verified

- `python -m pytest -q` passes with 24 tests.
- `python -m build` produces sdist and wheel.
- `twine check dist/*` passes.
- Fresh Python 3.11 wheel install passes the CLI smoke checklist.
- `logmask perf-benchmark --lines 10000` completes locally.

## v0.1.1

Hardening release for deterministic, CPU-only mask-first log parsing.

### Added

- `--template-id-mode sequential|hash` for `logmask parse`.
- Hash-derived template IDs such as `T5FBBF3CD`.
- Parser metadata field: `template_id_mode`.
- Stronger tests for byte determinism, span invariants, runtime hash invariants,
  redacted validation examples, overlap ordering, log-level preservation, and
  hash-ID stability across input ordering changes.
- Fresh-wheel release fixtures: `tests/fixtures/toy/sample.txt` and
  `tests/fixtures/toy/logs.txt`.

### Changed

- README now clearly positions Logmask-Drain as an architecture-first,
  CPU-only implementation, not the DeepParse authors' fine-tuned DeepSeek
  artifact.
- Package metadata now requires Python 3.11 or newer.

### Verified

- `python3 -m pytest -q` passes with 20 tests.
- `python3 -m build` produces sdist and wheel.
- Fresh Python 3.11 wheel install passes the CLI smoke checklist.
- `twine check dist/*` passes.
- Toy benchmark demonstrates the intended proof point: raw Drain groups lines
  correctly but misses exact variable-boundary recovery, while mask-first
  methods recover `PA_generic=1.0`.
