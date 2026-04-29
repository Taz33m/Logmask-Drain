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

### Watch Items

- `simple_drain` is intentionally Drain-like, not a full Drain clone. Public
  docs should keep that distinction.
- Conservative rules are safer than aggressive rules but will miss some useful
  variables. This is preferable for v0.2 because over-masking damages template
  quality.
- CI currently forces Node 24 for GitHub JavaScript actions because upstream
  actions still report Node 20 deprecation annotations.

## Recommended Next Work

- Add mask-tuning documentation with before/after examples.
- Add a small public-log fixture if licensing is clean.
- Add report-driven recommendations, such as "consider contextual mask" for
  recurring high-cardinality unmasked tokens.
- Keep LLM synthesis out until real-log coverage and validator behavior are
  stronger.

