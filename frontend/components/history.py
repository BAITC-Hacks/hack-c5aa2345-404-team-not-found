"""Recent protocols and quick access to meeting results."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

import streamlit as st

from frontend.components.layout import page_header


def render_history(meetings: list[dict[str, Any]], backend_error: str | None = None) -> None:
    page_header(
        "Архив",
        "История протоколов",
        "Записи и результаты обработок, сохранённые локально.",
    )
    if backend_error:
        st.info("Backend сейчас недоступен. Здесь отображаются протоколы, созданные в демонстрационной сессии.")
    if not meetings:
        st.markdown(
            "<div class='drop-note'>История пока пуста. Загрузите запись или откройте демонстрационный протокол.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Создать первый протокол", type="primary"):
            st.session_state["navigate_to"] = "Новое совещание"
            st.rerun()
        return

    search = st.text_input("Поиск по названию", placeholder="Например, еженедельное совещание")
    visible = [
        meeting for meeting in meetings
        if search.casefold() in str(meeting.get("title", "")).casefold()
    ]
    st.caption(f"Найдено протоколов: {len(visible)}")
    if not visible:
        st.info("По этому запросу протоколов нет.")
        return

    # IDs stay unique when protocols share a title and creation minute.
    options = {str(item["meeting_id"]): item for item in visible}

    def option_label(meeting_id: str) -> str:
        item = options[meeting_id]
        return (
            f"{_date_label(item.get('created_at'))} · {item.get('title', 'Совещание')} · "
            f"{len(item.get('tasks', []))} поруч. · {meeting_id[-8:]}"
        )

    selected_id = st.selectbox(
        "Выберите протокол", list(options), format_func=option_label,
        label_visibility="collapsed", key="history_selected_meeting",
    )
    selected = options[selected_id]
    summary = selected.get("summary", [])

    st.markdown("### " + str(selected.get("title", "Протокол совещания")))
    if selected.get("is_demo"):
        st.markdown("<span class='status-pill'>Демонстрационные данные</span>", unsafe_allow_html=True)
    st.caption(
        f"{_date_label(selected.get('created_at'))} · "
        f"{len(selected.get('transcript', []))} реплик · "
        f"{len(selected.get('tasks', []))} поручений"
    )
    if summary:
        with st.container(border=True):
            st.markdown("**Саммари**")
            for item in summary:
                st.markdown(f"• {item}")
    if selected.get("tasks"):
        st.markdown("**Поручения**")
        for task in selected["tasks"]:
            st.markdown(
                f"- **{task.get('description', '')}** — {task.get('assignee', 'Не определён')} · {task.get('deadline', 'Срок не указан')}"
            )
    if st.button("Открыть протокол и экспорт", type="primary", icon="📄"):
        st.session_state["active_result"] = deepcopy(selected)
        st.session_state["navigate_to"] = "Новое совещание"
        st.rerun()


def _date_label(value: str | None) -> str:
    if not value:
        return "Дата неизвестна"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value
