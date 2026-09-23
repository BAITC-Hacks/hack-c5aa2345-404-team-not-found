"""Local settings, read from environment variables at server startup."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SAMRUK KAZYNA Meeting Protocol API"
    storage_path: Path = field(default_factory=lambda: Path(os.environ.get("MEETINGS_STORAGE_PATH", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "SAMRUK_KAZYNA/meetings"))).resolve())
    whisper_path: Path = field(default_factory=lambda: Path(os.environ.get("WHISPER_MODEL_PATH", "models/faster-whisper-large-v3")).resolve())
    pyannote_path: Path = field(default_factory=lambda: Path(os.environ.get("PYANNOTE_MODEL_PATH", "models/speaker-diarization-community-1")).resolve())
    device: str = field(default_factory=lambda: os.environ.get("WHISPER_DEVICE", "cuda"))
    compute_type: str = field(default_factory=lambda: os.environ.get("WHISPER_COMPUTE_TYPE", "int8_float16"))
    ollama_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen3:4b"))
    ffmpeg: str = field(default_factory=lambda: os.environ.get("FFMPEG_PATH", "ffmpeg"))
    max_upload_bytes: int = 250 * 1024 * 1024
    max_duration_seconds: int = 3600
    queue_capacity: int = 5
    local_only: bool = True
    allowed_audio_extensions: tuple[str, ...] = (".wav", ".mp3", ".m4a", ".mp4")


settings = Settings()
