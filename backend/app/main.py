import json
import uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .agent.orchestrator import MeetingAgent

ROOT = Path(__file__).resolve().parent.parent; DATA = ROOT / "data" / "meetings"; DATA.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Meeting Protocol API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
agent = MeetingAgent()

@app.get("/health")
def health(): return {"status": "ok", "local_only": True}

@app.post("/api/meetings", status_code=202)
async def create_meeting(audio: UploadFile = File(...)):
    if not audio.filename: raise HTTPException(400, "Файл не выбран")
    meeting_id = uuid.uuid4().hex; folder = DATA / meeting_id; folder.mkdir()
    suffix = Path(audio.filename).suffix.lower() or ".audio"
    audio_path = folder / f"input{suffix}"; audio_path.write_bytes(await audio.read())
    try:
        result = agent.process(audio_path, meeting_id, folder); (folder / "result.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc: raise HTTPException(500, f"Ошибка обработки: {exc}")
    return {"meeting_id": meeting_id, "status": result.status, "result_url": f"/api/meetings/{meeting_id}", "warnings": result.warnings}

@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    path = DATA / meeting_id / "result.json"
    if not path.exists(): raise HTTPException(404, "Совещание не найдено")
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/api/meetings/{meeting_id}/download/{kind}")
def download(meeting_id: str, kind: str):
    if kind not in {"docx", "pdf"}: raise HTTPException(400, "kind должен быть docx или pdf")
    path = DATA / meeting_id / f"protocol.{kind}"
    if not path.exists(): raise HTTPException(404, "Файл ещё не готов")
    return FileResponse(path, filename=f"protocol-{meeting_id}.{kind}")

