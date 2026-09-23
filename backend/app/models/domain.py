from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    detected_languages: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    text: str
    segments: list[TranscriptSegment]
    detected_languages: list[str]


@dataclass(frozen=True, slots=True)
class DiarizationTurn:
    speaker: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class MeetingTask:
    assignee: str | None
    task: str
    deadline: str | None
    assigned_by: str | None
    source_speaker: str
    source_text: str
