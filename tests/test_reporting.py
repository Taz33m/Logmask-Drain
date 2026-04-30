from logmask_drain.reporting import summarize_parsed
from logmask_drain.models import ParsedLine, ParserMetadata


def test_empty_report_has_actionable_recommendation():
    summary = summarize_parsed([])

    assert summary["recommendations"][0]["code"] == "empty_input"


def test_report_surfaces_runtime_timeout_metadata():
    parser = ParserMetadata(
        engine="simple_drain",
        engine_version="0.1",
        similarity_threshold=0.4,
        tokenizer_version="whitespace_v1",
        runtime_mask_sha256="abc",
        runtime_timeout_count=2,
        runtime_timeouts_by_mask={"slow": 2},
    )
    line = ParsedLine(
        line_id=0,
        raw="abc",
        masked="abc",
        template_id="T000001",
        template_hash="sha1:abc",
        template="abc",
        parser=parser,
    )

    summary = summarize_parsed([line])

    assert summary["runtime_timeout_count"] == 2
    assert summary["runtime_timeouts_by_mask"] == {"slow": 2}
    assert any(item["code"] == "runtime_regex_timeouts" for item in summary["recommendations"])
