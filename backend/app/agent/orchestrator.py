from pathlib import Path
from .models import ProtocolResult, Utterance
from .stt import transcribe
from .diarize import diarize
from .llm import analyze
from .exporter import export_files

class MeetingAgent:
    def process(self, audio_path: Path, meeting_id: str, output_dir: Path) -> ProtocolResult:
        segments, warnings = transcribe(audio_path)
        speakers, diarize_warnings = diarize(audio_path); warnings += diarize_warnings
        utterances = []
        for index, segment in enumerate(segments):
            speaker = "SPEAKER_00" if not speakers else min(speakers, key=lambda s: abs(s["start"] - segment.start))["speaker_id"]
            utterances.append(Utterance(speaker, segment.start, segment.end, segment.text))
        tasks, summary, llm_warnings = analyze("\n".join(f"[{u.speaker}] {u.text}" for u in utterances)); warnings += llm_warnings
        result = ProtocolResult(meeting_id, "completed", summary, tasks, utterances, warnings)
        export_files(result, output_dir)
        return result

