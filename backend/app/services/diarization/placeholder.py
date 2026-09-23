from pathlib import Path

from app.core.errors import FeatureNotConfiguredError
from app.models import DiarizationTurn
from .base import DiarizationService


class PlaceholderDiarizationService(DiarizationService):
    """Safe scaffold: never contacts Hugging Face or loads pyannote."""

    def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        raise FeatureNotConfiguredError(
            "Speaker diarization is planned. Configure and test a local pyannote pipeline first."
        )
