"""Single-worker local meeting processing, with explicit resource checks."""
from __future__ import annotations

from dataclasses import asdict
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.request
from urllib.parse import urlsplit
import wave

from app.storage import Store

log = logging.getLogger(__name__)
UNRESOLVED = "UNRESOLVED"


class ProcessingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


def merge_segments(segments, turns) -> list[dict]:
    """Keep every STT segment; never assign words to competing speaker turns."""
    result = []
    ordered_turns = sorted(turns, key=lambda item: (item.start, item.end))
    for item in ordered_turns:
        if not all(math.isfinite(value) for value in (item.start, item.end)) or not 0 <= item.start <= item.end:
            raise ValueError("Invalid diarization timestamps")
    for segment in segments:
        start, end = float(segment.start), float(segment.end)
        if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start <= end:
            raise ValueError("Invalid transcript timestamps")
        overlaps: dict[str, list[tuple[float, float]]] = {}
        for turn in ordered_turns:
            if turn.start > end:
                break
            left, right = max(start, turn.start), min(end, turn.end)
            if right > left or (start == end and turn.start <= start < turn.end):
                overlaps.setdefault(turn.speaker, []).append((left, right))
        speaker = UNRESOLVED
        if len(overlaps) == 1:
            candidate, intervals = next(iter(overlaps.items()))
            # Use union length: duplicated/overlapping turns must not inflate coverage.
            coverage = 0.0
            previous_end = start
            for left, right in sorted(intervals):
                coverage += max(0.0, right - max(left, previous_end))
                previous_end = max(previous_end, right)
            if coverage >= (end - start) / 2:
                speaker = candidate
        result.append({
            "speaker": speaker, "start": start, "end": end,
            "text": " ".join(segment.text.splitlines()).strip(), "detected_languages": list(segment.detected_languages),
        })
    return result


def transcript_chunks(transcript: list[dict], limit: int = 4500) -> list[str]:
    """Chunk only at STT turn boundaries; fail rather than silently cut a turn."""
    if limit < 1:
        raise ValueError("Chunk limit must be positive")
    chunks, lines, size = [], [], 0
    for segment in transcript:
        # STT model output can contain newlines/colon prefixes. Keep one input turn
        # so such content cannot create a forged speaker label in the LLM parser.
        text = " ".join(segment["text"].splitlines()).strip()
        speaker = segment["speaker"]
        if not re.fullmatch(r"[A-Za-z0-9_ -]{1,80}", speaker):
            raise ValueError("Invalid anonymous speaker label")
        line = speaker + ": " + text
        if len(line) > limit:
            raise ProcessingError("transcript_too_long", "Одна реплика превышает лимит локального анализа. Требуется разделение реплик; текст не обрезан.")
        if lines and size + 1 + len(line) > limit:
            chunks.append("\n".join(lines))
            lines, size = [], 0
        lines.append(line)
        size += len(line) + (1 if len(lines) > 1 else 0)
    if lines:
        chunks.append("\n".join(lines))
    return chunks


def exact_unique_tasks(tasks: list[dict]) -> list[dict]:
    fields = ("assignee", "task", "deadline", "assigned_by", "source_speaker", "source_text")
    seen, unique = set(), []
    for task in tasks:
        key = tuple(task[field] for field in fields)
        if key not in seen:
            seen.add(key)
            unique.append(task)
    return unique


def atomic_json(path: Path, value: dict) -> None:
    handle, temporary = tempfile.mkstemp(prefix=".result-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class _InstanceLock:
    """OS-held file lock; a crash releases it without stale PID file recovery."""
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.stream = (root / ".pipeline.lock").open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise RuntimeError("Another backend already uses this meeting storage. Run one server worker.") from exc

    def close(self):
        if not self.stream.closed:
            self.stream.close()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _installed(*distributions: str) -> bool:
    try:
        return all(importlib.metadata.version(name) for name in distributions)
    except importlib.metadata.PackageNotFoundError:
        return False


class Pipeline:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.storage_path).resolve()
        if config.queue_capacity < 1:
            raise ValueError("Queue capacity must be positive")
        self._instance_lock = _InstanceLock(self.root)
        try:
            self.store = Store(self.root)
            self.store.recover()
            self.jobs = queue.Queue(maxsize=config.queue_capacity)
            self._stopping = threading.Event()
            self._processing = threading.Lock()
            self.worker = threading.Thread(target=self._run, name="local-meeting-worker", daemon=True)
            self.worker.start()
        except BaseException:
            self._instance_lock.close()
            raise

    def _ffmpeg_path(self) -> str | None:
        value = str(self.config.ffmpeg)
        path = shutil.which(value)
        return path or (str(Path(value).resolve()) if Path(value).is_file() else None)

    def _ollama_ready(self) -> bool:
        try:
            parsed = urlsplit(self.config.ollama_url)
        except ValueError:
            return False
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or "cloud" in self.config.ollama_model.lower()):
            return False
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
            request = urllib.request.Request(self.config.ollama_url.rstrip("/") + "/api/show",
                data=json.dumps({"model": self.config.ollama_model}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=3) as response:
                content = response.read(1024 * 1024 + 1)
                if len(content) > 1024 * 1024:
                    return False
                metadata = json.loads(content)
                return isinstance(metadata, dict) and not metadata.get("remote_host") and not metadata.get("remote_model")
        except (OSError, ValueError):
            return False

    def readiness(self) -> dict[str, str]:
        # Availability checks never load model weights or send meeting contents.
        ffmpeg = bool(self._ffmpeg_path())
        stt = (Path(self.config.whisper_path) / "model.bin").is_file() and _installed("faster-whisper", "ctranslate2")
        diarization = ((Path(self.config.pyannote_path) / "config.yaml").is_file()
                       and _installed("pyannote.audio", "torch", "torchcodec", "soundfile"))
        llm = _installed("httpx", "pydantic") and self._ollama_ready()
        export = False
        try:
            from app.services.export.local import font_path
            export = _installed("python-docx", "reportlab") and Path(font_path()).is_file()
        except (ImportError, OSError, ValueError, RuntimeError, TypeError):
            pass
        return {key: "ready" if available else "missing" for key, available in
                {"ffmpeg": ffmpeg, "stt": stt, "diarization": diarization, "analysis": llm, "export": export}.items()}

    def normalize(self, source: Path, output: Path) -> float:
        executable = self._ffmpeg_path()
        if not executable:
            raise ProcessingError("ffmpeg_missing", "FFmpeg не настроен на сервере.")
        duration_limit = min(float(self.config.max_duration_seconds), 3600.0)
        if duration_limit <= 0:
            raise ProcessingError("invalid_configuration", "Некорректный лимит длительности на сервере.")
        command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-protocol_whitelist", "file", "-format_whitelist", "wav,mp3,mov",
                   "-i", str(source), "-map", "0:a:0", "-vn", "-sn", "-dn",
                   "-t", str(duration_limit + 1), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                   "-f", "wav", str(output)]
        try:
            subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            with wave.open(str(output), "rb") as decoded:
                duration = decoded.getnframes() / decoded.getframerate()
                valid = decoded.getnchannels() == 1 and decoded.getsampwidth() == 2 and decoded.getframerate() == 16000
            if not valid or duration <= 0:
                raise ProcessingError("invalid_audio", "В записи не удалось получить аудиодорожку.")
            if duration > duration_limit:
                raise ProcessingError("audio_too_long", "Запись превышает лимит длительности. Загрузите более короткую запись; файл не обрабатывался частично.")
            return duration
        except subprocess.TimeoutExpired as exc:
            raise ProcessingError("preprocessing_timeout", "Подготовка записи заняла слишком много времени.") from exc
        except (subprocess.CalledProcessError, OSError, wave.Error, EOFError) as exc:
            raise ProcessingError("invalid_audio", "Не удалось прочитать аудиодорожку. Поддерживаются WAV, MP3, M4A и MP4.") from exc

    def process(self, meeting_id: str, source: Path) -> None:
        with self._processing:
            stage = "preprocessing"
            try:
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", meeting_id):
                    raise ValueError("Invalid meeting identifier")
                directory = (self.root / meeting_id).resolve()
                if directory.parent != self.root:
                    raise ValueError("Invalid meeting directory")
                source = Path(source).resolve()
                if source.parent != directory or not source.is_file():
                    raise ValueError("Input is outside its meeting directory")
                meeting = self.store.get(meeting_id)
                if not meeting:
                    raise ValueError("Meeting does not exist")
                self.store.update(meeting_id, "processing", stage=stage)
                normalized = directory / "normalized.wav"
                duration = self.normalize(source, normalized)

                from app.services.stt.local import LocalSTTService
                from app.services.diarization.local import LocalDiarizationService
                from app.services.llm.local import LocalMeetingAnalysisService

                stage = "transcribing"
                self.store.update(meeting_id, "processing", stage=stage)
                stt = LocalSTTService(self.config.whisper_path, device=self.config.device,
                                      compute_type=self.config.compute_type, release_after_call=True)
                transcript = stt.transcribe(normalized)
                if not transcript.segments:
                    raise ProcessingError("speech_not_found", "В записи не удалось обнаружить речь.")
                if any(segment.end > duration + 0.1 for segment in transcript.segments):
                    raise ProcessingError("invalid_timestamps", "Модель вернула временные метки за пределами записи.")

                stage = "diarizing"
                self.store.update(meeting_id, "processing", stage=stage)
                diarization = LocalDiarizationService(self.config.pyannote_path, device=self.config.device,
                                                       exclusive=False, release_after_call=True)
                turns = diarization.diarize(normalized)
                if any(turn.end > duration + 0.1 for turn in turns):
                    raise ProcessingError("invalid_timestamps", "Модель говорящих вернула временные метки за пределами записи.")
                labeled = merge_segments(transcript.segments, turns)

                stage = "analyzing"
                self.store.update(meeting_id, "processing", stage=stage)
                analysis = LocalMeetingAnalysisService(base_url=self.config.ollama_url, model=self.config.ollama_model,
                                                      num_ctx=8192, max_transcript_chars=4500)
                chunks = transcript_chunks(labeled)
                summaries, tasks = [], []
                for chunk in chunks:
                    summary, chunk_tasks = analysis.analyze(chunk)
                    summaries.append(summary)
                    for task in chunk_tasks:
                        data = asdict(task)
                        # UNRESOLVED may represent multiple people, so a single self-introduction
                        # cannot establish the author of other ambiguous segments.
                        if data["source_speaker"] == UNRESOLVED:
                            data["assigned_by"] = None
                        tasks.append(data)
                summary = summaries[0] if len(summaries) == 1 else "\n\n".join(
                    f"Часть {index + 1}/{len(summaries)}\n{text}" for index, text in enumerate(summaries))
                result = {"meeting_id": meeting_id, "processing_state": "completed", "local_only": True,
                          "summary": summary, "transcript": labeled, "tasks": exact_unique_tasks(tasks),
                          "exports": ["docx", "pdf"]}
                from app.schemas import MeetingAnalysisResponse
                MeetingAnalysisResponse.model_validate(result, strict=True)
                from app.services.export.local import export_protocol
                export_protocol(meeting["title"], result, directory)
                if not all((directory / ("protocol." + extension)).is_file() for extension in result["exports"]):
                    raise ProcessingError("export_failed", "Не удалось подготовить оба файла протокола.")
                atomic_json(directory / "result.json", result)
                self.store.update(meeting_id, "completed")
            except Exception as exc:
                error = {"code": exc.code, "message": exc.safe_message} if isinstance(exc, ProcessingError) else {
                    "code": "processing_failed", "message": "Не удалось обработать запись. Проверьте локальные модели и настройки сервера."}
                self.store.update(meeting_id, "failed", error=error)
                # Never put transcripts, local paths, model responses or exception strings in logs.
                log.warning("Meeting processing failed at %s (%s)", stage, type(exc).__name__)

    def _run(self):
        try:
            while not self._stopping.is_set():
                try:
                    job = self.jobs.get(timeout=0.2)
                except queue.Empty:
                    continue
                try:
                    self.process(*job)
                except Exception:
                    log.error("Meeting worker could not persist a processing result")
                finally:
                    self.jobs.task_done()
        finally:
            self._instance_lock.close()

    def close(self):
        self._stopping.set()
        while True:
            try:
                meeting_id, _ = self.jobs.get_nowait()
            except queue.Empty:
                break
            try:
                self.store.update(meeting_id, "failed", error={"code": "interrupted", "message": "Сервер был остановлен. Загрузите запись повторно."})
            finally:
                self.jobs.task_done()
        self.worker.join(timeout=10)
        # If inference is finishing, its thread retains the OS lock. Closing a GUI
        # or API server must not release the lock while the previous GPU job runs.
