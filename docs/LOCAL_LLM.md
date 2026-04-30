# Local LLM Synthesis

Local LLM synthesis is optional. It uses a local model through an external
`llama-cli` executable from llama.cpp. The local model never writes a trusted
runtime bundle directly. It proposes candidate masks, then Logmask-Drain runs
the same strict local validation gate used for API LLM candidates.

## Trust Boundary

```text
sample logs
  -> local prompt
  -> llama-cli candidate JSON
  -> candidate schema validation
  -> regex and mask safety validation
  -> saved mask bundle
  -> deterministic parser runtime
```

The saved bundle does not include raw sampled logs or raw model responses by
default. Validation examples remain redacted unless `--include-raw-examples` is
explicitly supplied.

## Requirements

- A built `llama-cli` executable available on `PATH`, or passed with
  `--llama-cli`.
- A local model file, usually GGUF, passed with `--model-path`.
- Enough CPU/RAM for the chosen model. The default Logmask install does not
  install or download models.

## Basic Workflow

```bash
logmask sample logs.txt --k 50 --mode entropy_greedy --out sample.txt

logmask synthesize sample.txt \
  --backend local-llm \
  --local-provider llama-cpp \
  --llama-cli llama-cli \
  --model-path ./models/mask-synth.gguf \
  --candidate-report local-candidates.json \
  --out masks.local.json

logmask validate-masks masks.local.json --logs sample.txt --strict

logmask parse logs.txt \
  --masks masks.local.json \
  --template-id-mode hash \
  --out parsed.jsonl
```

Hybrid mode keeps conservative built-ins and adds only accepted local-model
candidates:

```bash
logmask synthesize sample.txt \
  --backend local-llm \
  --model-path ./models/mask-synth.gguf \
  --base-rules conservative \
  --out masks.local-hybrid.json
```

## Prompt Size Guards

Local synthesis refuses oversized prompts by default:

- `--max-local-sample-lines 200`
- `--max-local-sample-chars 100000`

Use `logmask sample` first. Override only after reviewing the prompt size:

```bash
logmask synthesize sample.txt \
  --backend local-llm \
  --model-path ./models/mask-synth.gguf \
  --allow-large-local-sample \
  --out masks.local.json
```

## Common Failures

- Missing `--model-path`: pass an explicit local model path.
- Missing `llama-cli`: install llama.cpp or pass `--llama-cli /path/to/llama-cli`.
- Timeout: increase `--local-timeout-seconds`, reduce `--max-tokens`, or sample
  fewer lines.
- Invalid JSON: inspect `--candidate-report` when available and try a smaller
  model prompt or lower `--temperature`.
- Rejected candidates: this is expected. The validator rejects broad, unsafe,
  duplicate, or context-destroying masks.

## Optional Live Smoke Test

Default tests do not run local model inference. To run the opt-in smoke:

```bash
LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS=1 \
LOGMASK_LLAMA_MODEL=./models/mask-synth.gguf \
LOGMASK_LLAMA_CLI=llama-cli \
python -m pytest tests/test_live_local_llm.py -q
```

Optional environment knobs:

- `LOGMASK_LOCAL_LLM_TIMEOUT_SECONDS`
- `LOGMASK_LOCAL_LLM_CTX_SIZE`
- `LOGMASK_LOCAL_LLM_MAX_TOKENS`
