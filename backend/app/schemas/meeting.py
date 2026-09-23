from pydantic import BaseModel, Field


class TranscriptSegmentSchema(BaseModel):
    speaker: str = Field(examples=["Speaker 1"])
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    detected_languages: list[str] = Field(default_factory=list, examples=[["kk", "ru"]])


class MeetingTaskSchema(BaseModel):
    assignee: str | None = None
    task: str
    deadline: str | None = None
    assigned_by: str | None = None
    source_speaker: str
    source_text: str


class MeetingAnalysisResponse(BaseModel):
    summary: str
    tasks: list[MeetingTaskSchema] = Field(default_factory=list)
    transcript: list[TranscriptSegmentSchema] = Field(default_factory=list)
    processing_state: str = "planned"
    local_only: bool = True


class HealthResponse(BaseModel):
    status: str = "scaffold"
    local_only: bool = True
    processing_modules: dict[str, str]
