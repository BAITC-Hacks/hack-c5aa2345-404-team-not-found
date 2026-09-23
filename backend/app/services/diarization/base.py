from abc import ABC, abstractmethod
from pathlib import Path

from app.models import DiarizationTurn


class DiarizationService(ABC):
    """Future local speaker-diarization provider contract."""

    @abstractmethod
    def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Return timestamped anonymous speaker turns for a local audio file."""
