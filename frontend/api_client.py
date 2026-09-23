"""Small HTTP client for the local FastAPI backend."""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from frontend.desktop_settings import load_backend_url, validate_backend_url

CONNECT_TIMEOUT_SECONDS = 8
PROCESS_TIMEOUT_SECONDS = 60 * 60


class ApiUnavailable(RuntimeError):
    """Raised when the local backend cannot be reached."""


class ApiTimeout(RuntimeError):
    """Raised when the backend started a request but did not finish in time."""


class ApiError(RuntimeError):
    """Raised when the backend returns an error response."""


def get_backend_url() -> str:
    """Keep each Streamlit session's selected server independent of other users."""
    if get_script_run_ctx(suppress_warning=True) is None:
        return load_backend_url()
    if "backend_url" not in st.session_state:
        st.session_state["backend_url"] = load_backend_url()
    return validate_backend_url(st.session_state["backend_url"])


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    api_url = get_backend_url()
    try:
        kwargs.setdefault("timeout", (CONNECT_TIMEOUT_SECONDS, 30))
        # Local requests must not inherit a workstation's external HTTP proxy.
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(method, f"{api_url}{path}", **kwargs)
    except requests.ConnectTimeout as exc:
        raise ApiUnavailable(f"Backend недоступен по адресу {api_url}") from exc
    except requests.ReadTimeout as exc:
        raise ApiTimeout("Backend принял запрос, но не успел вернуть результат. Проверьте состояние локальной обработки.") from exc
    except requests.ConnectionError as exc:
        raise ApiUnavailable(f"Не удалось установить или сохранить соединение с backend по адресу {api_url}") from exc
    except requests.Timeout as exc:
        raise ApiTimeout("Локальный backend не ответил вовремя") from exc
    except requests.RequestException as exc:
        raise ApiError("Не удалось выполнить запрос. Проверьте адрес и настройки backend.") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", response.text) if isinstance(payload, dict) else payload
        except ValueError:
            detail = response.text
        raise ApiError(str(detail))
    return response


def health() -> dict[str, Any]:
    try:
        payload = _request("GET", "/health", timeout=(1.5, 2)).json()
    except ValueError as exc:
        raise ApiError("Сервер вернул некорректный health-ответ. Проверьте адрес backend.") from exc
    if not isinstance(payload, dict):
        raise ApiError("Сервер вернул неожиданный health-ответ. Проверьте адрес backend.")
    return payload


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
