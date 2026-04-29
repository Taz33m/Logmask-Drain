# Engineering Review

## Current Assessment

The project has a solid deterministic core: fixed mask bundles, strict regex
validation, span-preserving masking, stable template hashes, and CI-backed
fresh-wheel smoke tests.

The main product risk is not lack of LLM synthesis. The main risk is parser
trustworthiness on messy real logs: conservative mask behavior, reporting
quality, throughput, and reproducibility.

## Findings

### Fixed in v0.2 Development

- High-cardinality report logic now ignores tokens that contain placeholders,
  not only tokens that start with placeholders. This prevents contextual tokens
  such as `request_id=<VAR:REQUEST_ID>` from being misclassified as unmasked
  text.
- Reports now include deterministic recommendations and the repo includes a
  mask-tuning guide with contextual-mask examples.
- Conservative rules now include a contextual `path=` mask so
  `path=/srv/app/...` preserves the `path=` prefix while masking the value.

### Watch Items

- `simple_drain` is intentionally Drain-like, not a full Drain clone. Public
  docs should keep that distinction.
- Conservative rules are safer than aggressive rules but will miss some useful
  variables. This is preferable for v0.2 because over-masking damages template
  quality.
- CI currently forces Node 24 for GitHub JavaScript actions because upstream
  actions still report Node 20 deprecation annotations.

## Recommended Next Work

- Add a small public-log fixture if licensing is clean.
- Keep LLM synthesis out until real-log coverage and validator behavior are
  stronger.
