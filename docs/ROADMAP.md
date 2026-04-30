# Roadmap

Logmask-Drain is now beyond the original PRD scope. The core product boundary
is implemented: fixed mask bundles drive deterministic mask-first parsing, and
all LLM/model paths are optional candidate generators that feed the same local
validation gate.

## Current Release Line

### v0.6.x

- Keep rules as the default CPU-only, network-free synthesis path.
- Harden optional API and local model candidate synthesis.
- Keep saved mask bundles deterministic and auditable.
- Refresh docs so they track the implemented architecture instead of older
  release plans.

## Next Releases

### v0.7: Evaluation Credibility

- Add PA_typed reporting when typed template ground truth is available.
- Add variable-span F1 reporting when span ground truth is available.
- Add richer benchmark fixtures with explicit label provenance.
- Improve benchmark JSON schemas and caveats for public comparisons.
- Keep LogHub-compatible evaluation opt-in and dataset-free.

### v0.8: Operational Resynthesis

- Add mask-bundle change summaries and risk hints.
- Improve `drift` output for deciding when to resynthesize masks.
- Add resynthesis workflow docs for schema drift.
- Add stronger runtime warning aggregation for production parsing.

### v1.0: Stable Contracts

- Freeze public mask bundle and parsed JSONL compatibility guarantees.
- Publish a schema compatibility policy.
- Decide whether to publish to PyPI.
- Keep DeepSeek fine-tuning, LogBERT reproduction, and paper-scale accuracy
  parity claims out of scope unless separately funded and benchmarked.
