import os

import pytest


@pytest.mark.skipif(
    os.environ.get("LOGMASK_RUN_LIVE_LLM_TESTS") != "1",
    reason="live API LLM tests are opt-in",
)
def test_live_openai_provider_smoke():
    pytest.importorskip("openai")
    from logmask_drain.synthesis_backends.api_llm import OpenAIProvider, synthesize_api_llm_bundle

    bundle, report = synthesize_api_llm_bundle(
        ["INFO trace_id=abc-123 request_id=req-456 completed"],
        provider=OpenAIProvider(),
        model=os.environ.get("LOGMASK_LIVE_LLM_MODEL", "gpt-4.1-mini"),
        max_candidates=8,
    )

    assert bundle.generator.provider == "openai"
    assert report["candidate_validation"]["candidate_count"] >= 0

