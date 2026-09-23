"""Portfolio dashboard with isolated drafts and revision-aware saves."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

import streamlit as st

from frontend import api_client
from frontend.components.layout import page_header
from frontend.components.meeting import task_deadline_state


def render_dashboard(meetings: list[dict[str, Any]], backend_error: str | None = None) -> None:
    page_header(
        "Контроль исполнения", "Дашборд поручений",
        "Общий список задач по протоколам. Проверьте ответственных, сроки и статусы.",
    )
    flash = st.session_state.pop("dashboard_flash", None)
    if flash:
        if flash["errors"]:
            st.error("Не удалось сохранить некоторые правки. Черновик сохранён. " + " · ".join(flash["errors"]))
        else:
            st.toast("Изменения сохранены", icon="✅")
    if backend_error:
        st.info("История backend недоступна. Доступны протоколы текущей демонстрационной сессии и сохранённые черновики.")

    tasks = _collect_tasks(meetings)
    overdue = sum(item["deadline_state"] == "Просрочено" for item in tasks)
    done = sum(item["status"] == "Выполнено" for item in tasks)
    active = sum(item["status"] == "В работе" and item["deadline_state"] != "Просрочено" for item in tasks)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("В работе", active, help="Открытые поручения без истёкшего срока")
    k2.metric("Просрочено", overdue, delta=str(overdue) if overdue else None, delta_color="inverse")
    k3.metric("Выполнено", done)
    k4.metric("Всего поручений", len(tasks))

    st.markdown("### Единый реестр")
    filter_choice = st.selectbox(
        "Показать", ["Все поручения", "В работе", "Просрочено", "Выполнено"], key="dashboard_filter",
    )
    current_rows = _editor_rows(_filter_tasks(tasks, filter_choice))
    # Keep the source snapshot separate from the widget's edit-delta dictionary.
    # An API refresh must not silently replace the base of a pending draft.
    drafts = st.session_state.setdefault("dashboard_drafts", {})
    draft = drafts.get(filter_choice)
    current_signature = _fingerprint({
        "meetings": [{
            "meeting_id": item.get("meeting_id"), "revision": item.get("revision"),
            "title": item.get("title"), "tasks": item.get("tasks", []),
        } for item in meetings], "filter": filter_choice,
    })
    if draft is None:
        draft = {
            "meetings": deepcopy(meetings), "rows": current_rows,
            "source_signature": current_signature, "generation": 0,
        }
        drafts[filter_choice] = draft
    if draft["source_signature"] != current_signature:
        st.info("Список протоколов изменился. Здесь сохранён ваш черновик; обновите список, чтобы начать редактирование актуальной версии.")
    if st.button("Обновить список и сбросить черновик", key="refresh_dashboard"):
        drafts.pop(filter_choice, None)
        st.rerun()
    if not draft["rows"]:
        st.info("Нет поручений для выбранного фильтра." if tasks else "Поручения появятся здесь после обработки первой записи.")
        return

    editor_key = "dashboard_tasks_" + _fingerprint({
        "filter": filter_choice, "rows": draft["rows"],
        "source": draft["source_signature"], "generation": draft["generation"],
    })
    # A form submits all changed cells together, without rerunning the app
    # and requesting the backend after every individual edit.
    with st.form("dashboard_form_" + editor_key):
        edited = st.data_editor(
            draft["rows"], key=editor_key, hide_index=True, num_rows="fixed",
            use_container_width=True,
            disabled=["meeting_id", "task_index", "Совещание", "Индикация срока"],
            column_config={
                "meeting_id": None, "task_index": None,
                "Совещание": st.column_config.TextColumn(width="medium"),
                "Поручение": st.column_config.TextColumn("Суть поручения", width="large", required=True, max_chars=2000),
                "Ответственный": st.column_config.TextColumn(width="medium", max_chars=200),
                "Срок": st.column_config.TextColumn(width="small", max_chars=120, help="Точная дата: ГГГГ-ММ-ДД или ДД.ММ.ГГГГ. Словесные сроки требуют проверки."),
                "Индикация срока": st.column_config.TextColumn("Дедлайн", width="small"),
                "Статус": st.column_config.SelectboxColumn(options=["В работе", "Выполнено"], required=True, width="small"),
            },
        )
        submitted = st.form_submit_button("Сохранить изменения", type="primary", use_container_width=True)
    st.caption("Сохраните правки перед переходом на другой экран. Красная отметка — срок истёк или наступает в ближайшие три дня. Индикация обновляется после сохранения.")

    if submitted:
        changes = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)
        # Store submitted cells independently of widget cleanup, so a failed
        # request or navigation cannot discard these corrections.
        draft["rows"] = deepcopy(changes)
        updated, errors = _save_dashboard_edits(changes, draft["meetings"])
        if errors:
            saved_by_id = {str(item["meeting_id"]): item for item in updated}
            draft["meetings"] = [
                deepcopy(saved_by_id.get(str(item.get("meeting_id")), item))
                for item in draft["meetings"]
            ]
            draft["generation"] += 1
        else:
            drafts.pop(filter_choice, None)
        st.session_state["dashboard_flash"] = {"errors": errors}
        st.rerun()


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()[:20]


def _filter_tasks(tasks: list[dict[str, Any]], choice: str) -> list[dict[str, Any]]:
    if choice == "В работе":
        return [item for item in tasks if item["status"] == "В работе" and item["deadline_state"] != "Просрочено"]
    if choice == "Просрочено":
        return [item for item in tasks if item["deadline_state"] == "Просрочено"]
    if choice == "Выполнено":
        return [item for item in tasks if item["status"] == "Выполнено"]
    return tasks


def _editor_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "meeting_id": item["meeting_id"], "task_index": item["task_index"],
        "Совещание": item["meeting_title"], "Поручение": item["description"],
        "Ответственный": item["assignee"], "Срок": item["deadline"],
        "Индикация срока": _deadline_label(item["deadline_state"]), "Статус": item["status"],
    } for item in tasks]


def _collect_tasks(meetings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for meeting in meetings:
        meeting_id = str(meeting.get("meeting_id", ""))
        for index, task in enumerate(meeting.get("tasks", [])):
            state, _ = task_deadline_state(task)
            rows.append({
                "meeting_id": meeting_id, "meeting_title": meeting.get("title") or "Протокол совещания",
                "task_index": index, "description": task.get("description", ""),
                "assignee": task.get("assignee", "Не определён"), "deadline": task.get("deadline", "Не указан"),
                "status": task.get("status", "В работе"), "deadline_state": state,
            })
    return rows


def _deadline_label(state: str) -> str:
    icons = {"Просрочено": "🔴", "Скоро срок": "🔴", "В срок": "🟢", "Выполнено": "✓"}
    return f"{icons.get(state, '•')} {state}"


def _prepare_updates(changes: list[dict[str, Any]], meetings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate every row before writing anything; preserve untouched fields."""
    originals = {str(item.get("meeting_id")): item for item in meetings}
    candidates: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, int]] = set()
    for row in changes:
        meeting_id = str(row.get("meeting_id", ""))
        if meeting_id not in originals:
            raise ValueError("Протокол больше не найден. Обновите список.")
        try:
            index = int(row.get("task_index", -1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Не удалось определить исходное поручение. Обновите список.") from exc
        if (meeting_id, index) in seen or not 0 <= index < len(originals[meeting_id].get("tasks", [])):
            raise ValueError("Список поручений изменился. Обновите список.")
        seen.add((meeting_id, index))
        description = str(row.get("Поручение") or "").strip()
        assignee = str(row.get("Ответственный") or "").strip() or "Не определён"
        deadline = str(row.get("Срок") or "").strip() or "Не указан"
        status = row.get("Статус") or "В работе"
        if not description:
            title = originals[meeting_id].get("title", meeting_id)
            raise ValueError(f"Заполните суть поручения №{index + 1} в протоколе «{title}».")
        if len(description) > 2000 or len(assignee) > 200 or len(deadline) > 120:
            raise ValueError("Слишком длинное значение: поручение — до 2000, ответственный — до 200, срок — до 120 символов.")
        if status not in {"В работе", "Выполнено"}:
            raise ValueError("Выберите статус «В работе» или «Выполнено».")
        if meeting_id not in candidates:
            candidates[meeting_id] = deepcopy(originals[meeting_id])
        candidate = candidates[meeting_id]
        # Index belongs to the source snapshot and is hidden/disabled. The quote
        # and every other provenance field stay attached to their original task.
        candidate["tasks"][index].update({
            "description": description, "assignee": assignee,
            "deadline": deadline, "status": status,
        })
    return [item for meeting_id, item in candidates.items() if item["tasks"] != originals[meeting_id].get("tasks", [])]


def _remember_saved_result(result: dict[str, Any]) -> None:
    meeting_id = str(result.get("meeting_id"))
    if result.get("is_demo") or meeting_id.startswith("demo-"):
        saved = st.session_state.setdefault("demo_meetings", [])
        replacement = deepcopy(result)
        st.session_state["demo_meetings"] = [
            replacement if str(item.get("meeting_id")) == meeting_id else item for item in saved
        ]
        if not any(str(item.get("meeting_id")) == meeting_id for item in saved):
            st.session_state["demo_meetings"].insert(0, replacement)
    active = st.session_state.get("active_result")
    if active and str(active.get("meeting_id")) == meeting_id:
        st.session_state["active_result"] = deepcopy(result)


def _save_dashboard_edits(
    changes: list[dict[str, Any]], meetings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return successes and errors; never mutate the source on a failed save."""
    try:
        pending = _prepare_updates(changes, meetings)
    except ValueError as exc:
        return [], [str(exc)]
    updated, failures = [], []
    for candidate in pending:
        meeting_id = str(candidate["meeting_id"])
        try:
            if candidate.get("is_demo") or meeting_id.startswith("demo-"):
                # Demo records need the same stale-draft protection locally.
                current = next((item for item in st.session_state.get("demo_meetings", []) if str(item.get("meeting_id")) == meeting_id), None)
                source = next(item for item in meetings if str(item.get("meeting_id")) == meeting_id)
                if current is not None and current.get("tasks") != source.get("tasks"):
                    failures.append(f"{candidate.get('title', meeting_id)}: поручения уже изменились; обновите список перед сохранением.")
                    continue
                result = candidate
            else:
                result = api_client.update_tasks(meeting_id, candidate["tasks"], revision=candidate.get("revision"))
        except (api_client.ApiError, api_client.ApiUnavailable, api_client.ApiTimeout) as exc:
            failures.append(f"{candidate.get('title', meeting_id)}: {exc}")
            continue
        _remember_saved_result(result)
        updated.append(result)
    return updated, failures
