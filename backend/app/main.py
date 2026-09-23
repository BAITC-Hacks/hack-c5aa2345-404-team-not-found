"""HTTP API for local meeting processing and protocol review.

Inference runs on one background worker so status requests remain responsive and
several uploads do not load several copies of the local speech models. Start the
application with one Uvicorn worker; jobs are persisted, but this is not a
distributed queue. A restart marks unfinished jobs as interrupted.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent.exporter import export_files
from .agent.models import ProtocolResult, Task, Utterance
from .agent.orchestrator import MeetingAgent

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "meetings"
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".mkv", ".mov", ".mp3", ".mp4", ".ogg",
    ".wav", ".webm",
}
MEETING_ID_RE = re.compile(r"^[a-f0-9]{32}$")
logger = logging.getLogger(__name__)
agent = MeetingAgent()
# Serialise task edits and their revision checks in the single API process.
_edit_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict) -> None:
    """Readers see either the previous document or the complete new document."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    return payload


def _recover_interrupted_jobs() -> None:
    for path in DATA.glob("*/status.json"):
        try:
            state = _load_json(path)
            if state.get("status") == "processing":
                # A completed result can survive a crash just before the final
                # status write; keep that valid protocol available.
                if (path.parent / "result.json").is_file():
                    state.update(status="completed", stage="completed", progress=100,
                                 message="Протокол готов")
                else:
                    state.update(status="failed", stage="failed",
                                 message="Обработка прервана перезапуском сервера. Загрузите запись повторно.")
                state["updated_at"] = _now()
                _atomic_json(path, state)
        except (OSError, ValueError):
            logger.warning("Could not recover job state %s", path)


@asynccontextmanager
async def lifespan(application: FastAPI):
    DATA.mkdir(parents=True, exist_ok=True)
    _recover_interrupted_jobs()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meeting-inference")
    application.state.executor = executor
    try:
        yield
    finally:
        # Complete the running job on a graceful shutdown. Queued jobs become
        # 'failed' on the next startup and can be uploaded again.
        await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)


app = FastAPI(title="Meeting Protocol API", version="1.2.0", lifespan=lifespan)


class EditableTask(BaseModel):
    """Fields a reviewer can correct before exporting a protocol."""

    assignee: str = Field(default="Не определён", max_length=200)
    deadline: str = Field(default="Не указан", max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    source_quote: str = Field(default="", max_length=2000)
    status: Literal["В работе", "Выполнено"] = "В работе"


class TaskChanges(BaseModel):
    tasks: list[EditableTask] = Field(max_length=1000)
    # Optional for compatibility with older clients. New clients should always
    # send the revision they opened to prevent lost edits from another session.
    revision: int | None = Field(default=None, ge=1)


def _meeting_folder(meeting_id: str) -> Path:
    if not MEETING_ID_RE.fullmatch(meeting_id):
        raise HTTPException(status_code=404, detail="Совещание не найдено")
    folder = (DATA / meeting_id).resolve()
    if folder.parent != DATA.resolve():
        raise HTTPException(status_code=404, detail="Совещание не найдено")
    return folder


def _read_state(folder: Path) -> dict | None:
    path = folder / "status.json"
    if not path.is_file():
        return None
    try:
        return _load_json(path)
    except (OSError, ValueError) as exc:
        logger.exception("Could not read job status in %s", folder)
        raise HTTPException(status_code=500, detail="Не удалось прочитать статус обработки") from exc


def _read_result(meeting_id: str) -> tuple[Path, dict]:
    folder = _meeting_folder(meeting_id)
    path = folder / "result.json"
    if not path.is_file():
        state = _read_state(folder)
        if state and state.get("status") == "processing":
            raise HTTPException(status_code=409, detail="Протокол ещё обрабатывается")
        if state and state.get("status") == "failed":
            raise HTTPException(status_code=422, detail=state["message"])
        raise HTTPException(status_code=404, detail="Совещание не найдено")
    try:
        payload = _load_json(path)
        payload.setdefault("revision", 1)
        return folder, payload
    except (OSError, ValueError) as exc:
        logger.exception("Could not read result for meeting %s", meeting_id)
        raise HTTPException(status_code=500, detail="Не удалось прочитать протокол") from exc


def _process_meeting(audio_path: Path, meeting_id: str, folder: Path, state: dict) -> None:
    """Background entry point: persist failures so polling never loses a job."""
    def progress(stage: str, percent: int, message: str) -> None:
        state.update(stage=stage, progress=percent, message=message, updated_at=_now())
        _atomic_json(folder / "status.json", state)

    try:
        # Immutable export directories keep a download consistent with the
        # saved revision while another reviewer is regenerating a protocol.
        export_folder = folder / "exports" / "1"
        result = agent.process(audio_path, meeting_id, export_folder, on_progress=progress)
        payload = result.to_dict()
        payload.update(title=state["title"], created_at=state["created_at"], revision=1,
                       export_revision=1)
        _atomic_json(folder / "result.json", payload)
        state.update(status="completed")
        progress("completed", 100, "Протокол готов")
    except Exception:
        logger.exception("Meeting processing failed for %s", meeting_id)
        state.update(status="failed", failed_stage=state.get("stage"), stage="failed",
                     message="Не удалось обработать запись. Проверьте запись и журнал backend.",
                     updated_at=_now())
        try:
            _atomic_json(folder / "status.json", state)
        except OSError:
            logger.exception("Could not persist failed status for %s", meeting_id)


@app.get("/health")
def health():
    return {"status": "ok", "local_only": True}


@app.post("/api/meetings", status_code=202)
async def create_meeting(audio: UploadFile = File(...)):
    """Stream the upload to disk, then return before local inference starts."""
    folder: Path | None = None
    submitted = False
    try:
        if not audio.filename:
            raise HTTPException(status_code=400, detail="Файл не выбран")
        filename = Path(audio.filename.replace("\\", "/"))
        suffix = filename.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Формат файла не поддерживается. Загрузите аудио или видео.")
        if audio.size is not None and audio.size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Размер файла превышает лимит 500 МБ")

        meeting_id = uuid.uuid4().hex
        folder = DATA / meeting_id
        folder.mkdir(parents=True, exist_ok=False)
        audio_path = folder / f"input{suffix}"
        size = 0
        with audio_path.open("wb") as output:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Размер файла превышает лимит 500 МБ")
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Файл пуст. Выберите запись совещания.")

        state = {
            "meeting_id": meeting_id, "status": "processing", "progress": 5,
            "stage": "queued", "message": "Запись загружена. Ожидает обработки…",
            "title": filename.stem[:160], "created_at": _now(), "updated_at": _now(),
        }
        _atomic_json(folder / "status.json", state)
        app.state.executor.submit(_process_meeting, audio_path, meeting_id, folder, state)
        submitted = True
        return {
            "meeting_id": meeting_id, "status": "processing",
            "status_url": f"/api/meetings/{meeting_id}/status",
            "result_url": f"/api/meetings/{meeting_id}", "warnings": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not accept recording")
        raise HTTPException(status_code=500, detail="Не удалось сохранить запись на сервере") from exc
    finally:
        await audio.close()
        # Only the fresh UUID folder from this request is eligible for removal.
        if folder is not None and not submitted:
            shutil.rmtree(folder, ignore_errors=True)


@app.get("/api/meetings")
def list_meetings(limit: int = 100, offset: int = 0):
    """Return saved protocols for history and the assignments dashboard."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    meetings = []
    for result_path in DATA.glob("*/result.json"):
        try:
            payload = _load_json(result_path)
            payload.setdefault("meeting_id", result_path.parent.name)
            payload.setdefault("title", f"Совещание {result_path.parent.name[:8]}")
            payload.setdefault("created_at", datetime.fromtimestamp(
                result_path.stat().st_mtime, timezone.utc).isoformat())
            payload.setdefault("revision", 1)
            meetings.append(payload)
        except (OSError, ValueError):
            logger.warning("Skipping invalid meeting result in %s", result_path)
    meetings.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    next_offset = offset + limit if offset + limit < len(meetings) else None
    return {"meetings": meetings[offset:offset + limit], "next_offset": next_offset}


@app.get("/api/meetings/{meeting_id}/status")
def get_meeting_status(meeting_id: str):
    folder = _meeting_folder(meeting_id)
    state = _read_state(folder)
    if state is not None:
        return state
    # Completed protocols created by the previous API remain usable.
    _, payload = _read_result(meeting_id)
    return {"meeting_id": meeting_id, "status": "completed", "progress": 100,
            "stage": "completed", "message": "Протокол готов",
            "warnings": payload.get("warnings", [])}


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    _, payload = _read_result(meeting_id)
    return payload


@app.put("/api/meetings/{meeting_id}/tasks")
def update_meeting_tasks(meeting_id: str, changes: TaskChanges):
    """Save reviewed tasks and regenerate immutable exports for that revision."""
    with _edit_lock:
        folder, payload = _read_result(meeting_id)
        revision = payload["revision"]
        if changes.revision is not None and changes.revision != revision:
            raise HTTPException(status_code=409, detail="Протокол изменён в другой сессии. Обновите его перед сохранением.")
        tasks = [Task(**task.model_dump()) for task in changes.tasks]
        transcript = [Utterance(**line) for line in payload.get("transcript", [])]
        result = ProtocolResult(
            meeting_id=meeting_id, status=payload.get("status", "completed"),
            summary=payload.get("summary", []), tasks=tasks, transcript=transcript,
            warnings=payload.get("warnings", []),
        )
        next_revision = revision + 1
        # Use a unique directory even after an earlier failed save; readers only
        # follow export_revision once result.json has been atomically replaced.
        export_id = f"{next_revision}-{uuid.uuid4().hex}"
        export_folder = folder / "exports" / export_id
        try:
            export_files(result, export_folder)
            payload.update(tasks=[task.model_dump() for task in changes.tasks],
                           revision=next_revision, export_revision=export_id, updated_at=_now())
            _atomic_json(folder / "result.json", payload)
        except Exception as exc:
            shutil.rmtree(export_folder, ignore_errors=True)
            logger.exception("Could not save edits for %s", meeting_id)
            raise HTTPException(status_code=500, detail="Не удалось сохранить поручения и сформировать файлы") from exc
        return payload


@app.get("/api/meetings/{meeting_id}/download/{kind}")
def download(meeting_id: str, kind: str):
    if kind not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="kind должен быть docx или pdf")
    folder, payload = _read_result(meeting_id)
    export_revision = payload.get("export_revision")
    export_folder = folder if export_revision is None else folder / "exports" / str(export_revision)
    path = (export_folder / f"protocol.{kind}").resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл ещё не готов")
    return FileResponse(path, filename=f"protocol-{meeting_id}.{kind}")
