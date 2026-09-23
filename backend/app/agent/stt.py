from pathlib import Path
from .models import Segment

def transcribe(audio_path: Path, model_size: str = "small") -> tuple[list[Segment], list[str]]:
    """Local faster-whisper wrapper. Returns a demo fallback if ML is unavailable."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="auto", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), language=None, vad_filter=True)
        result = [Segment(float(s.start), float(s.end), s.text.strip(), "ru") for s in segments]
        return result, []
    except ImportError:
        return [Segment(0, 1, "Демо-режим: установите faster-whisper для транскрибации аудио.")], ["faster-whisper не установлен: использован demo-текст."]
    except Exception as exc:
        return [Segment(0, 1, "Не удалось распознать аудио в demo-режиме.")], [f"STT недоступен: {exc}"]

