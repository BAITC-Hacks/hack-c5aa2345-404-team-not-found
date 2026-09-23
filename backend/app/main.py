from contextlib import asynccontextmanager
import os
from pathlib import Path
import shutil
import sys
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api import router
from app.core.config import Settings
from app.pipeline import Pipeline

_dll_handles = []


def prepare_local_runtime(config):
    for name, value in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1", "PYANNOTE_METRICS_ENABLED": "0",
                        "DO_NOT_TRACK": "1"}.items():
        os.environ[name] = value
    # Python 3.8+ needs explicit DLL search directories on Windows (TorchCodec/FFmpeg).
    if hasattr(os, "add_dll_directory") and not _dll_handles:
        directories = [Path(sys.prefix) / "Lib/site-packages/torch/lib"]
        ffmpeg = shutil.which(str(config.ffmpeg))
        if ffmpeg:
            directories.append(Path(ffmpeg).parent)
        for directory in directories:
            if directory.is_dir():
                _dll_handles.append(os.add_dll_directory(str(directory)))

class UploadLimitMiddleware:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers", [])).get(b"content-length")
        try:
            oversized = length is not None and int(length) > self.limit
        except ValueError:
            oversized = True
        detail = {"code": "too_large", "message": "Максимальный размер записи — 250 МБ."}
        if oversized:
            return await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send)
        count = 0

        async def limited_receive():
            nonlocal count
            message = await receive()
            count += len(message.get("body", b""))
            if count > self.limit:
                raise HTTPException(413, detail=detail)
            return message

        return await self.app(scope, limited_receive, send)


def create_app(config=None, pipeline_factory=Pipeline):
    config = config or Settings()

    @asynccontextmanager
    async def lifespan(application):
        prepare_local_runtime(config)
        application.state.pipeline = pipeline_factory(config)
        try:
            yield
        finally:
            application.state.pipeline.close()

    application = FastAPI(title=config.app_name, version="0.2.0", lifespan=lifespan,
                          description="Local meeting API with a single sequential model worker.")
    application.include_router(router)
    application.add_middleware(UploadLimitMiddleware, limit=config.max_upload_bytes + 65536)
    return application


app = create_app()
