from fastapi import FastAPI

from app.api import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0-scaffold",
    description="Privacy-first, on-premise meeting-protocol service scaffold.",
)
app.include_router(router)
