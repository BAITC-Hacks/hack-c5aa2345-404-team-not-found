"""Run local inference, reporting actual stage transitions to the API."""

from collections.abc import Callable
from pathlib import Path
from .models import ProtocolResult, Utterance
from .stt import transcribe
from .diarize import diarize
from .llm import analyze
from .exporter import export_files

ProgressCallback = Callable[[str, int, str], None]


class MeetingAgent:
    def process(
        self,
        audio_path: Path,
        meeting_id: str,
        output_dir: Path,
        on_progress: ProgressCallback | None = None,
    ) -> ProtocolResult:
        """Report stage milestones; percentages are not estimates of remaining time."""
        def report(stage: str, progress: int, message: str) -> None:
            if on_progress is not None:
                on_progress(stage, progress, message)

        report("transcribe", 10, "Идёт транскрибация записи…")
        segments, warnings = transcribe(audio_path)
        report("diarize", 40, "Диаризация: определяем спикеров…")
        speakers, diarize_warnings = diarize(audio_path)
        warnings += diarize_warnings
        utterances = []
        for segment in segments:
            speaker = "SPEAKER_00" if not speakers else min(
                speakers, key=lambda span: abs(span["start"] - segment.start)
            )["speaker_id"]
            utterances.append(Utterance(speaker, segment.start, segment.end, segment.text))
        report("analyze", 65, "Формируем саммари и извлекаем поручения…")
        tasks, summary, llm_warnings = analyze(
            "\n".join(f"[{line.speaker}] {line.text}" for line in utterances)
        )
        warnings += llm_warnings
        result = ProtocolResult(meeting_id, "completed", summary, tasks, utterances, warnings)
        report("export", 90, "Создаём протоколы PDF и DOCX…")
        export_files(result, output_dir)
        return result

