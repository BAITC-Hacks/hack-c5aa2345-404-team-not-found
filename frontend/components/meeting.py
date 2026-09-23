"""Upload, real pipeline progress, editable protocol and local downloads."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import date, datetime
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from frontend import api_client, api_mock
from frontend.components.layout import page_header
from frontend.exporters import make_docx, make_pdf

SUPPORTED_EXTENSIONS = ["aac", "flac", "m4a", "mkv", "mov", "mp3", "mp4", "ogg", "wav", "webm"]
MAX_FILE_SIZE = 500 * 1024 * 1024
API_ERRORS = (api_client.ApiError, api_client.ApiUnavailable, api_client.ApiTimeout)


def render_new_meeting(backend_online: bool) -> None:
    page_header("Протоколирование", "От встречи к решениям",
                "Загрузите запись, проверьте протокол и передайте поручения в работу.")
    file_tab, link_tab = st.tabs(["Запись совещания", "Онлайн-встреча"])
    with file_tab:
        left, right = st.columns([1.55, 0.9], gap="large")
        with left:
            st.markdown("#### Загрузите аудио или видео")
            uploaded = st.file_uploader(
                "Перетащите запись или выберите файл",
                type=SUPPORTED_EXTENSIONS, key="meeting_upload",
                help="MP3, WAV, M4A, MP4, MOV, WEBM, AAC, FLAC, MKV, OGG. До 500 МБ.",
            )
            if uploaded is not None:
                st.caption(f"{uploaded.name} · {uploaded.size / 1024**2:.1f} МБ")
            st.caption("Русский · Қазақша · Смешанная речь. Обработка локальными моделями.")
        with right:
            with st.container(border=True):
                st.markdown("#### В готовом протоколе")
                st.markdown("**01** Ключевые решения и саммари\n\n"
                            "**02** Поручения, ответственные и сроки\n\n"
                            "**03** Реплики по спикерам и временные отметки")
                st.caption("Исправьте выводы ИИ перед экспортом и передачей команде.")

        process, demo = st.columns(2)
        busy = bool(st.session_state.get("pending_meeting_id"))
        if process.button("Начать обработку", type="primary", use_container_width=True,
                          disabled=uploaded is None or busy or not backend_online):
            if uploaded.size > MAX_FILE_SIZE:
                st.error("Файл превышает лимит 500 МБ.")
            elif uploaded.size == 0:
                st.error("Файл пуст. Выберите запись с аудиодорожкой.")
            else:
                try:
                    with st.spinner("Загрузка записи в локальный сервис…"):
                        created = api_client.create_meeting(
                            uploaded.name, uploaded.getvalue(),
                            mimetypes.guess_type(uploaded.name)[0] or "application/octet-stream",
                        )
                    st.session_state["pending_meeting_id"] = created["meeting_id"]
                    st.session_state.pop("processing_error", None)
                    st.rerun()
                except API_ERRORS as exc:
                    st.error(f"Не удалось загрузить запись: {exc}")
        if demo.button("Посмотреть демо-протокол", use_container_width=True, disabled=busy):
            progress = st.progress(0, text="Готовим демонстрацию…")
            result = api_mock.process_meeting(
                progress_callback=lambda value, message: progress.progress(value, text=message),
            )
            _remember_demo(result)
            st.session_state["active_result"] = result
            st.session_state["flash"] = "Открыт синтетический пример. Запись не обрабатывалась."
            st.rerun()
        if not backend_online:
            st.info("Сервис обработки не подключён. Можно открыть демо и проверить весь сценарий без нейросетей.")

    with link_tab:
        st.markdown("#### Teams · Zoom · Google Meet")
        st.text_input("Ссылка на встречу", placeholder="https://meet.google.com/…", key="meeting_url")
        st.button("Подключиться к встрече", disabled=True)
        st.info("Для подключения участником нужен коннектор видеоконференций. В текущей версии загрузите запись встречи.")

    if busy:
        _render_processing()
    if error := st.session_state.get("processing_error"):
        st.error(error)
    if result := st.session_state.get("active_result"):
        st.divider()
        render_result(result)


@st.fragment(run_every=2)
def _render_processing() -> None:
    """Poll real backend milestones; no time-based percentage estimates."""
    meeting_id = st.session_state.get("pending_meeting_id")
    if not meeting_id:
        return
    try:
        job = api_client.get_progress(meeting_id)
        value = max(0, min(100, int(job.get("progress", 0))))
        st.progress(value, text=job.get("message", "Обработка записи…"))
        st.caption("Транскрибация → диаризация → анализ поручений → экспорт")
        if job["status"] == "completed":
            result = api_client.get_meeting(meeting_id)
            st.session_state["active_result"] = result
            st.session_state.pop("pending_meeting_id", None)
            st.session_state["flash"] = "Протокол готов к проверке."
            st.rerun()
        elif job["status"] == "failed":
            st.session_state["processing_error"] = job.get("message", "Обработка не завершена.")
            st.session_state.pop("pending_meeting_id", None)
            st.rerun()
    except API_ERRORS as exc:
        st.warning(f"Не удалось обновить статус: {exc}. Повторим запрос автоматически.")


def _remember_demo(result: dict[str, Any]) -> None:
    saved = st.session_state.setdefault("demo_meetings", [])
    saved[:] = [item for item in saved if item["meeting_id"] != result["meeting_id"]]
    saved.insert(0, result)


def render_result(result: dict[str, Any]) -> None:
    tasks, transcript = result.get("tasks", []), result.get("transcript", [])
    st.subheader(result.get("title") or "Протокол совещания")
    st.caption(f"{_format_date(result.get('created_at'))} · {len(transcript)} реплик · {len(tasks)} поручений")
    if result.get("is_demo"):
        st.info("Демо-протокол: синтетические реплики и даты. Данные сохраняются только в этой сессии.")
    if summary := result.get("summary"):
        st.markdown(
            "<div class='summary-card'><div class='panel-title'>Саммари совещания</div>" +
            "".join(f"<p>• {escape(str(item))}</p>" for item in summary) + "</div>",
            unsafe_allow_html=True,
        )
    task_tab, transcript_tab, export_tab = st.tabs(["Поручения", "Транскрипт", "Экспорт"])
    with task_tab:
        _render_editable_tasks(result, tasks)
    with transcript_tab:
        if not transcript:
            st.info("Транскрипт пуст.")
        for line in transcript:
            speaker = escape(_speaker_name(str(line.get("speaker", ""))))
            text = escape(str(line.get("text", "")))
            timestamp = _format_timestamp(line.get("start"))
            st.markdown(
                f"<div class='transcript-line'><div class='transcript-speaker'>{speaker} "
                f"<span class='small-foot'>{timestamp}</span></div>"
                f"<div class='transcript-text'>{text}</div></div>", unsafe_allow_html=True,
            )
    with export_tab:
        _render_exports(result)
    if warnings := result.get("warnings"):
        with st.expander(f"Замечания обработки · {len(warnings)}", expanded=True):
            for warning in warnings:
                st.warning(str(warning))


def _fingerprint(result: dict) -> str:
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _render_editable_tasks(result: dict, tasks: list[dict]) -> None:
    """Keep source rows apart from Streamlit's widget delta state.

    The hidden quote travels with its own row, including after row deletion.
    A form batches edits and the content fingerprint resets the editor on save.
    """
    key = f"tasks_{result['meeting_id']}_{_fingerprint(result)}"
    records = [{
        "Поручение": task.get("description", ""),
        "Ответственный": task.get("assignee", ""),
        "Срок": task.get("deadline", ""),
        "Статус": task.get("status", "В работе"),
        "_quote": task.get("source_quote", ""),
    } for task in tasks]
    data = pd.DataFrame(records, columns=["Поручение", "Ответственный", "Срок", "Статус", "_quote"]).astype(str)
    if not tasks:
        st.info("ИИ не выделил поручений. При необходимости добавьте их вручную.")
    with st.form(f"form_{key}"):
        edited = st.data_editor(
            data, key=key, use_container_width=True, hide_index=True, num_rows="dynamic",
            disabled=["_quote"],
            column_config={
                "Поручение": st.column_config.TextColumn("Суть поручения", width="large", required=True, max_chars=2000),
                "Ответственный": st.column_config.TextColumn(width="medium", max_chars=200),
                "Срок": st.column_config.TextColumn(width="small", max_chars=120, help="YYYY-MM-DD или ДД.ММ.ГГГГ. Неясные сроки сохраняйте текстом."),
                "Статус": st.column_config.SelectboxColumn(options=["В работе", "Выполнено"], default="В работе", required=True),
                "_quote": None,
            },
        )
        st.caption("Для календарного контроля укажите дату с годом. Сроки «до пятницы» и «не указан» требуют уточнения.")
        submitted = st.form_submit_button("Сохранить правки", type="primary")
    if submitted:
        _save_task_edits(result, edited)
    if tasks:
        with st.expander("Основания поручений · цитаты из расшифровки"):
            for index, task in enumerate(tasks, 1):
                st.write(f"{index}. {task.get('source_quote') or 'Добавлено вручную / цитата не определена'}")


def _text(value: Any) -> str:
    return "" if value is None or (not isinstance(value, str) and pd.isna(value)) else str(value).strip()


def _save_task_edits(result: dict, edited: Any) -> None:
    changed = []
    for index, row in enumerate(edited.to_dict("records"), 1):
        description = _text(row.get("Поручение"))
        if not description:
            st.error(f"Заполните суть поручения в строке {index} или удалите эту строку.")
            return
        changed.append({
            "description": description,
            "assignee": _text(row.get("Ответственный")) or "Не определён",
            "deadline": _text(row.get("Срок")) or "Не указан",
            "status": _text(row.get("Статус")) or "В работе",
            "source_quote": _text(row.get("_quote")),
        })
    try:
        if result.get("is_demo"):
            updated = api_mock.update_tasks(result, changed)
            _remember_demo(updated)
        else:
            updated = api_client.update_tasks(result["meeting_id"], changed, result.get("revision"))
        st.session_state["active_result"] = updated
        st.session_state["flash"] = "Поручения сохранены. Экспорт будет включать исправления."
        st.rerun()
    except API_ERRORS as exc:
        st.error(f"Не удалось сохранить правки: {exc}")


def _render_exports(result: dict) -> None:
    st.markdown("#### Итоговый протокол")
    st.caption("Саммари, сохранённые поручения и транскрипт. Сначала сохраните правки в таблице.")
    key = f"export_{result['meeting_id']}_{_fingerprint(result)}"
    if st.button("Подготовить файлы", key=f"prepare_{key}", type="primary"):
        with st.spinner("Формируем документы…"):
            try:
                if result.get("is_demo"):
                    files = {"docx": make_docx(result), "pdf": make_pdf(result)}
                else:
                    files = {kind: api_client.download_protocol(result["meeting_id"], kind) for kind in ("docx", "pdf")}
                st.session_state[key] = files
            except (*API_ERRORS, RuntimeError, OSError, ValueError) as exc:
                st.error(f"Не удалось подготовить экспорт: {exc}")
    if files := st.session_state.get(key):
        docx, pdf = st.columns(2)
        suffix = result["meeting_id"][:12]
        docx.download_button("Скачать DOCX", files["docx"], f"protocol-{suffix}.docx",
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             key=f"docx_{key}", use_container_width=True)
        pdf.download_button("Скачать PDF", files["pdf"], f"protocol-{suffix}.pdf", "application/pdf",
                            key=f"pdf_{key}", use_container_width=True)


def task_deadline_state(task: dict) -> tuple[str, str]:
    if task.get("status") == "Выполнено":
        return "Выполнено", "deadline-ok"
    value = str(task.get("deadline", "")).strip()
    parsed = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return "Срок не распознан", ""
    days = (parsed - date.today()).days
    if days < 0:
        return "Просрочено", "deadline-overdue"
    if days <= 3:
        return "Скоро срок", "deadline-soon"
    return "В срок", "deadline-ok"


def _format_date(value: str | None) -> str:
    if not value:
        return "Дата не указана"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y · %H:%M")
    except ValueError:
        return value


def _format_timestamp(value: Any) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return ""
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _speaker_name(value: str) -> str:
    if value.startswith("SPEAKER_"):
        try:
            return f"Спикер {int(value.rsplit('_', 1)[1]) + 1}"
        except ValueError:
            pass
    return value or "Спикер"
