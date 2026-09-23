"""Streamlit entry point for Meeting Desk."""

from __future__ import annotations

import time
import sys
from pathlib import Path

# Streamlit adds the script directory to sys.path; also include the repository
# so the same command works from a terminal, an IDE and Streamlit AppTest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from frontend import api_client
from frontend.components.dashboard import render_dashboard
from frontend.components.history import render_history
from frontend.components.layout import apply_theme
from frontend.components.meeting import render_new_meeting
from frontend.components.sidebar import render_sidebar

st.set_page_config(
    page_title="Meeting Desk — автопротоколирование",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Локальная система автоматизированного протоколирования совещаний."},
)

if destination := st.session_state.pop("navigate_to", None):
    st.session_state["active_page"] = destination

st.session_state.setdefault("dark_theme", False)
st.session_state.setdefault("demo_meetings", [])


def backend_status() -> bool:
    """Cache the local health check briefly to keep navigation responsive."""
    now = time.monotonic()
    checked_at = st.session_state.get("backend_checked_at", 0.0)
    if now - checked_at > 4:
        try:
            health = api_client.health()
            st.session_state["backend_online"] = health.get("status") == "ok"
            st.session_state["backend_error"] = None
        except (api_client.ApiUnavailable, api_client.ApiError, api_client.ApiTimeout) as exc:
            st.session_state["backend_online"] = False
            st.session_state["backend_error"] = str(exc)
        st.session_state["backend_checked_at"] = now
    return bool(st.session_state.get("backend_online", False))


def meeting_data() -> tuple[list[dict], str | None]:
    """Read stored meetings from the local backend and merge current demos."""
    persisted: list[dict] = []
    error = None
    if st.session_state.get("backend_online"):
        try:
            persisted = api_client.list_meetings()
        except (api_client.ApiUnavailable, api_client.ApiError, api_client.ApiTimeout) as exc:
            error = str(exc)
    else:
        error = st.session_state.get("backend_error")
    merged = {str(item.get("meeting_id")): item for item in persisted}
    for item in st.session_state.get("demo_meetings", []):
        merged[str(item.get("meeting_id"))] = item
    meetings = list(merged.values())
    meetings.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return meetings, error


backend_online = backend_status()
page, dark_theme = render_sidebar(backend_online)
apply_theme(dark_theme)
if message := st.session_state.pop("flash", None):
    st.success(message)

if page == "Новое совещание":
    render_new_meeting(backend_online)
else:
    meetings, backend_error = meeting_data()
    if page == "История протоколов":
        render_history(meetings, backend_error)
    elif page == "Дашборд поручений":
        render_dashboard(meetings, backend_error)
