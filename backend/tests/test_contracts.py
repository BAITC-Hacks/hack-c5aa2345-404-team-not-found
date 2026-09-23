"""Contract examples for a later test run; dependencies are not installed at this stage."""

from app.schemas.meeting import MeetingAnalysisResponse


def test_empty_analysis_is_explicitly_planned() -> None:
    result = MeetingAnalysisResponse(summary="", processing_state="planned")
    assert result.local_only is True
    assert result.tasks == []
