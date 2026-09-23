"""Exercise the built native EXE assembly without opening GUI or editing preferences."""
from __future__ import annotations

import copy
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "desktop/build/native-tests"
EXE = ROOT / "desktop/release/SAMRUK-KAZYNA.exe"
OUT.mkdir(parents=True, exist_ok=True)
DEMO = json.loads((ROOT / "samples/api/meeting-completed.json").read_text(encoding="utf-8-sig"))
STATS = {"uploads": 0, "redirect_uploads": 0, "trap_requests": 0, "multipart_checks": [], "requests": []}
LOCK = threading.Lock()


def meeting(identifier="example-meeting-001", title="Тестовое совещание", status="completed"):
    return {"id": identifier, "title": title, "created_at": "2026-09-23T10:00:00Z", "status": status, "stage": None, "error": None}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def reply(self, data, status=200, content_type="application/json", headers=None):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def track(self):
        with LOCK:
            STATS["requests"].append({"method": self.command, "path": self.path})

    def do_GET(self):
        self.track()
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/trap":
            with LOCK:
                STATS["trap_requests"] += 1
            return self.reply({"unexpected": True})
        if path == "/health":
            return self.reply({"status": "fixture", "local_only": True, "processing_modules": []})
        if path == "/api/meetings":
            return self.reply({"items": [meeting()]})
        identifier = path.split("/")[3] if path.startswith("/api/meetings/") else ""
        if path.endswith("/result"):
            result = copy.deepcopy(DEMO)
            result["meeting_id"] = identifier
            if identifier == "invalid-segment":
                result["transcript"][0]["end"] = -1
            if identifier == "nonlocal":
                result["local_only"] = False
            return self.reply(result)
        if path.endswith("/export"):
            if identifier == "invalid-export":
                return self.reply(b"<html>Server error</html>", content_type="text/html")
            export_format = parse_qs(parsed.query).get("format", [""])[0]
            if export_format == "docx":
                return self.reply((OUT / "native-demo.docx").read_bytes(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            if export_format == "pdf":
                return self.reply(b"%PDF-1.4\n% Synthetic transport fixture only; no renderer check.\n%%EOF\n", content_type="application/pdf")
            return self.reply({"detail": "format missing"}, 422)
        if identifier == "scaffold":
            return self.reply({"detail": "Processing is not implemented"}, 501)
        if identifier == "validation":
            return self.reply({"detail": [{"loc": ["body", "file"], "msg": "Field required", "input": "SECRET_FIXTURE_INPUT"}]}, 422)
        if identifier == "invalid-json":
            return self.reply(b"{this is not valid JSON")
        if identifier == "wrong-id":
            return self.reply(meeting("different-id"))
        if identifier == "oversize":
            self.send_response(200)
            self.send_header("Content-Length", str(33 * 1024 * 1024))
            self.send_header("Connection", "close")
            self.end_headers()
            return
        if identifier == "slow":
            self.send_response(200)
            self.send_header("Content-Length", "10000")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"{")
            self.wfile.flush()
            time.sleep(5)
            return
        if identifier == "example-meeting-001":
            return self.reply(meeting())
        return self.reply({"detail": {"code": "not_found", "message": "Not found"}}, 404)

    def do_POST(self):
        self.track()
        if self.path == "/trap":
            with LOCK:
                STATS["trap_requests"] += 1
            return self.reply({"unexpected": True})
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
        parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
        title = parts["title"].get_content() if "title" in parts else ""
        file = parts.get("file")
        check = {
            "file_field": file is not None,
            "no_legacy_audio_field": "audio" not in parts,
            "filename": file.get_filename() == "sample.wav" if file else False,
            "bytes": file.get_payload(decode=True) == b"RIFF_SYNTHETIC_UPLOAD_FIXTURE_NO_SPEECH" if file else False,
            "title_utf8": title in {"Сынақ қазақша", "REDIRECT_FIXTURE"},
        }
        with LOCK:
            STATS["multipart_checks"].append(check)
        if not all(check.values()):
            return self.reply({"detail": {"code": "bad_multipart", "message": "Multipart contract mismatch"}}, 422)
        if title == "REDIRECT_FIXTURE":
            with LOCK:
                STATS["redirect_uploads"] += 1
            return self.reply(b"", 307, headers={"Location": "/trap"})
        with LOCK:
            STATS["uploads"] += 1
        return self.reply(meeting("upload-001", title, "queued"), 202)


def main():
    if not EXE.is_file():
        raise SystemExit("Build desktop/release/SAMRUK-KAZYNA.exe first")
    csc = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    harness = OUT / "NativeChecks.exe"
    copied = OUT / EXE.name
    shutil.copy2(EXE, copied)
    args = [str(csc), "/nologo", "/target:exe", "/langversion:5", "/platform:x64", "/codepage:65001", "/out:" + str(harness)]
    args += ["/r:" + str(copied)]
    args += ["/r:" + name + ".dll" for name in ["System.Net.Http", "System.Web.Extensions", "System.IO.Compression", "System.IO.Compression.FileSystem", "System.Xml", "System.Drawing", "System.Windows.Forms"]]
    args += [str(ROOT / "desktop/tests/native_checks.cs")]
    subprocess.run(args, cwd=ROOT, check=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        completed = subprocess.run([str(harness), "http://127.0.0.1:" + str(server.server_port), str(OUT)], cwd=ROOT, timeout=60)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    (OUT / "fixture.json").write_text(json.dumps(STATS, ensure_ascii=False, indent=2), encoding="utf-8")
    assert STATS["uploads"] == 1, STATS
    assert STATS["redirect_uploads"] == 1, STATS
    assert STATS["trap_requests"] == 0, "Redirect was followed"
    assert all(all(item.values()) for item in STATS["multipart_checks"]), STATS
    print("Fixture: one normal upload, one rejected redirect, no retry or redirect destination request.")
    print("Reports:", OUT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
