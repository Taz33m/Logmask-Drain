# Changelog

## v0.7.0 - 2026-04-30

Reproducibility benchmark layer release.

### Added

- `logmask benchmark-matrix` for plain logs plus template CSV labels.
- `logmask benchmark-loghub-matrix` for user-supplied LogHub/LogHub-2k-style
  structured CSV files.
- Versioned benchmark result schema with dataset, sample, environment, and
  per-method parser/mask metadata.
- Matrix methods for raw `simple_drain`, raw `drain3`, built-in masks, saved
  bundles, saved API/local LLM bundles, and saved hybrid bundles.
- `PA_typed` reporting when typed template labels are available.
- Drain3 matrix methods skip cleanly with install guidance when the optional
  dependency is absent.
- `docs/BENCHMARK_MATRIX.md` with method IDs, result fields, metric meanings,
  and live-synthesis caveats.
- `SECURITY.md` with sensitive-artifact guidance, optional LLM boundary notes,
  runtime regex timeout guidance, and vulnerability reporting instructions.
- Repository logo asset for the public README.
- Reproducible matrix fixtures and tests for typed labels, LogHub `EventId`
  grouping, saved-bundle requirements, Drain3 skip behavior, and LLM provider
  isolation.

### Changed

- Package version is now `0.7.0`.
- LogHub benchmark docs now describe LogHub-2k-compatible matrix workflows.
- API/local LLM benchmark methods use saved bundles by default; live synthesis
  only runs with `--synthesize-missing` and is marked `live_synthesis=true`.
- API and local LLM prompts now render sampled logs as JSON data and explicitly
  instruct providers to treat log lines as inert data.
- YAML mask-bundle loading now uses `yaml.safe_load` when the optional YAML
  extra is installed.
- Removed the unimplemented `re2` extra from public package metadata and
  README installation docs.

### Verified

- `pytest -q` passes in a temporary Python 3.11 environment with 80 tests and
  3 skipped optional/live tests.
- `python -m build` in the Python 3.11 environment produces sdist and wheel.
- `twine check dist/logmask_drain-0.7.0*` passes.
- The source distribution includes README assets, `SECURITY.md`, docs, package
  code, and benchmark fixtures.

## v0.6.1 - 2026-04-30

Documentation and evaluation-metric hardening release.

### Added

- `parsing_accuracy_typed` for exact typed-template matching.
- `variable_span_f1` for exact variable span precision, recall, and F1 with
  typed and untyped modes.
- Opt-in live local LLM smoke test gated by
  `LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS=1`.
- `docs/LOCAL_LLM.md` with llama.cpp workflow, prompt-size guards, failure
  modes, and live-smoke instructions.
- `docs/ROADMAP.md` with v0.7/v0.8/v1.0 release direction.
- `docs/PYPI_RELEASE_CHECKLIST.md` for future PyPI readiness.

### Changed

- Package version is now `0.6.1`.
- `docs/PRD.md` now reflects the actual v0.6 architecture and completed
  roadmap items.
- README now links to local LLM, roadmap, and PyPI-readiness docs.

### Verified

- `python -m pytest -q` passes with 73 tests and 2 skipped opt-in live tests.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.6.1*` passes.
- Fresh Python 3.11 wheel install passes the CLI smoke checklist.
- Fresh wheel benchmark smoke passes on the toy fixture.
- Fresh wheel local-LLM smoke fails cleanly before provider work when
  `--model-path` is missing.

## v0.6.0 - 2026-04-30

Optional local llama.cpp candidate-mask synthesis release.

### Added

- `logmask synthesize --backend local-llm` for local candidate-mask synthesis.
- `llama-cpp` local provider using an external `llama-cli` executable.
- Local synthesis options: `--model-path`, `--llama-cli`,
  `--local-provider`, `--local-timeout-seconds`, `--ctx-size`,
  `--max-tokens`, `--max-local-sample-lines`, `--max-local-sample-chars`, and
  `--allow-large-local-sample`.
- `local_llm_masks_v1` prompt template for JSON-only candidate-mask output.
- Local LLM JSON extraction that tolerates preamble, trailing text, and echoed
  prompts by selecting the last valid candidate-mask object.
- Local sample-size provenance in generated bundles and candidate reports.
- Unit and CLI tests for mocked local providers, llama.cpp subprocess handling,
  local prompt snapshots, oversized prompt guards, and JSON extraction.

### Changed

- Package version is now `0.6.0`.
- Rules remain the default synthesis backend.
- Local model output is candidate masks only; strict validation still decides
  which masks enter the saved runtime bundle.

### Verified

- `python -m pytest -q` passes with 70 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.6.0*` passes.
- Fresh Python 3.11 wheel install passes the CLI smoke checklist.
- Fresh wheel local-LLM smoke fails cleanly before provider work when
  `--model-path` is missing.
- Fresh wheel install with `logmask-drain[drain3]` still parses the toy fixture
  with `--engine drain3`.

## v0.5.0 - 2026-04-30

Optional real `drain3` parser adapter release.

### Added

- Optional `drain3` parser adapter behind `--engine drain3`.
- Restored `drain3` package extra: `logmask-drain[drain3]`.
- Drain3 parser metadata with `engine=drain3`, package version, and
  `tokenizer_version=drain3_default_v1`.
- Mocked adapter and CLI tests for drain3 behavior without requiring the
  optional dependency in the default test environment.
- CI fresh-wheel smoke coverage for installing `logmask-drain[drain3]` and
  parsing a toy fixture with `--engine drain3`.

### Changed

- Package version is now `0.5.0`.
- `simple_drain` remains the default parser engine.
- The drain3 adapter receives Logmask-masked lines and disables Drain3-side
  numeric parametrization so mask bundles stay the explicit runtime boundary.

### Verified

- `python -m pytest -q` passes with 57 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.5.0*` passes.
- Fresh Python 3.11 wheel install passes the CLI smoke checklist.
- Fresh wheel install with `logmask-drain[drain3]` parses the toy fixture with
  `--engine drain3`.

## v0.4.1 - 2026-04-30

Privacy, UX, and consistency hardening release.

### Added

- API LLM sample-size guards: `--max-api-sample-lines`,
  `--max-api-sample-chars`, and explicit `--allow-large-api-sample` override.
- API sample line/character counts in API LLM bundle provenance and candidate
  reports.
- Runtime regex timeout metadata in parser output and reports.
- `--strict-runtime` for `logmask parse` to fail on runtime regex timeouts.
- LogHub metric-semantics tests for `EventId`, `EventTemplate`, `Message`,
  `LineId`, and no-`EventId` fallback behavior.

### Changed

- Package version is now `0.4.1`.
- Redacted validation examples no longer include raw substring previews by
  default.
- `benchmark` and `benchmark-loghub` now default to `drain,builtin`; `bundle`
  must be requested explicitly with `--masks`.
- LLM duplicate-candidate rejection reason is now `duplicate_match_equivalent`.
- Candidate type registry now includes `FLOAT`, `USERNAME`, and `FILENAME`.
- Strict mask validation now rejects replacement/type mismatches such as
  `type=IP` with `replacement=<VAR:ID>`.
- Removed the advertised `drain3` optional extra until the adapter is actually
  implemented.
- Updated stale `drain3` error text and README release wording.

### Verified

- `python -m pytest -q` passes with 53 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.4.1*` passes.
- Fresh wheel install passes the CLI smoke checklist.
- `logmask benchmark` defaults to `drain,builtin` from a fresh wheel.
- API LLM oversized sample guard fails before provider/dependency work.

## v0.4.0 - 2026-04-29

LogHub-compatible evaluation harness.

### Added

- `logmask benchmark-loghub` for LogHub-style structured CSV files with
  `Content`, `EventTemplate`, and optional `EventId` columns.
- LogHub structured CSV loader with explicit label provenance in JSON output.
- LogHub-compatible fixture and CLI tests.
- `docs/LOGHUB_BENCHMARKS.md` with label-source and public-comparison caveats.
- CI fresh-wheel smoke coverage for `candidate-schema` and
  `benchmark-loghub`.

### Changed

- Package version is now `0.4.0`.

### Verified

- `python -m pytest -q` passes with 40 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.4.0*` passes.
- Fresh wheel install passes the CLI smoke checklist.
- `logmask benchmark-loghub` works from a fresh wheel with explicit label
  provenance.

## v0.3.1 - 2026-04-29

API LLM synthesis hardening release.

### Added

- `--provider-timeout-seconds` and `--provider-max-retries` for
  `logmask synthesize --backend api-llm`.
- Provider timeout/retry settings in generated bundle provenance and candidate
  reports.
- `logmask candidate-schema` for exporting the candidate-mask JSON schema.
- Grouped `rejection_examples` in candidate reports for easier debugging.
- Prompt snapshot and adversarial candidate tests.

### Changed

- Package version is now `0.3.1`.
- Duplicate runtime-equivalent candidate detection now ignores priority, so
  candidates cannot evade duplicate detection by only changing ordering weight.

### Verified

- `python -m pytest -q` passes with 37 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.3.1*` passes.
- Fresh wheel install without `api-llm` extra passes.
- `logmask candidate-schema` works from a fresh wheel.
- Rules backend remains network-free from a fresh wheel.
- API backend without optional dependency fails cleanly with install guidance.

## v0.3.0 - 2026-04-29

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

### Verified

- `python -m pytest -q` passes with 33 tests and 1 skipped live API test.
- `python -m build` produces sdist and wheel.
- `twine check dist/logmask_drain-0.3.0*` passes.
- Fresh wheel install without `api-llm` extra passes.
- Rules backend remains network-free from a fresh wheel.
- API backend without optional dependency fails cleanly with install guidance.
- GitHub Actions CI passes on Python 3.11, 3.12, and 3.13.

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
