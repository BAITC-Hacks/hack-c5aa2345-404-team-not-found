from pathlib import Path

from app.core.errors import FeatureNotConfiguredError
from app.models import TranscriptResult
from .base import STTService


class PlaceholderSTTService(STTService):
    """Safe scaffold: never loads or downloads a speech-recognition model."""

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        raise FeatureNotConfiguredError(
            "STT is planned. Configure and test a local faster-whisper model before processing audio."
        )
