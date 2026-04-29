# Changelog

## v0.2.0 (unreleased)

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

- Development package version is now `0.2.0`.
- High-cardinality token reporting now ignores contextual placeholder tokens
  such as `request_id=<VAR:REQUEST_ID>`.

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
