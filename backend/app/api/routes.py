import json
import queue
import shutil
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()


def failure(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


def meeting(request, meeting_id):
    value = request.app.state.pipeline.store.get(meeting_id)
    if value is None:
        failure(404, "not_found", "Встреча не найдена.")
    return value


@router.get("/health")
def health(request: Request):
    checks = request.app.state.pipeline.readiness()
    return dict(status="ok" if checks and all(value == "ready" for value in checks.values()) else "not_ready",
                local_only=True, processing_modules=checks)


@router.post("/api/meetings", status_code=202)
def create_meeting(request: Request, response: Response, file: UploadFile = File(...), title: str = Form("")):
    pipeline = request.app.state.pipeline
    directory = None
    try:
        checks = pipeline.readiness()
        if not checks or not all(value == "ready" for value in checks.values()):
            failure(503, "not_ready", "Локальные модели, Ollama или FFmpeg пока недоступны.")
        if pipeline.jobs.full():
            failure(503, "queue_full", "Очередь заполнена. Повторите позже.")
        extension = Path(file.filename or "").suffix.lower()
        if extension not in pipeline.config.allowed_audio_extensions:
            failure(415, "unsupported_format", "Поддерживаются WAV, MP3, M4A и MP4.")
        if len(title) > 200:
            failure(422, "invalid_title", "Название должно содержать не более 200 символов.")
        title = " ".join(title.split()) or "Совещание"
        meeting_id = uuid.uuid4().hex
        directory = pipeline.config.storage_path / meeting_id
        directory.mkdir()
        source = directory / ("source" + extension)
        size, prefix = 0, b""
        with source.open("xb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > pipeline.config.max_upload_bytes:
                    failure(413, "too_large", "Максимальный размер записи — 250 МБ.")
                if not prefix:
                    prefix = chunk[:16]
                output.write(chunk)
        matches = ((extension == ".wav" and prefix[:4] == b"RIFF" and prefix[8:12] == b"WAVE") or
                   (extension == ".mp3" and (prefix[:3] == b"ID3" or (len(prefix) > 1 and prefix[0] == 255 and prefix[1] & 224 == 224))) or
                   (extension in {".mp4", ".m4a"} and prefix[4:8] == b"ftyp"))
        if not matches:
            failure(415, "invalid_media", "Содержимое файла не соответствует поддерживаемому формату.")
        value = pipeline.store.create(meeting_id, title)
        try:
            pipeline.jobs.put_nowait((meeting_id, source))
        except queue.Full:
            pipeline.store.update(meeting_id, "failed", error={"code": "queue_full", "message": "Очередь заполнена. Загрузите запись повторно."})
            failure(503, "queue_full", "Очередь заполнена. Повторите позже.")
        directory = None
        response.headers["Location"] = "/api/meetings/" + meeting_id
        return value
    finally:
        file.file.close()
        if directory is not None:
            # Delete only the UUID directory created by this request, under storage.
            root = pipeline.config.storage_path.resolve()
            target = directory.resolve()
            if target.parent == root and len(target.name) == 32:
                shutil.rmtree(target)


@router.get("/api/meetings")
def list_meetings(request: Request):
    return {"items": request.app.state.pipeline.store.list()}


@router.get("/api/meetings/{meeting_id}")
def get_meeting(request: Request, meeting_id: str):
    return meeting(request, meeting_id)


@router.get("/api/meetings/{meeting_id}/result")
def get_result(request: Request, meeting_id: str):
    value = meeting(request, meeting_id)
    if value["status"] != "completed":
        failure(409, "not_ready", "Результат ещё не готов.")
    path = request.app.state.pipeline.config.storage_path / value["id"] / "result.json"
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/meetings/{meeting_id}/export")
def get_export(request: Request, meeting_id: str, format: Literal["docx", "pdf"] = "docx"):
    value = meeting(request, meeting_id)
    if value["status"] != "completed":
        failure(409, "not_ready", "Результат ещё не готов.")
    mime = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(request.app.state.pipeline.config.storage_path / value["id"] / ("protocol." + format),
                        media_type=mime, filename="SAMRUK-protocol." + format)
