# Security Policy

Logmask-Drain is designed for local, deterministic log parsing. The default
rules workflow does not require a network connection, GPU, model download, or
API key.

## Supported Versions

Security fixes target the current release line on `main`. If you are using an
older tag, upgrade before reporting behavior that may already be fixed.

## Sensitive Artifacts

Treat these files as sensitive:

- raw log samples passed to `logmask synthesize`,
- parsed JSONL files, because they contain raw lines and extracted values,
- report JSON files when they include high-cardinality token examples,
- candidate reports created with `--include-raw-examples`,
- API/local LLM prompts, because they include sampled log lines.

Mask bundles redact validation examples by default and store hashes plus
lengths instead of raw matches. Raw validation examples are written only when
`--include-raw-examples` is explicitly supplied.

## Optional LLM Backends

API LLM synthesis is opt-in. When `--backend api-llm` is used, sampled log
lines are sent to the selected provider. The CLI enforces sample line and
character caps before provider lookup and records only sample counts and hashes
in saved bundles. Use `logmask sample` before API synthesis and review samples
before sending them outside your environment.

Local LLM synthesis is also opt-in. It writes a temporary prompt file for the
external `llama-cli` process and deletes that file when the process exits.

LLM output never becomes trusted runtime configuration directly. Providers
return candidate masks, and strict local validation decides which candidates
enter a saved mask bundle.

## Regex Execution

Logmask-Drain uses the third-party `regex` module with timeouts for validation
and runtime masking. Runtime timeouts are counted in parser metadata and
reports. Use `logmask parse --strict-runtime` to fail instead of allowing an
under-masked line after a timeout.

## Reporting Vulnerabilities

Please report security issues privately through GitHub Security Advisories if
available on the repository. If advisories are unavailable, open a minimal
GitHub issue that requests private contact without including sensitive logs,
tokens, API keys, or exploit details.
