from fastapi import APIRouter, HTTPException

from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        processing_modules={
            "stt": "planned: local faster-whisper",
            "diarization": "planned: local pyannote",
            "analysis": "planned: local LLM through Ollama or llama.cpp",
            "export": "planned: DOCX and PDF",
        }
    )


@router.post("/api/meetings", status_code=501)
def create_meeting_placeholder() -> None:
    raise HTTPException(
        status_code=501,
        detail="Audio processing is not configured in the scaffold stage. No file is stored or sent externally.",
    )
