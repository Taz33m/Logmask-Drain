import os
from pathlib import Path

import pytest

from logmask_drain.synthesis_backends.local_llm import LlamaCppProvider, synthesize_local_llm_bundle


@pytest.mark.skipif(
    os.environ.get("LOGMASK_RUN_LIVE_LOCAL_LLM_TESTS") != "1",
    reason="live local LLM smoke is opt-in",
)
def test_live_local_llm_synthesis_smoke():
    model_path_value = os.environ.get("LOGMASK_LLAMA_MODEL")
    if not model_path_value:
        pytest.skip("LOGMASK_LLAMA_MODEL is required for live local LLM smoke")
    model_path = Path(model_path_value)
    if not model_path.exists():
        pytest.skip(f"LOGMASK_LLAMA_MODEL does not exist: {model_path}")

    provider = LlamaCppProvider(llama_cli=os.environ.get("LOGMASK_LLAMA_CLI", "llama-cli"))
    bundle, report = synthesize_local_llm_bundle(
        ["INFO trace_id=abc-123 request_id=req-456 completed in 25ms"],
        provider=provider,
        model_path=model_path,
        max_candidates=4,
        timeout_seconds=float(os.environ.get("LOGMASK_LOCAL_LLM_TIMEOUT_SECONDS", "120")),
        ctx_size=int(os.environ.get("LOGMASK_LOCAL_LLM_CTX_SIZE", "2048")),
        max_tokens=int(os.environ.get("LOGMASK_LOCAL_LLM_MAX_TOKENS", "512")),
        strict=True,
    )

    assert bundle.generator.backend == "local-llm"
    assert bundle.generator.provider == "llama-cpp"
    assert bundle.candidate_validation is not None
    assert report["candidate_validation"]["candidate_count"] >= 0
