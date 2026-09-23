"""Offline speaker diarization using an operator-provisioned pipeline."""

import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def diarize(audio_path: Path) -> tuple[list[dict], list[str]]:
    config = os.getenv("PYANNOTE_PIPELINE_PATH", "")
    if not config or not Path(config).is_file():
        return [], ["Диаризация не настроена: укажите локальный YAML в PYANNOTE_PIPELINE_PATH. Идентификация спикеров не выполнена."]
    try:
        from pyannote.audio import Pipeline

        # Local config must reference local/cached segmentation and embedding
        # weights. Offline mode prevents their implicit network download.
        pipeline = Pipeline.from_pretrained(str(Path(config).resolve()))
        output = pipeline(str(audio_path))
        diarization = getattr(output, "speaker_diarization", output)
        return [
            {"start": float(turn.start), "end": float(turn.end), "speaker_id": speaker}
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ], []
    except Exception as exc:
        return [], [f"Диаризация недоступна; спикеры не идентифицированы: {exc}"]
