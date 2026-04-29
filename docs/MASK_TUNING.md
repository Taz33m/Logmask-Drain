# Mask Tuning Guide

Logmask-Drain works best when masks are specific enough to preserve static
structure and broad enough to collapse true identifiers. Tune masks by reading
the report, not by guessing.

## Start Conservative

Use conservative rules first:

```bash
logmask synthesize sample.txt --backend rules --rule-mode conservative --out masks.json
logmask parse logs.txt --masks masks.json --template-id-mode hash --out parsed.jsonl
logmask report parsed.jsonl --format json --out report.json
```

Conservative mode intentionally does **not** mask log levels, bare numbers,
generic IDs, status codes, or version numbers by default.

## Prefer Contextual Masks

Use `value_group` when static context should remain in the template.

Good:

```json
{
  "name": "request_id_assignment",
  "type": "REQUEST_ID",
  "pattern": "\\brequest[_-]?id[=:]\\s*([A-Za-z0-9_.:-]+)\\b",
  "value_group": 1,
  "replacement": "<VAR:REQUEST_ID>",
  "priority": 86,
  "enabled": true,
  "flags": ["IGNORECASE"]
}
```

This produces:

```text
request_id=<VAR:REQUEST_ID>
```

Avoid broad masks that erase the static prefix:

```text
<VAR:REQUEST_ID>
```

The prefix is useful structure for template matching, dashboards, and debugging.

Other good contextual-mask shapes:

```text
path=<VAR:PATH>
pid=<VAR:PID>
port=<VAR:PORT>
session_id=<VAR:SESSION_ID>
```

## Read the Report

Useful fields:

- `singleton_template_examples`: inspect these first when template cardinality
  is too high.
- `top_unmasked_high_cardinality_tokens`: review these for true identifiers.
- `mask_coverage_by_type`: check whether the expected variable categories are
  being extracted.
- `recommendations`: deterministic report-level tuning hints.

## Keep Semantic Constants

Do not automatically mask values such as:

- `INFO`, `WARN`, `ERROR`
- `status=200`
- `version=2`
- `HTTP/1.1`
- `TLS 1.3`

These can be important for monitoring and anomaly detection.

## Escalate Carefully

Use aggressive mode only after checking conservative output:

```bash
logmask synthesize sample.txt --backend rules --rule-mode aggressive --out aggressive-masks.json
logmask diff-masks masks.json aggressive-masks.json
```

Aggressive mode can reduce template count, but it can also over-mask useful
constants. Compare `PA_generic`, singleton count, and report recommendations
before adopting it.
