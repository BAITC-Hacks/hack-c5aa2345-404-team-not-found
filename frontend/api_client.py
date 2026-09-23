"""Small HTTP client for the local FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import requests

API_URL = os.getenv("MEETING_API_URL", "http://127.0.0.1:8000").rstrip("/")
CONNECT_TIMEOUT_SECONDS = 8
PROCESS_TIMEOUT_SECONDS = 60 * 60


class ApiUnavailable(RuntimeError):
    """Raised when the local backend cannot be reached."""


class ApiTimeout(RuntimeError):
    """Raised when the backend started a request but did not finish in time."""


class ApiError(RuntimeError):
    """Raised when the backend returns an error response."""


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    try:
        kwargs.setdefault("timeout", (CONNECT_TIMEOUT_SECONDS, 30))
        # Local requests must not inherit a workstation's external HTTP proxy.
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(method, f"{API_URL}{path}", **kwargs)
    except requests.ConnectTimeout as exc:
        raise ApiUnavailable(f"Backend недоступен по адресу {API_URL}") from exc
    except requests.ReadTimeout as exc:
        raise ApiTimeout("Backend принял запрос, но не успел вернуть результат. Проверьте состояние локальной обработки.") from exc
    except requests.ConnectionError as exc:
        raise ApiUnavailable(f"Не удалось установить или сохранить соединение с backend по адресу {API_URL}") from exc
    except requests.Timeout as exc:
        raise ApiTimeout("Локальный backend не ответил вовремя") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(str(detail))
    return response


def health() -> dict[str, Any]:
    return _request("GET", "/health", timeout=(1.5, 2)).json()


def create_meeting(filename: str, content: bytes, content_type: str) -> dict[str, Any]:
    response = _request(
        "POST",
        "/api/meetings",
        files={"audio": (filename, content, content_type)},
        timeout=(CONNECT_TIMEOUT_SECONDS, 600),
    )
    return response.json()


def get_meeting(meeting_id: str) -> dict[str, Any]:
    return _request("GET", f"/api/meetings/{meeting_id}").json()


def list_meetings() -> list[dict[str, Any]]:
    meetings, offset = [], 0
    while True:
        page = _request("GET", "/api/meetings", params={"limit": 100, "offset": offset}).json()
        meetings.extend(page.get("meetings", []))
        next_offset = page.get("next_offset")
        if next_offset is None or next_offset <= offset:
            return meetings
        offset = next_offset


def update_tasks(meeting_id: str, tasks: list[dict[str, Any]], revision: int | None = None) -> dict[str, Any]:
    payload = {"tasks": tasks}
    if revision is not None:
        payload["revision"] = revision
    return _request(
        "PUT", f"/api/meetings/{meeting_id}/tasks", json=payload
    ).json()


def get_progress(meeting_id: str) -> dict[str, Any]:
    return _request("GET", f"/api/meetings/{meeting_id}/status", timeout=(2, 5)).json()


def download_protocol(meeting_id: str, kind: str) -> bytes:
    return _request("GET", f"/api/meetings/{meeting_id}/download/{kind}").content
