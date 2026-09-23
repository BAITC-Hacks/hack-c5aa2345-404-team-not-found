from pathlib import Path

def diarize(audio_path: Path) -> tuple[list[dict], list[str]]:
    try:
        from pyannote.audio import Pipeline
        import os
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN не задан")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
        diarization = pipeline(str(audio_path))
        return [{"start": float(turn.start), "end": float(turn.end), "speaker_id": speaker} for turn, _, speaker in diarization.itertracks(yield_label=True)], []
    except Exception as exc:
        return [], [f"Диаризация недоступна, применена упрощённая схема: {exc}"]

