from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class Segment:
    start: float
    end: float
    text: str
    lang_guess: str = "ru"

@dataclass
class Utterance:
    speaker: str
    start: float
    end: float
    text: str

@dataclass
class Task:
    assignee: str
    deadline: str
    description: str
    source_quote: str
    status: str = "В работе"

@dataclass
class ProtocolResult:
    meeting_id: str
    status: str
    summary: list[str]
    tasks: list[Task]
    transcript: list[Utterance]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "tasks": [asdict(x) for x in self.tasks], "transcript": [asdict(x) for x in self.transcript]}

