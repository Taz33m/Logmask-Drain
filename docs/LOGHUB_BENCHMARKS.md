# LogHub-Compatible Benchmarks

Logmask-Drain v0.7 includes a LogHub/LogHub-2k-compatible benchmark harness for
user-supplied structured CSV files. It does not download datasets, bundle
LogHub data, or make LogHub-scale accuracy claims.

Use it with a `*_structured.csv` file that contains at least:

- `Content`: raw log message text.
- `EventTemplate`: ground-truth template.

If `EventId` is present, it is used as the ground-truth grouping label for
`GA_exact`. If not, normalized `EventTemplate` values are used as grouping
labels.

If `TypedEventTemplate` or `typed_template` is present, the benchmark matrix
also reports `PA_typed`.

```bash
logmask synthesize sample.txt \
  --backend rules \
  --rule-mode conservative \
  --out masks.json

logmask benchmark-loghub-matrix \
  --structured HDFS_2k.log_structured.csv \
  --methods simple_raw,builtin_simple,bundle_simple \
  --masks masks.json \
  --label-source "LogHub-2k structured CSV EventTemplate/EventId" \
  --out loghub-results.json
```

The JSON output records label provenance:

- `label_source`
- `content_column`
- `template_column`
- `cluster_column`
- `typed_template_column`
- `line_count`

The matrix command records parser/mask configuration per method, including
whether a model-backed method used a saved bundle or explicit live synthesis.
Saved bundles are the reproducible path. Live API/local model synthesis is
opt-in with `--synthesize-missing` and is marked `live_synthesis=true`.

Benchmark numbers are only as credible as the label source and parser
configuration you provide. For public comparisons, document the dataset version,
label source, sampling procedure, mask bundle hash, parser settings, and whether
templates were original, corrected, or normalized.
