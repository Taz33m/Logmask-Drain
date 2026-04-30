# Engineering Review

## Current Assessment

The project has a solid deterministic core: fixed mask bundles, strict regex
validation, span-preserving masking, stable template hashes, and CI-backed
fresh-wheel smoke tests.

The current product risk is optional model-generated regex quality. The
mitigation is unchanged across API and local model backends: model output is
candidate JSON only, strict local validation remains the gatekeeper, and parsing
still runs from saved deterministic mask bundles.

## Findings

### Fixed in v0.3 Development

- API LLM synthesis is optional and candidate-only; rules remain the default
  network-free backend.
- Candidate reports omit raw observed examples by default and saved bundles do
  not include raw sampled logs or raw LLM responses.
- LLM candidates are rejected for unsafe regexes, broad full-line captures,
  log-level masks, unknown types unless explicitly allowed, duplicate runtime
  equivalents, and contextual key/value masks that fail to use `value_group`.

### Fixed After v0.3

- LogHub-compatible structured CSV benchmarking exists with explicit label
  provenance and no bundled datasets.
- The optional `drain3` adapter is implemented behind `--engine drain3`, while
  `simple_drain` remains the default.
- Local llama.cpp synthesis is implemented behind `--backend local-llm`; local
  model output remains candidate-only and goes through the same validation gate.
- The PRD and roadmap now reflect the v0.6 architecture instead of the older
  v0.3 plan.
- Initial typed-template accuracy and exact variable-span F1 helpers are
  available for v0.7 evaluation work.

### Fixed in v0.2 Development

- High-cardinality report logic now ignores tokens that contain placeholders,
  not only tokens that start with placeholders. This prevents contextual tokens
  such as `request_id=<VAR:REQUEST_ID>` from being misclassified as unmasked
  text.
- Reports now include deterministic recommendations and the repo includes a
  mask-tuning guide with contextual-mask examples.
- Conservative rules now include a contextual `path=` mask so
  `path=/srv/app/...` preserves the `path=` prefix while masking the value.
- The v0.2 release checklist records the required release gate and a local
  10k-line throughput smoke snapshot.

### Watch Items

- `simple_drain` is intentionally Drain-like, not a full Drain clone. Public
  docs should keep that distinction.
- Conservative rules are safer than aggressive rules but will miss some useful
  variables. This remains preferable because over-masking damages template
  quality.
- CI currently forces Node 24 for GitHub JavaScript actions because upstream
  actions still report Node 20 deprecation annotations.
- The OpenAI provider, local llama.cpp provider, and `drain3` parser are
  optional; environments without optional extras/tools should still install,
  test, and run the default rules backend.
- LogHub-compatible support is a harness, not a benchmark claim. Public docs
  should continue to avoid paper-scale accuracy claims.

## Recommended Next Work

- v0.7 should focus on evaluation credibility: PA_typed, span F1 integration,
  richer fixtures, and clearer benchmark JSON contracts.
- Add a small public-log fixture if licensing is clean.
- Keep PyPI publishing gated behind the checklist in
  `docs/PYPI_RELEASE_CHECKLIST.md`.
