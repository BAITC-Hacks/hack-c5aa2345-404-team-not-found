"""Synthetic-only evaluation checks; no models, real recordings, PDF or Ollama."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import types
import unittest
import wave
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/local-ai/evaluate-meeting.py"


class EvaluationTest(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path(str(SCRIPT))
        self.state = self.module["main"].__globals__
        self.temp = tempfile.TemporaryDirectory(prefix="local-ai-evaluation-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.audio = self.root / "synthetic.wav"
        self.pdf = self.root / "synthetic.pdf"
        # Bytes for manifest tests only; not passed to decoders.
        self.audio.write_bytes(b"synthetic-audio")
        self.pdf.write_bytes(b"synthetic-document")
        self.out = self.root / "private-results"

    def prepare(self, stage="compare"):
        args = argparse.Namespace(stage=stage, audio=self.audio, reference=self.pdf,
                                  output_dir=self.out, ffmpeg="ffmpeg")
        self.module["prepare_run"](args)

    def write(self, name, value):
        (self.out / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_import_does_not_initialize_run(self):
        self.assertIsNone(self.module["OUT"])
        self.assertIsNone(self.module["CONFIG"])

    def test_unicode_normalization(self):
        self.assertEqual(self.module["tokens"]("Ёж, ҚАЗАҚША! １２"), ["еж", "қазақша", "12"])

    def test_edit_counts_and_empty_sequences(self):
        align = self.module["align"]
        counts, operations = align(["a", "b", "c"], ["a", "x", "c", "d"])
        self.assertEqual(counts, {"equal": 2, "substitute": 1, "delete": 0, "insert": 1})
        self.assertEqual(len(operations), 4)
        self.assertEqual(align([], ["a"])[0]["insert"], 1)
        self.assertEqual(align(["a"], [])[0]["delete"], 1)
        self.assertEqual(sum(align([], [])[0].values()), 0)

    def test_alignment_limit(self):
        with patch.dict(self.state, {"MAX_ALIGNMENT_CELLS": 4}):
            with self.assertRaises(ValueError):
                self.module["align"](["a", "b"], ["a", "b"])

    def test_rejects_git_directory_and_worktree_file(self):
        for name, directory in (("repo", True), ("worktree", False)):
            repo = self.root / name
            repo.mkdir()
            marker = repo / ".git"
            if directory:
                marker.mkdir()
            else:
                marker.write_text("gitdir: somewhere", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.module["outside_git"](repo / "ignored" / "results")
        with self.assertRaises(ValueError):
            self.module["outside_git"](SCRIPT.parent / "results")

    def test_manifest_binds_both_inputs(self):
        self.prepare()
        self.prepare("speech")
        self.pdf.write_bytes(b"changed-document")
        with self.assertRaises(ValueError):
            self.prepare("extract")

    def test_existing_outputs_and_unmanaged_directory_preserved(self):
        self.out.mkdir()
        existing = self.out / "keep.txt"
        existing.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
        self.out = self.root / "another-run"
        self.prepare()
        self.write("comparison-metrics.json", {"keep": True})
        with self.assertRaises(FileExistsError):
            self.prepare()
        with self.assertRaises(FileExistsError):
            self.module["write"]("comparison-metrics.json", {})

    def test_comparison_is_not_accuracy_and_html_escapes(self):
        self.prepare()
        (self.out / "reference.txt").write_text("Протокол. <script>alert(1)</script>", encoding="utf-8")
        (self.out / "recognized.txt").write_text("Протокол.", encoding="utf-8")
        self.write("reference-metadata.json", {"structure_indicators": {
            "protocol_heading": 1, "agenda_heading": 1, "decisions_heading": 0,
            "participants_heading": 0}})
        with contextlib.redirect_stdout(io.StringIO()):
            self.module["compare"]()
        metrics = json.loads((self.out / "comparison-metrics.json").read_text(encoding="utf-8"))
        self.assertIsNone(metrics["recognition_accuracy_claim"])
        self.assertFalse(metrics["verified_as_verbatim_reference"])
        page = (self.out / "text-differences.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Content-Security-Policy", page)

    def test_speaker_overlap_and_ambiguity(self):
        self.prepare("analyze")
        self.write("full-stt.json", {"source": str(self.audio), "result": {"segments": [
            {"start": 0, "end": 2, "text": "synthetic"},
            {"start": 2, "end": 4, "text": "synthetic"}]}})
        self.write("full-diarization.json", {"source": str(self.audio), "speaker_segments": [
            {"speaker": "S0", "start": 0, "end": 3},
            {"speaker": "S1", "start": 3, "end": 4}]})
        result = self.module["label_segments"]()
        self.assertEqual(result[0]["speaker"], "S0")
        self.assertTrue(result[1]["speaker_assignment_uncertain"])
        self.assertTrue(result[1]["speaker"].startswith("UNRESOLVED_"))

    def test_invalid_intervals_rejected(self):
        validate = self.module["validate_intervals"]
        for start, end in ((-1, 1), (2, 1), (0, float("nan")), (0, float("inf"))):
            with self.assertRaises(ValueError):
                validate([{"start": start, "end": end}])

    def test_pdf_extraction_uses_layout_without_printing_content(self):
        self.prepare("extract")
        calls = []

        def extract_text(**kwargs):
            calls.append(kwargs)
            return "Протокол. Повестка. Синтетический пример."

        reader = types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=extract_text)])
        with patch.dict("sys.modules", {"pypdf": types.SimpleNamespace(PdfReader=lambda path: reader)}):
            with contextlib.redirect_stdout(io.StringIO()) as console:
                self.module["extract"]()
        self.assertEqual(calls, [{"extraction_mode": "layout"}])
        self.assertNotIn("Синтетический пример", console.getvalue())

    def test_normalization_uses_local_input_and_preserves_original(self):
        self.prepare("normalize")
        commands = []

        def ffmpeg(command, **kwargs):
            commands.append(command)
            with wave.open(command[-1], "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\0\0" * 160)
            return types.SimpleNamespace(returncode=0)

        with patch.object(self.module["subprocess"], "run", side_effect=ffmpeg):
            self.module["normalize"]()
        self.assertIn("-n", commands[0])
        self.assertIn("file,pipe", commands[0])
        self.assertEqual(self.audio.read_bytes(), b"synthetic-audio")
        metadata = json.loads((self.out / "normalization.json").read_text())
        self.assertEqual(metadata["duration_seconds"], 0.01)

    def test_analysis_failure_is_nonzero_not_a_successful_report(self):
        self.prepare("analyze")
        class FailingService:
            def __init__(self, **kwargs):
                pass

            def analyze(self, text):
                raise ValueError("synthetic-private-text")

        with patch.dict(self.state, {"setup": lambda: {}, "label_segments": lambda: []}):
            with patch("app.services.llm.local.LocalMeetingAnalysisService", FailingService):
                with self.assertRaises(RuntimeError):
                    self.module["analyze"]()
        result = json.loads((self.out / "ollama-analysis.json").read_text())
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValueError")

    def test_cli_nonzero_and_private_exception_log(self):
        def fail():
            raise RuntimeError("synthetic-private-content")

        console = io.StringIO()
        with patch.dict(self.state, {"compare": fail}), contextlib.redirect_stdout(console):
            code = self.module["main"](["compare", "--audio", str(self.audio),
                "--reference", str(self.pdf), "--output-dir", str(self.out)])
        self.assertEqual(code, 1)
        self.assertNotIn("synthetic-private-content", console.getvalue())
        self.assertIn("synthetic-private-content", (self.out / "compare.log").read_text(encoding="utf-8"))
        self.assertFalse(json.loads((self.out / "compare-run.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
