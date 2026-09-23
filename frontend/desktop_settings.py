"""Non-secret desktop preferences stored outside the application bundle."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit, urlunsplit


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def settings_path() -> Path:
    """Use the Windows user's writable data directory, never frozen resources."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / "SAMRUK_KAZYNA" / "desktop-settings.json"


def validate_backend_url(value: str) -> str:
    """Accept an HTTP(S) base URL without credentials or request parameters."""
    if not isinstance(value, str):
        raise ValueError("Адрес backend должен быть строкой.")
    value = value.strip()
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("Введите адрес backend без пробелов: http://127.0.0.1:8000")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        # Accessing port also validates the range and rejects non-numeric ports.
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Некорректный адрес или порт backend.") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("Адрес должен начинаться с http:// или https:// и содержать имя сервера.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Не включайте логин, пароль или токен в адрес backend.")
    if "?" in value or "#" in value or "\\" in value or "%" in parsed.netloc:
        raise ValueError("Адрес backend не должен содержать параметры, фрагмент или обратную косую черту.")
    if port == 0 or parsed.netloc.endswith(":"):
        raise ValueError("Укажите корректный порт backend от 1 до 65535.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def load_backend_url() -> str:
    """An explicit saved choice overrides the environment's initial default."""
    try:
        payload = json.loads(settings_path().read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "backend_url" in payload:
            return validate_backend_url(payload["backend_url"])
    except (OSError, ValueError, TypeError, UnicodeError):
        # A malformed file must not prevent starting the app or its settings UI.
        pass
    try:
        return validate_backend_url(os.environ.get("MEETING_API_URL", DEFAULT_BACKEND_URL))
    except ValueError:
        return DEFAULT_BACKEND_URL


def save_backend_url(value: str) -> str:
    """Atomically persist only a validated URL; no meeting data or credentials."""
    normalized = validate_backend_url(value)
    target = settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            json.dump({"backend_url": normalized}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return normalized
