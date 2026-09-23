"""Offline contract checks; real model checks are separate and explicitly invoked."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx

from app.core.errors import FeatureNotConfiguredError
from app.services.stt.local import LocalSTTService
from app.services.diarization.local import LocalDiarizationService
from app.services.llm.local import LocalMeetingAnalysisService


class AdaptersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / "fixture.wav"
        self.audio.touch()  # Adapters below use mocked decoders, not a real audio fixture.

    def test_import_and_construction_do_not_load_ml_or_connect(self):
        code = """
import socket, sys
def fail(*args, **kwargs): raise AssertionError('Network call during import/construction')
socket.socket.connect = fail
from app.services.stt.local import LocalSTTService
from app.services.diarization.local import LocalDiarizationService
from app.services.llm.local import LocalMeetingAnalysisService
LocalSTTService('missing'); LocalDiarizationService('missing'); LocalMeetingAnalysisService()
assert not any(name in sys.modules for name in ['torch', 'faster_whisper', 'pyannote.audio', 'httpx'])
"""
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_missing_weights_fail_without_download(self):
        for service in [LocalSTTService(self.root), LocalDiarizationService(self.root)]:
            with self.assertRaises(FeatureNotConfiguredError):
                (service.transcribe if isinstance(service, LocalSTTService) else service.diarize)(self.audio)

    def test_stt_preserves_text_and_consumes_lazy_segments(self):
        (self.root / "model.bin").touch()
        model = Mock()
        model.transcribe.return_value = (iter([
            SimpleNamespace(start=0.2, end=2.0, text="  Ертең API дайын болады.  "),
            SimpleNamespace(start=2.2, end=4.1, text=" Проверим загрузку. "),
        ]), SimpleNamespace(language="kk"))
        factory = Mock(return_value=model)
        with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=factory)}):
            service = LocalSTTService(self.root)
            result = service.transcribe(self.audio)
        self.assertEqual(result.text, "Ертең API дайын болады. Проверим загрузку.")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0].detected_languages, [])
        self.assertEqual(result.detected_languages, ["kk"])
        self.assertTrue(factory.call_args.kwargs["local_files_only"])
        self.assertTrue(model.transcribe.call_args.kwargs["multilingual"])
        self.assertEqual(model.transcribe.call_args.kwargs["task"], "transcribe")
        self.assertIsNone(service._model)

    def test_stt_does_not_mask_decoder_errors(self):
        service = LocalSTTService(self.root)
        with patch.object(service, "_load", side_effect=RuntimeError("decoder failure")):
            with self.assertRaisesRegex(RuntimeError, "decoder failure"):
                service.transcribe(self.audio)

    def test_stt_rejects_invalid_timestamps(self):
        model = Mock()
        model.transcribe.return_value = ([SimpleNamespace(start=3, end=2, text="test")], SimpleNamespace(language="ru"))
        service = LocalSTTService(self.root)
        with patch.object(service, "_load", return_value=model):
            with self.assertRaises(ValueError): service.transcribe(self.audio)

    def test_diarization_uses_4x_result_and_preserves_anonymous_ids(self):
        standard = Mock()
        standard.itertracks.return_value = [(SimpleNamespace(start=1.5, end=3.0), None, "SPEAKER_01")]
        exclusive = Mock()
        exclusive.itertracks.return_value = [(SimpleNamespace(start=0.0, end=1.0), None, "SPEAKER_00")]
        pipeline = Mock(return_value=SimpleNamespace(speaker_diarization=standard, exclusive_speaker_diarization=exclusive))
        for flag, expected in [(False, "SPEAKER_01"), (True, "SPEAKER_00")]:
            service = LocalDiarizationService(self.root, exclusive=flag, num_speakers=2)
            with patch.object(service, "_load", return_value=pipeline):
                turns = service.diarize(self.audio)
            self.assertEqual(turns[0].speaker, expected)
            self.assertEqual(pipeline.call_args.kwargs, {"num_speakers": 2})

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError): LocalSTTService(self.root, device="cpu")
        with self.assertRaises(ValueError): LocalDiarizationService(self.root, min_speakers=3, max_speakers=2)
        with self.assertRaises(ValueError): LocalDiarizationService(self.root, num_speakers=2, min_speakers=1)
        with self.assertRaises(ValueError): LocalDiarizationService(self.root, num_speakers=1.5)
        for url in ["https://example.com", "http://192.168.1.1:11434", "http://user:pass@localhost:11434", "http://localhost/api"]:
            with self.assertRaises(ValueError): LocalMeetingAnalysisService(base_url=url)
        with self.assertRaises(ValueError): LocalMeetingAnalysisService(model="qwen3:cloud")

    def run_llm(self, answers, transcript="SPEAKER_00: Проверить PDF завтра.", metadata=None, retries=0):
        real_client = httpx.Client
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.path == "/api/show":
                return httpx.Response(200, json=metadata or {})
            item = answers.pop(0)
            if isinstance(item, Exception): raise item
            return httpx.Response(200, json={"done": True, "message": {"content": item}})

        def factory(**kwargs):
            self.assertFalse(kwargs["trust_env"])
            self.assertFalse(kwargs["follow_redirects"])
            return real_client(**kwargs, transport=httpx.MockTransport(handler))

        with patch("httpx.Client", side_effect=factory):
            result = LocalMeetingAnalysisService(retries=retries).analyze(transcript)
        return result, calls

    def response(self, **changes):
        task = dict(assignee=None, task="Проверить PDF", deadline="завтра", assigned_by=None,
                    source_speaker="SPEAKER_00", source_text="Проверить PDF завтра.")
        task.update(changes)
        return json.dumps({"summary": "Обсудили проверку PDF.", "tasks": [task]}, ensure_ascii=False)

    def test_llm_keeps_null_and_relative_deadline(self):
        (summary, tasks), calls = self.run_llm([self.response()])
        self.assertTrue(summary)
        self.assertIsNone(tasks[0].assignee)
        self.assertIsNone(tasks[0].assigned_by)
        self.assertEqual(tasks[0].deadline, "завтра")
        self.assertEqual([call.url.path for call in calls], ["/api/show", "/api/chat"])
        payload = json.loads(calls[-1].content)
        self.assertEqual(payload["keep_alive"], 0)
        self.assertFalse(payload["think"])

    def test_llm_retries_invalid_json_once(self):
        (_, tasks), calls = self.run_llm(["not json", self.response()], retries=1)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(calls), 3)

    def test_llm_rejects_wrong_speaker_quote_or_invented_name(self):
        for overrides in [dict(source_speaker="SPEAKER_99"), dict(source_text="Несуществующая цитата"), dict(assignee="ВыдуманноеИмя")]:
            with self.assertRaisesRegex(RuntimeError, "JSON/source validation"):
                self.run_llm([self.response(**overrides)])

    def test_llm_rejects_cloud_metadata_before_sending_transcript(self):
        with self.assertRaises(FeatureNotConfiguredError):
            self.run_llm([], metadata={"remote_host": "https://ollama.com"})

    def test_llm_rejects_invented_calendar_deadline(self):
        with self.assertRaisesRegex(RuntimeError, "JSON/source validation"):
            self.run_llm([self.response(deadline="2026-09-24")])

    def test_llm_does_not_turn_network_failure_into_demo(self):
        with self.assertRaisesRegex(RuntimeError, "Ollama is unavailable"):
            self.run_llm([httpx.ConnectError("connection refused")])

    def test_empty_and_unlabeled_transcript_handling(self):
        service = LocalMeetingAnalysisService()
        self.assertEqual(service.analyze("   "), ("", []))
        with self.assertRaises(ValueError): service.analyze("текст без говорящего")
        with self.assertRaises(ValueError): service.analyze("SPEAKER_00: " + "a" * 6001)


if __name__ == "__main__":
    unittest.main()
