from pathlib import Path
import os
from .models import Segment

# Set before importing faster-whisper / Hugging Face; these libraries read
# offline settings on import. Provision weights separately before deployment.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

def transcribe(audio_path: Path, model_size: str = "small") -> tuple[list[Segment], list[str]]:
    """Local faster-whisper wrapper. Returns a demo fallback if ML is unavailable."""
    try:
        from faster_whisper import WhisperModel
        # Models must already be present in the local cache; never pull weights
        # from a public model hub during an on-premise meeting workflow.
        model = WhisperModel(
            os.getenv("WHISPER_MODEL_PATH", model_size),
            device="auto",
            compute_type="int8",
            local_files_only=True,
        )
        segments, _ = model.transcribe(str(audio_path), language=None, vad_filter=True)
        result = [Segment(float(s.start), float(s.end), s.text.strip(), "ru") for s in segments]
        return result, []
    except ImportError:
        return [Segment(0, 1, "Демо-режим: установите faster-whisper для транскрибации аудио.")], ["faster-whisper не установлен: использован demo-текст."]
    except Exception as exc:
        return [Segment(0, 1, "Не удалось распознать аудио в demo-режиме.")], [f"STT недоступен: {exc}"]

