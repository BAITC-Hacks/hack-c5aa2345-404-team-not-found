"""Local structural QA only. Never print speech content or infer WER/DER without truth."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import soundfile as sf


def check_intervals(segments, duration):
    return all(math.isfinite(item["start"]) and math.isfinite(item["end"])
               and 0 <= item["start"] <= item["end"] <= duration + 0.05 for item in segments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--stt", type=Path, required=True)
    parser.add_argument("--diarization", type=Path)
    args = parser.parse_args()
    audio_info = sf.info(args.audio)
    with args.audio.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stt = json.loads(args.stt.read_text(encoding="utf-8"))
    segments = stt["result"]["segments"]
    checks = {
        "stt_returned_text": bool(stt["result"]["text"].strip()),
        "stt_returned_segments": bool(segments),
        "stt_audio_path_matches": Path(stt["source"]).resolve() == args.audio.resolve(),
        "stt_timestamps_in_recording": check_intervals(segments, audio_info.duration),
        "stt_segments_ordered": all(a["start"] <= b["start"] for a, b in zip(segments, segments[1:])),
    }
    report = {
        "audio_sha256": digest, "audio_seconds": audio_info.duration,
        "stt_seconds": stt["seconds"], "stt_real_time_factor": round(stt["seconds"] / audio_info.duration, 4),
        "stt_segment_count": len(segments), "stt_text_characters": len(stt["result"]["text"]),
        "dominant_language": stt["result"]["detected_languages"],
        "manual_audio_comparison_complete": False, "word_error_rate": None, "diarization_error_rate": None,
        "limitation": "No human reference transcript/speaker timeline supplied. Structural checks are not accuracy measurements.",
    }
    if args.diarization:
        diar = json.loads(args.diarization.read_text(encoding="utf-8"))
        turns = diar["speaker_segments"]
        checks["diarization_returned_turns"] = bool(turns)
        checks["diarization_audio_path_matches"] = Path(diar["source"]).resolve() == args.audio.resolve()
        checks["diarization_timestamps_in_recording"] = check_intervals(turns, audio_info.duration)
        report.update({"diarization_tested": True, "diarization_seconds": diar["seconds"], "speaker_count": len({turn["speaker"] for turn in turns}),
                       "diarization_turn_count": len(turns)})
    else:
        report["diarization_tested"] = False
    report["checks"] = checks
    report["structural_checks_passed"] = all(checks.values())
    root = Path(os.environ.get("HACKALEM_AI_HOME", str(Path(os.environ["LOCALAPPDATA"]) / "HackAlemAI")))
    output = root / "results" / "recording-checks.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))  # Metrics only, no transcript.
    print(f"Saved: {output}")
    if not report["structural_checks_passed"]:
        raise SystemExit(1)
