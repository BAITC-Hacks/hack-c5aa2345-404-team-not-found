"""Deterministic worker helper checks: no models, network, downloads or real audio."""
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from app.core.config import Settings
from app.models.domain import DiarizationTurn, TranscriptSegment
from app.pipeline import Pipeline, ProcessingError, UNRESOLVED, atomic_json, exact_unique_tasks, merge_segments, transcript_chunks


class AlignmentTest(unittest.TestCase):
    def test_unambiguous_speaker_preserves_text_and_languages(self):
        segment = TranscriptSegment(0, 2, "Ертең API дайын.", ["kk", "en"])
        result = merge_segments([segment], [DiarizationTurn("SPEAKER_1", 0, 3)])
        self.assertEqual(result, [{"speaker": "SPEAKER_1", "start": 0., "end": 2., "text": segment.text, "detected_languages": ["kk", "en"]}])

    def test_cross_speaker_segment_is_unresolved_even_with_majority(self):
        segment = TranscriptSegment(0, 10, "Two voices.")
        result = merge_segments([segment], [DiarizationTurn("A", 0, 8), DiarizationTurn("B", 8, 10)])
        self.assertEqual(result[0]["speaker"], UNRESOLVED)
        self.assertEqual(result[0]["text"], segment.text)

    def test_missing_and_insufficient_coverage_are_unresolved(self):
        segment = TranscriptSegment(0, 10, "Speech")
        self.assertEqual(merge_segments([segment], [])[0]["speaker"], UNRESOLVED)
        self.assertEqual(merge_segments([segment], [DiarizationTurn("A", 0, 1)])[0]["speaker"], UNRESOLVED)

    def test_duplicated_turns_do_not_inflate_coverage(self):
        segment = TranscriptSegment(0, 10, "Speech")
        result = merge_segments([segment], [DiarizationTurn("A", 0, 2)] * 5)
        self.assertEqual(result[0]["speaker"], UNRESOLVED)

    def test_overlapping_turns_for_same_voice_are_merged(self):
        result = merge_segments([TranscriptSegment(0, 4, "Speech")],
                                [DiarizationTurn("A", 0, 2), DiarizationTurn("A", 1, 3)])
        self.assertEqual(result[0]["speaker"], "A")

    def test_invalid_intervals_rejected(self):
        with self.assertRaises(ValueError):
            merge_segments([TranscriptSegment(1, 0, "Speech")], [])
        with self.assertRaises(ValueError):
            merge_segments([], [DiarizationTurn("A", 0, float("nan"))])

    def test_newline_cannot_introduce_fake_speaker_and_evidence_matches(self):
        result = merge_segments([TranscriptSegment(0, 1, "Текст\nOTHER: ложная метка")], [DiarizationTurn("A", 0, 1)])
        chunk = transcript_chunks(result)[0]
        self.assertNotIn("\nOTHER:", chunk)
        self.assertEqual(chunk, "A: " + result[0]["text"])


class ChunkTest(unittest.TestCase):
    def test_whole_turns_are_preserved_exactly_without_truncation(self):
        turns = [{"speaker": "A", "text": "Привет " + str(i)} for i in range(8)]
        chunks = transcript_chunks(turns, limit=30)
        self.assertTrue(all(len(chunk) <= 30 for chunk in chunks))
        self.assertEqual("\n".join(chunks), "\n".join("A: " + item["text"] for item in turns))
        self.assertGreater(len(chunks), 1)

    def test_single_long_turn_fails_instead_of_cutting(self):
        with self.assertRaises(ProcessingError) as context:
            transcript_chunks([{"speaker": "A", "text": "x" * 4501}])
        self.assertEqual(context.exception.code, "transcript_too_long")

    def test_dedupe_is_exact_and_keeps_distinct_sources(self):
        task = dict(assignee=None, task="Проверить", deadline=None, assigned_by=None, source_speaker="A", source_text="Проверить.")
        different = dict(task, source_speaker="B")
        self.assertEqual(exact_unique_tasks([task, dict(task), different]), [task, different])


class RuntimeSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_one_pipeline_owner_per_storage(self):
        config = Settings(storage_path=self.root)
        first = Pipeline(config)
        try:
            with self.assertRaises(RuntimeError):
                Pipeline(config)
        finally:
            first.close()
        second = Pipeline(config)
        second.close()

    def test_atomic_json_unicode_and_no_partial_files(self):
        path = self.root / "result.json"
        atomic_json(path, {"text": "Қазақша"})
        self.assertIn("Қазақша", path.read_text(encoding="utf-8"))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            atomic_json(path, {"bad": float("nan")})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".result-*.tmp")), [])

    def pipeline_for_normalization(self):
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.config = replace(Settings(), max_duration_seconds=2)
        return pipeline

    def write_wave(self, path, seconds):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 16000 * seconds)

    def test_normalization_restricts_protocol_and_formats(self):
        pipeline = self.pipeline_for_normalization()
        target = self.root / "normalized.wav"
        def convert(command, **kwargs):
            self.write_wave(Path(command[-1]), 1)
            self.assertEqual(command[command.index("-protocol_whitelist") + 1], "file")
            self.assertEqual(command[command.index("-format_whitelist") + 1], "wav,mp3,mov")
            self.assertEqual(kwargs["timeout"], 300)
        with patch.object(pipeline, "_ffmpeg_path", return_value="ffmpeg"), patch("app.pipeline.subprocess.run", side_effect=convert):
            self.assertEqual(pipeline.normalize(self.root / "input.mp3", target), 1.0)

    def test_long_audio_is_rejected_not_silently_shortened(self):
        pipeline = self.pipeline_for_normalization()
        target = self.root / "normalized.wav"
        with patch.object(pipeline, "_ffmpeg_path", return_value="ffmpeg"), patch("app.pipeline.subprocess.run", side_effect=lambda *a, **kw: self.write_wave(target, 3)):
            with self.assertRaises(ProcessingError) as context:
                pipeline.normalize(self.root / "input.mp3", target)
        self.assertEqual(context.exception.code, "audio_too_long")

    def test_decoder_failure_does_not_expose_paths(self):
        pipeline = self.pipeline_for_normalization()
        with patch.object(pipeline, "_ffmpeg_path", return_value="ffmpeg"), patch("app.pipeline.subprocess.run", side_effect=subprocess.CalledProcessError(1, "C:/PRIVATE_SECRET")):
            with self.assertRaises(ProcessingError) as context:
                pipeline.normalize(self.root / "input.mp3", self.root / "normalized.wav")
        self.assertNotIn("PRIVATE_SECRET", context.exception.safe_message)


if __name__ == "__main__":
    unittest.main()
