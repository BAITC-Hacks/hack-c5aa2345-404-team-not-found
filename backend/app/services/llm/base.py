from abc import ABC, abstractmethod

from app.models import MeetingTask


class MeetingAnalysisService(ABC):
    """Future local LLM contract for summaries and assigned tasks."""

    @abstractmethod
    def analyze(self, speaker_transcript: str) -> tuple[str, list[MeetingTask]]:
        """Return a summary and traceable tasks without sending text outside the deployment."""
