from abc import ABC, abstractmethod
from pathlib import Path

from app.models import TranscriptResult


class STTService(ABC):
    """Future local speech-to-text provider contract."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Return original-language transcript segments for a local audio file."""
