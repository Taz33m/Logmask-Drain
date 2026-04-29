from logmask_drain.reporting import summarize_parsed


def test_empty_report_has_actionable_recommendation():
    summary = summarize_parsed([])

    assert summary["recommendations"][0]["code"] == "empty_input"

