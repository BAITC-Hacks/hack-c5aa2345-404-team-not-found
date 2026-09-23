"""Real HTTP routes, SQLite, worker and exports; only models/FFmpeg are synthetic."""
import io
import json
import tempfile
import time
import unittest
import wave
import zipfile
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.models.domain import TranscriptResult, TranscriptSegment, DiarizationTurn, MeetingTask
from app.pipeline import Pipeline
from app.storage import Store


def audio_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 32000)
    return buffer.getvalue()


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Settings(storage_path=Path(self.temp.name))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(Pipeline, "readiness", return_value={"stt": "ready", "analysis": "ready"}))
        self.stack.enter_context(patch.object(Pipeline, "normalize", side_effect=self.normalize))
        self.stt = self.stack.enter_context(patch("app.services.stt.local.LocalSTTService.transcribe", return_value=TranscriptResult(
            text="Ертең есеп дайындау.", segments=[TranscriptSegment(0, 1, "Ертең есеп дайындау.", ["kk"])], detected_languages=["kk"])))
        self.stack.enter_context(patch("app.services.diarization.local.LocalDiarizationService.diarize", return_value=[DiarizationTurn("SPEAKER_00", 0, 2)]))
        self.stack.enter_context(patch("app.services.llm.local.LocalMeetingAnalysisService.analyze", return_value=("Обсудили отчёт.", [
            MeetingTask(None, "Дайындау <есеп> & проверить", "Ертең", None, "SPEAKER_00", "Ертең есеп дайындау.")])) )
        self.client = self.stack.enter_context(TestClient(create_app(self.config)))

    @staticmethod
    def normalize(source, target):
        target.write_bytes(source.read_bytes())
        return 2.0

    def upload(self, **kwargs):
        return self.client.post("/api/meetings", files={"file": ("synthetic.wav", audio_bytes(), "audio/wav")}, data={"title": "Тест Қазақша"}, **kwargs)

    def completed(self, meeting_id):
        for _ in range(250):
            value = self.client.get("/api/meetings/" + meeting_id).json()
            if value["status"] in ("completed", "failed"):
                return value
            time.sleep(.02)
        self.fail("Worker did not finish")

    def test_full_api_worker_and_both_exports(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        response = self.upload()
        self.assertEqual(response.status_code, 202, response.text)
        item = response.json()
        self.assertEqual(item["status"], "queued")
        self.assertEqual(response.headers["location"], "/api/meetings/" + item["id"])
        self.assertEqual(self.completed(item["id"])["status"], "completed")
        result = self.client.get(response.headers["location"] + "/result").json()
        self.assertEqual(result["meeting_id"], item["id"])
        self.assertEqual(result["transcript"][0]["text"], "Ертең есеп дайындау.")
        self.assertIsNone(result["tasks"][0]["assigned_by"])
        self.assertEqual(len(self.client.get("/api/meetings").json()["items"]), 1)
        for kind in ("docx", "pdf"):
            exported = self.client.get(response.headers["location"] + "/export?format=" + kind)
            self.assertEqual(exported.status_code, 200)
            self.assertIn("attachment", exported.headers["content-disposition"])
            self.assertTrue(exported.content.startswith(b"PK" if kind == "docx" else b"%PDF"))
            if kind == "docx":
                with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                    xml = archive.read("word/document.xml").decode()
                    self.assertIn("Ертең", xml)
                    self.assertIn("&lt;есеп&gt;", xml)
        persisted = Store(self.config.storage_path).get(item["id"])
        self.assertEqual(persisted["status"], "completed")

    def test_input_validation_and_no_orphan_files(self):
        for filename, content in (("bad.exe", b"RIFF0000WAVE"), ("fake.wav", b"not audio"), ("empty.mp3", b"")):
            response = self.client.post("/api/meetings", files={"file": (filename, content)})
            self.assertEqual(response.status_code, 415)
        self.assertEqual(self.client.post("/api/meetings").status_code, 422)
        self.assertEqual(self.client.get("/api/meetings/unknown").status_code, 404)
        self.assertEqual(self.client.get("/api/meetings/unknown/export?format=exe").status_code, 422)
        self.assertFalse(any(path.is_dir() for path in self.config.storage_path.iterdir()))

    def test_unavailable_models_do_not_accept_upload_or_demo(self):
        with patch.object(Pipeline, "readiness", return_value={"stt": "missing"}):
            self.assertEqual(self.client.get("/health").json()["status"], "not_ready")
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self.client.get("/api/meetings").json(), {"items": []})

    def test_model_failure_is_safe_and_not_completed(self):
        self.stt.side_effect = RuntimeError("private transcript C:/secret/token")
        item = self.upload().json()
        result = self.completed(item["id"])
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["stage"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(self.client.get("/api/meetings/" + item["id"] + "/result").status_code, 409)

    def test_size_limit_and_recovery(self):
        self.client.app.state.pipeline.config = replace(self.config, max_upload_bytes=10)
        self.assertEqual(self.upload().status_code, 413)
        store = self.client.app.state.pipeline.store
        store.create("interrupted-test", "Pending")
        store.recover()
        self.assertEqual(store.get("interrupted-test")["error"]["code"], "interrupted")

    def test_request_limit_before_multipart_parsing(self):
        response = self.client.post("/api/meetings", content=b"x", headers={"Content-Length": str(self.config.max_upload_bytes + 65537)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"]["code"], "too_large")

    def test_pending_result_is_409(self):
        store = self.client.app.state.pipeline.store
        store.create("queued-check", "Pending")
        self.assertEqual(self.client.get("/api/meetings/queued-check/result").status_code, 409)
        self.assertEqual(self.client.get("/api/meetings/queued-check/export?format=pdf").status_code, 409)


if __name__ == "__main__":
    unittest.main()
