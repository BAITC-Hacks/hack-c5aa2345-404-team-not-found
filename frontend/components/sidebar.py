"""Navigation, appearance, and local-service state."""

import streamlit as st


PAGES = {
    "Новое совещание": "✦",
    "История протоколов": "◷",
    "Дашборд поручений": "▦",
}


def render_sidebar(backend_online: bool) -> tuple[str, bool]:
    with st.sidebar:
        st.markdown(
            '<div class="brand-row"><div class="brand-mark">М</div><div><div class="brand-title">Meeting Desk</div><div class="brand-subtitle">AI · minutes</div></div></div>',
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
        else:
            st.markdown("<span class='status-pill'>○ Доступен режим демонстрации</span>", unsafe_allow_html=True)
        st.markdown(
            "<div class='small-foot' style='margin-top:1rem'>Данные обрабатываются локально.<br>Внешние облачные API не используются.</div>",
            unsafe_allow_html=True,
        )
    return page, dark

