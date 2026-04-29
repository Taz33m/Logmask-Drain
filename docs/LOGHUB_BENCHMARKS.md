# LogHub-Compatible Benchmarks

Logmask-Drain v0.4.0 includes a LogHub-compatible benchmark harness for
structured CSV files. It does not download datasets, bundle LogHub data, or make
LogHub-scale accuracy claims.

Use it with a `*_structured.csv` file that contains at least:

- `Content`: raw log message text.
- `EventTemplate`: ground-truth template.

If `EventId` is present, it is used as the ground-truth grouping label for
`GA_exact`. If not, normalized `EventTemplate` values are used as grouping
labels.

```bash
logmask synthesize sample.txt \
  --backend rules \
  --rule-mode conservative \
  --out masks.json

logmask benchmark-loghub \
  --structured HDFS_2k.log_structured.csv \
  --methods drain,builtin,bundle \
  --masks masks.json \
  --label-source "LogHub structured CSV EventTemplate/EventId" \
  --out loghub-results.json
```

The JSON output records label provenance:

- `label_source`
- `content_column`
- `template_column`
- `cluster_column`
- `line_count`

Benchmark numbers are only as credible as the label source and parser
configuration you provide. For public comparisons, document the dataset version,
label source, sampling procedure, mask bundle hash, parser settings, and whether
templates were original, corrected, or normalized.
