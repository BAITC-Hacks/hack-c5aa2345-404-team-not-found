"""On-premise configuration contract. The scaffold starts no external clients."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "HackAlem Meeting Protocol API"
    storage_path: Path = Path("data/meetings")
    local_only: bool = True
    allowed_audio_extensions: tuple[str, ...] = (".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".webm")


settings = Settings()
