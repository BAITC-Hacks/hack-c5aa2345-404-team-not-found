"""Lazy, disk-only faster-whisper implementation of the shared STT contract."""
from __future__ import annotations

import gc
import math
from pathlib import Path
from threading import Lock

from app.core.errors import FeatureNotConfiguredError
from app.models import TranscriptResult, TranscriptSegment
from .base import STTService


class LocalSTTService(STTService):
    def __init__(
        self, model_path: str | Path, *, device: str = "cuda",
        compute_type: str = "int8_float16", cpu_threads: int = 8,
        beam_size: int = 5, language: str | None = None,
        release_after_call: bool = True,
    ) -> None:
        if device not in {"cuda", "cpu"} or cpu_threads < 1 or beam_size < 1:
            raise ValueError("Invalid STT device/thread/beam configuration")
        if device == "cpu" and compute_type in {"float16", "int8_float16"}:
            raise ValueError("Use compute_type='int8' for CPU")
        self.model_path = Path(model_path).expanduser().resolve()
        self.device, self.compute_type = device, compute_type
        self.cpu_threads, self.beam_size, self.language = cpu_threads, beam_size, language
        self.release_after_call = release_after_call
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is None:
            if not (self.model_path / "model.bin").is_file():
                raise FeatureNotConfiguredError("Local Whisper weights are missing; run the explicit download script first")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                str(self.model_path), device=self.device, compute_type=self.compute_type,
                cpu_threads=self.cpu_threads, num_workers=1, local_files_only=True,
            )
        return self._model

    def close(self) -> None:
        with self._lock:
            self._model = None
            gc.collect()

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError("Local input recording does not exist")
        with self._lock:
            try:
                segments, info = self._load().transcribe(
                    str(audio_path), task="transcribe", language=self.language,
                    multilingual=self.language is None, beam_size=self.beam_size,
                    vad_filter=True, word_timestamps=True,
                )
                result = []
                for item in segments:  # faster-whisper does the work during iteration.
                    start, end = float(item.start), float(item.end)
                    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
                        raise ValueError("STT returned invalid timestamps")
                    if item.text.strip():
                        result.append(TranscriptSegment(start, end, item.text.strip(), []))
                # The API exposes a dominant recording language, not reliable per-turn labels.
                language = getattr(info, "language", None)
                return TranscriptResult(
                    text=" ".join(item.text for item in result), segments=result,
                    detected_languages=[language] if language and result else [],
                )
            finally:
                if self.release_after_call:
                    self._model = None
                    gc.collect()
