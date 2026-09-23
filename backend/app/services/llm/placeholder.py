from app.core.errors import FeatureNotConfiguredError
from app.models import MeetingTask
from .base import MeetingAnalysisService


class PlaceholderMeetingAnalysisService(MeetingAnalysisService):
    """Safe scaffold: does not call Ollama, llama.cpp, or cloud LLMs."""

    def analyze(self, speaker_transcript: str) -> tuple[str, list[MeetingTask]]:
        raise FeatureNotConfiguredError(
            "Meeting analysis is planned. Configure and test a local LLM before processing transcripts."
        )
