# Engineering Review

## Current Assessment

The project has a solid deterministic core: fixed mask bundles, strict regex
validation, span-preserving masking, stable template hashes, and CI-backed
fresh-wheel smoke tests.

The v0.3 product risk is API-generated regex quality. The mitigation is to keep
LLM output as candidate JSON only: strict local validation remains the
gatekeeper, and parsing still runs from saved deterministic mask bundles.

## Findings

### Fixed in v0.3 Development

- API LLM synthesis is optional and candidate-only; rules remain the default
  network-free backend.
- Candidate reports omit raw observed examples by default and saved bundles do
  not include raw sampled logs or raw LLM responses.
- LLM candidates are rejected for unsafe regexes, broad full-line captures,
  log-level masks, unknown types unless explicitly allowed, duplicate runtime
  equivalents, and contextual key/value masks that fail to use `value_group`.

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
  variables. This is preferable for v0.2 because over-masking damages template
  quality.
- CI currently forces Node 24 for GitHub JavaScript actions because upstream
  actions still report Node 20 deprecation annotations.
- The OpenAI provider is optional; environments without the `api-llm` extra
  should still install, test, and run the default rules backend.

## Recommended Next Work

- Keep `drain3` integration separate from v0.3.
- Keep LogHub-compatible evaluation separate from v0.3.
- Add a small public-log fixture if licensing is clean.
