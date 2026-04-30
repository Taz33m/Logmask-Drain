# PyPI Release Checklist

Do not publish to PyPI until the release owner explicitly decides to do so.
GitHub releases remain the default distribution channel for pre-1.0 builds.

## Pre-Publish Requirements

- README clearly states the project is architecture-first and not the
  DeepParse authors' fine-tuned DeepSeek artifact.
- Default install remains CPU-only, network-free, and model-free.
- Optional dependencies are accurately named and tested.
- No saved artifact includes raw sampled logs or raw LLM responses by default.
- Changelog entry has a concrete date and verified block.
- CI passes on Python 3.11, 3.12, and 3.13 for both `main` and the release tag.
- Fresh-wheel smoke succeeds from a clean virtualenv.
- `twine check dist/logmask_drain-<version>*` passes.

## Local Gate

```bash
python -m pytest -q
python -m build
twine check dist/logmask_drain-<version>*
python -m venv /tmp/logmask-pypi-smoke
/tmp/logmask-pypi-smoke/bin/python -m pip install dist/logmask_drain-<version>-py3-none-any.whl
/tmp/logmask-pypi-smoke/bin/logmask --help
/tmp/logmask-pypi-smoke/bin/logmask synthesize tests/fixtures/toy/sample.txt \
  --backend rules \
  --rule-mode conservative \
  --out /tmp/masks.json
/tmp/logmask-pypi-smoke/bin/logmask parse tests/fixtures/toy/logs.txt \
  --masks /tmp/masks.json \
  --template-id-mode hash \
  --out /tmp/parsed.jsonl
```

## Optional Extras Smoke

```bash
/tmp/logmask-pypi-smoke/bin/python -m pip install \
  "dist/logmask_drain-<version>-py3-none-any.whl[api-llm]"

/tmp/logmask-pypi-smoke/bin/python -m pip install \
  "dist/logmask_drain-<version>-py3-none-any.whl[drain3]"
```

Live API and local LLM tests remain opt-in:

```bash
LOGMASK_RUN_LIVE_LLM_TESTS=1 python -m pytest tests/test_live_api_llm.py -q

LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS=1 \
LOGMASK_LLAMA_MODEL=./models/mask-synth.gguf \
python -m pytest tests/test_live_local_llm.py -q
```

## Publish

Publishing commands are intentionally omitted from the checklist until PyPI is
explicitly approved for this project.
