"""Navigation, appearance, and local-service state."""

import streamlit as st

from frontend import api_client
from frontend.desktop_settings import save_backend_url


PAGES = {
    "Новое совещание": "✦",
    "История протоколов": "◷",
    "Дашборд поручений": "▦",
}


def render_sidebar(backend_online: bool) -> tuple[str, bool]:
    with st.sidebar:
        st.markdown(
            '<div class="brand-row"><div class="brand-mark">S</div><div><div class="brand-title">SAMRUK KAZYNA</div><div class="brand-subtitle">Протоколы совещаний</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div class='eyebrow'>Рабочее пространство</div>", unsafe_allow_html=True)
        page = st.radio(
            "Навигация",
            list(PAGES),
            format_func=lambda item: f"{PAGES[item]}  {item}",
            label_visibility="collapsed",
            key="active_page",
        )
        st.divider()
        dark = st.toggle("Тёмная тема", value=st.session_state.get("dark_theme", False), key="dark_theme")
        if backend_online:
            st.markdown("<span class='status-pill'>● Локальный backend подключён</span>", unsafe_allow_html=True)
        elif st.session_state.get("backend_health_status") == "scaffold":
            st.markdown("<span class='status-pill'>○ Backend: каркас, AI не подключён</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='status-pill'>○ Обработка пока недоступна</span>", unsafe_allow_html=True)
        _render_backend_settings()
        st.markdown(
            "<div class='small-foot' style='margin-top:1rem'>Данные обрабатываются локально.<br>Внешние облачные API не используются.</div>",
            unsafe_allow_html=True,
        )
    return page, dark


def _render_backend_settings() -> None:
    with st.expander("Подключение к backend"):
        current_url = api_client.get_backend_url()
        st.caption("На этом компьютере: http://127.0.0.1:8000. Для сервера в локальной сети укажите его адрес.")
        busy = bool(st.session_state.get("pending_meeting_id"))
        with st.form("backend_settings"):
            address = st.text_input("Адрес backend", value=current_url, key="backend_url_input")
            st.caption("При смене сервера открытый результат и черновики будут сброшены. Демопротоколы останутся в сессии.")
            submitted = st.form_submit_button("Сохранить адрес", disabled=busy)
        if busy:
            st.caption("Адрес можно изменить после завершения текущей обработки.")
        if submitted:
            try:
                normalized = save_backend_url(address)
            except ValueError as exc:
                st.error(str(exc))
            except OSError:
                st.error("Не удалось сохранить настройки в папку пользователя. Проверьте права доступа.")
            else:
                if normalized != current_url:
                    _clear_backend_state()
                st.session_state["backend_url"] = normalized
                st.session_state.pop("backend_checked_at", None)
                st.session_state["flash"] = "Адрес backend сохранён. Подключение проверяется."
                st.rerun()
        if error := st.session_state.get("backend_error"):
            st.info(error)
        if st.button("Проверить подключение", key="check_backend"):
            st.session_state.pop("backend_checked_at", None)
            st.rerun()


def _clear_backend_state() -> None:
    """Never submit a previous server's edited meeting to a newly selected one."""
    active = st.session_state.get("active_result")
    if active and not active.get("is_demo"):
        st.session_state.pop("active_result", None)
    for key in ("dashboard_drafts", "dashboard_flash", "history_selected_meeting",
                "processing_error", "backend_online", "backend_health_status", "backend_error"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith(("export_", "tasks_", "dashboard_tasks_")):
            st.session_state.pop(key, None)

