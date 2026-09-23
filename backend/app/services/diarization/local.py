"""Lazy Community-1 adapter. No account/token is needed for inference from disk."""
from __future__ import annotations

import gc
import math
import os
from pathlib import Path
from threading import Lock

from app.core.errors import FeatureNotConfiguredError
from app.models import DiarizationTurn
from .base import DiarizationService


class LocalDiarizationService(DiarizationService):
    def __init__(
        self, model_path: str | Path, *, device: str = "cuda", exclusive: bool = False,
        num_speakers: int | None = None, min_speakers: int | None = None,
        max_speakers: int | None = None, release_after_call: bool = True,
    ) -> None:
        if device not in {"cuda", "cpu"}:
            raise ValueError("Invalid diarization device")
        counts = (num_speakers, min_speakers, max_speakers)
        if any(value is not None and (type(value) is not int or value < 1) for value in counts):
            raise ValueError("Speaker counts must be positive")
        if min_speakers and max_speakers and min_speakers > max_speakers:
            raise ValueError("min_speakers exceeds max_speakers")
        if num_speakers and (min_speakers or max_speakers):
            raise ValueError("Specify an exact count or bounds, not both")
        self.model_path = Path(model_path).expanduser().resolve()
        self.device, self.exclusive, self.release_after_call = device, exclusive, release_after_call
        self.counts = dict(zip(("num_speakers", "min_speakers", "max_speakers"), counts))
        self._pipeline = None
        self._lock = Lock()

    def _load(self):
        if self._pipeline is None:
            config_file = self.model_path / "config.yaml"
            if not config_file.is_file():
                raise FeatureNotConfiguredError("Local Community-1 weights are missing; authorize and download them first")
            # These flags are applied only at inference time, never at module import.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
            import huggingface_hub.constants
            huggingface_hub.constants.HF_HUB_OFFLINE = True
            huggingface_hub.constants.HF_HUB_DISABLE_TELEMETRY = True
            import yaml
            config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            if config.get("pipeline", {}).get("name") != "pyannote.audio.pipelines.SpeakerDiarization":
                raise ValueError("Only a local Community-1 SpeakerDiarization pipeline is supported")
            import torch
            from pyannote.audio import Pipeline
            from pyannote.audio.telemetry import set_telemetry_metrics
            set_telemetry_metrics(False)
            pipeline = Pipeline.from_pretrained(str(self.model_path), token=False)
            if pipeline is None:
                raise FeatureNotConfiguredError("Community-1 could not load its local files")
            pipeline.to(torch.device(self.device))
            self._pipeline = pipeline
        return self._pipeline

    def close(self) -> None:
        with self._lock:
            loaded = self._pipeline is not None
            self._pipeline = None
            gc.collect()
            if loaded:
                import torch
                if self.device == "cuda" and torch.cuda.is_available():
                    torch.cuda.empty_cache()

    def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError("Local input recording does not exist")
        with self._lock:
            try:
                options = {key: value for key, value in self.counts.items() if value is not None}
                output = self._load()(str(audio_path), **options)
                annotation = output.exclusive_speaker_diarization if self.exclusive else output.speaker_diarization
                turns = []
                for turn, _, speaker in annotation.itertracks(yield_label=True):
                    start, end = float(turn.start), float(turn.end)
                    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
                        raise ValueError("Diarization returned invalid timestamps")
                    turns.append(DiarizationTurn(str(speaker), start, end))
                return sorted(turns, key=lambda turn: (turn.start, turn.end, turn.speaker))
            finally:
                if self.release_after_call:
                    loaded = self._pipeline is not None
                    self._pipeline = None
                    gc.collect()
                    if loaded:
                        import torch
                        if self.device == "cuda" and torch.cuda.is_available():
                            torch.cuda.empty_cache()
