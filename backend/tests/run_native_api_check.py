"""Built native ApiClient -> real Uvicorn/FastAPI/SQLite/worker/export.

Only inference, readiness, and FFmpeg normalization are patched. The input is
two seconds of synthetic silence; no user recordings or external APIs are used.
Run: backend/.venv/Scripts/python.exe backend/tests/run_native_api_check.py
"""

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn
from app.core.config import Settings
from app.main import create_app
from app.models.domain import TranscriptResult, TranscriptSegment, DiarizationTurn, MeetingTask
from app.pipeline import Pipeline


def normalize(source, target):
    shutil.copyfile(source, target)
    return 2.0


def main():
    exe = ROOT / "desktop/release/SAMRUK-KAZYNA.exe"
    if not exe.is_file():
        raise SystemExit("Build the native EXE first: desktop/build-native.ps1")
    output = ROOT / "desktop/build/native-real-api-check"
    output.mkdir(parents=True, exist_ok=True)
    csc = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not csc.is_file():
        csc = csc.parent.parent.parent / "Framework/v4.0.30319/csc.exe"
    copied = output / exe.name
    shutil.copy2(exe, copied)
    harness = output / "NativeBackendIntegration.exe"
    references = ["System", "System.Core", "System.Net.Http", "System.Web.Extensions", "System.IO.Compression",
                  "System.IO.Compression.FileSystem", "System.Xml", "System.Windows.Forms", "System.Drawing"]
    subprocess.run([str(csc), "/nologo", "/target:exe", "/langversion:5", "/codepage:65001", "/out:" + str(harness),
                    "/r:" + str(copied), *["/r:" + item + ".dll" for item in references],
                    str(ROOT / "backend/tests/native_api_check.cs")], check=True, cwd=ROOT)
    wav_path = output / "synthetic.wav"
    with wave.open(str(wav_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 32000)
    with tempfile.TemporaryDirectory(prefix="samruk-native-api-") as temporary, ExitStack() as stack:
        stack.enter_context(patch.object(Pipeline, "readiness", return_value={"stt": "ready", "diarization": "ready", "analysis": "ready"}))
        stack.enter_context(patch.object(Pipeline, "normalize", side_effect=normalize))
        stt = stack.enter_context(patch("app.services.stt.local.LocalSTTService.transcribe", return_value=TranscriptResult(
            text="Ертең есеп дайындау. Подготовлю отчёт.",
            segments=[TranscriptSegment(0, .9, "Ертең есеп дайындау.", ["kk"]),
                      TranscriptSegment(1, 1.9, "Подготовлю отчёт.", ["ru"])], detected_languages=["kk", "ru"])))
        diarization = stack.enter_context(patch("app.services.diarization.local.LocalDiarizationService.diarize", return_value=[
            DiarizationTurn("SPEAKER_00", 0, .9), DiarizationTurn("SPEAKER_01", 1, 2)]))
        analysis = stack.enter_context(patch("app.services.llm.local.LocalMeetingAnalysisService.analyze", return_value=(
            "Обсудили отчёт на русском и казахском.", [MeetingTask("Айдос", "Подготовить есеп", "Ертең", None,
            "SPEAKER_00", "Ертең есеп дайындау.")])) )
        app = create_app(Settings(storage_path=Path(temporary)))
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.02)
            if not server.started:
                raise RuntimeError("Real Uvicorn application did not start")
            subprocess.run([str(harness), f"http://127.0.0.1:{port}", str(wav_path), str(output)],
                           check=True, cwd=output, timeout=45)
            stt.assert_called_once()
            diarization.assert_called_once()
            analysis.assert_called_once()
            report = json.loads((output / "native-integration.json").read_text(encoding="utf-8-sig"))
            report["exe_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
            report["model_adapters_each_called_once"] = True
            (output / "native-integration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Report:", output / "native-integration.json")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            listener.close()
            if thread.is_alive():
                raise RuntimeError("Test Uvicorn server did not stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
