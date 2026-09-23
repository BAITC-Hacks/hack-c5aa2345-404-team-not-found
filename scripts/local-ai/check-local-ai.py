"""Installation checks only; no backend or UI. Results stay outside Git."""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

ROOT = Path(os.environ.get("HACKALEM_AI_HOME", Path(os.environ["LOCALAPPDATA"]) / "HackAlemAI"))
os.environ["HF_HOME"] = str(ROOT / "huggingface")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
os.environ["DO_NOT_TRACK"] = "1"
os.environ["OLLAMA_NO_CLOUD"] = "1"
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
MODELS = {
    "whisper": ("Systran/faster-whisper-large-v3", ROOT / "models/faster-whisper-large-v3"),
    "pyannote": ("pyannote/speaker-diarization-community-1", ROOT / "models/speaker-diarization-community-1"),
}
_dll_handles = []
for folder in [Path(sys.prefix) / "Lib/site-packages/torch/lib", ROOT / "tools/ffmpeg-n8.1-latest-win64-gpl-shared-8.1/bin"]:
    if folder.is_dir():
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ["PATH"]
        if hasattr(os, "add_dll_directory"):
            _dll_handles.append(os.add_dll_directory(str(folder)))


def save(name, value):
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value[key] for key in ("passed", "checks", "seconds", "device", "load_seconds", "speech_quality_tested") if key in value}, ensure_ascii=False, indent=2), flush=True)
    print(f"Saved: {path}", flush=True)


def local_network_only():
    """Fail if a Python dependency attempts an external connection during checks."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def guard(address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError("External network access blocked during local checks")

    def connect(sock, address):
        guard(address)
        return original(sock, address)

    def connect_ex(sock, address):
        guard(address)
        return original_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def download(kind, revision=None):
    from huggingface_hub import HfApi, get_token, snapshot_download
    repo, path = MODELS[kind]
    if kind == "pyannote" and not get_token():
        raise SystemExit("Run scripts/local-ai/hf-login.py locally first; never paste tokens into chat.")
    revision = HfApi().model_info(repo, revision=revision or {
        "whisper": "edaa852ec7e145841d8ffdb056a99866b5f0a478",
        "pyannote": "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
    }[kind]).sha
    print(f"Downloading {repo}@{revision} to {path}", flush=True)
    snapshot_download(repo_id=repo, revision=revision, local_dir=path, max_workers=4)
    manifest = {"repository": repo, "revision": revision, "path": str(path)}
    (path / "hackalem-model.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    save(f"download-{kind}", manifest)


def runtime():
    import torch
    import ctranslate2
    import numpy as np
    import soundfile as sf
    from torchcodec.decoders import AudioDecoder
    from pyannote.audio import Pipeline
    from pyannote.audio.telemetry import set_telemetry_metrics
    set_telemetry_metrics(False, save_choice_as_default=True)
    wave = RESULTS / "decoder-synthetic-tone.wav"
    sf.write(wave, np.zeros(16000, dtype=np.float32), 16000)
    decoded = AudioDecoder(str(wave)).get_all_samples()
    gpu = torch.cuda.is_available()
    if gpu:
        x = torch.ones((64, 64), device="cuda")
        assert (x @ x)[0, 0].item() == 64
        torch.cuda.synchronize()
    packages = ["torch", "torchaudio", "torchcodec", "faster-whisper", "ctranslate2", "pyannote.audio", "huggingface-hub", "numpy", "httpx", "pydantic"]
    save("runtime", {
        "python": sys.version, "executable": sys.executable,
        "versions": {name: importlib.metadata.version(name) for name in packages},
        "torch_cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
        "gpu_available": gpu, "gpu": torch.cuda.get_device_name(0) if gpu else None,
        "ct2_gpu_count": ctranslate2.get_cuda_device_count(),
        "ct2_compute_types": sorted(ctranslate2.get_supported_compute_types("cuda" if gpu else "cpu")),
        "torchcodec_samples": list(decoded.data.shape),
        "external_python_network_blocked": True,
        "speech_quality_tested": False,
    })
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (RESULTS / "requirements-freeze.txt").write_text(freeze, encoding="utf-8")


def memory_snapshot():
    import psutil
    result = {"python_rss_mib": round(psutil.Process().memory_info().rss / 2**20, 1)}
    try:
        result["gpu_memory_used_mib"] = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        result["gpu_memory_used_mib"] = None
    return result


def whisper(device, audio=None):
    import torch  # Load CUDA/cuDNN DLLs from the tested PyTorch wheel.
    import ctranslate2
    import numpy as np
    from app.services.stt.local import LocalSTTService
    started = time.monotonic()
    service = LocalSTTService(MODELS["whisper"][1], device=device,
                              compute_type="int8_float16" if device == "cuda" else "int8")
    info = {"device": device, "external_python_network_blocked": True, "speech_quality_tested": False}
    try:
        if audio:
            result = service.transcribe(audio)
            info.update({"source": str(audio), "result": asdict(result), "seconds": round(time.monotonic() - started, 2)})
            # Successful execution is not an automatic quality evaluation.
            save("adapter-stt-audio", info)
        else:
            model = service._load()  # Explicit diagnostic only; constructors stay lazy.
            info["load_seconds"] = round(time.monotonic() - started, 2)
            features = ctranslate2.StorageView.from_array(np.zeros((1, 128, 3000), dtype=np.float32))
            encoded = model.model.encode(features)
            info.update({"encoder_shape": list(encoded.shape), "synthetic_encoder_check": True,
                         "memory_snapshot": memory_snapshot(), "passed": list(encoded.shape) == [1, 1500, 1280]})
            del model, encoded
            save("adapter-load-whisper", info)
            if not info["passed"]:
                raise SystemExit("Unexpected encoder shape")
    finally:
        service.close()


def pyannote(device, audio=None, num_speakers=None):
    from app.services.diarization.local import LocalDiarizationService
    service = LocalDiarizationService(MODELS["pyannote"][1], device=device, num_speakers=num_speakers)
    started = time.monotonic()
    info = {"device": device, "external_python_network_blocked": True, "speech_quality_tested": False}
    try:
        if audio:
            result = service.diarize(audio)
            info.update({"source": str(audio), "speaker_segments": [asdict(turn) for turn in result],
                         "seconds": round(time.monotonic() - started, 2)})
            save("adapter-diarize-audio", info)
        else:
            service._load()
            info.update({"load_seconds": round(time.monotonic() - started, 2),
                         "memory_snapshot": memory_snapshot(), "passed": True})
            save("adapter-load-pyannote", info)
    finally:
        service.close()


def llm():
    from app.services.llm.local import LocalMeetingAnalysisService
    transcript = """SPEAKER_00: Меня зовут Айгуль. Тимур, подготовь API для загрузки аудио к 25 сентября 2026 года.
SPEAKER_01: Я Тимур. Жақсы, API-ді дайындаймын.
SPEAKER_00: Айжанға қазақша интерфейсті тексеруді тапсырамын. Мерзімі айтылған жоқ.
SPEAKER_00: Ещё нужно проверить экспорт PDF, ответственный и срок пока не назначены.
SPEAKER_01: Мен келісемін. Бүгін тек демо деректерін қолданамыз."""
    started = time.monotonic()
    summary, tasks = LocalMeetingAnalysisService().analyze(transcript)
    checks = {
        "summary_string": isinstance(summary, str) and bool(summary.strip()),
        "exactly_three_tasks": len(tasks) == 3,
        "explicit_assignee_and_date": any(t.assignee == "Тимур" and t.deadline and "25" in t.deadline and "2026" in t.deadline for t in tasks),
        "kazakh_assignee_missing_deadline": any(t.assignee == "Айжан" and t.deadline is None for t in tasks),
        "unassigned_pdf_null": any("PDF" in t.task.upper() and t.assignee is None and t.deadline is None for t in tasks),
        "source_attribution": all(t.source_speaker == "SPEAKER_00" and t.assigned_by == "Айгуль" for t in tasks),
        "quotes_exist": all(t.source_text and t.source_text in transcript for t in tasks),
    }
    save("adapter-llm", {"output": {"summary": summary, "tasks": [asdict(t) for t in tasks]},
                        "checks": checks, "passed": all(checks.values()), "synthetic_text_only": True,
                        "external_python_network_blocked": True, "seconds": round(time.monotonic() - started, 2)})
    if not all(checks.values()):
        raise SystemExit("JSON/source validation succeeded but semantic checks failed; inspect the local result.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["download-whisper", "download-pyannote", "runtime", "load-whisper", "load-pyannote", "llm", "stt-audio", "diarize-audio"])
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--revision", help="Pinned Hugging Face commit for reproducible downloads")
    parser.add_argument("--num-speakers", type=int, help="Use only when the actual count is known")
    args = parser.parse_args()
    if args.command.endswith("-audio") and (not args.audio or not args.audio.is_file()):
        parser.error("--audio must point to the agreed local test recording")
    if args.command.startswith("download-"):
        download(args.command.removeprefix("download-"), args.revision)
    else:
        local_network_only()
        if args.command == "runtime": runtime()
        elif args.command == "llm": llm()
        elif args.command in ["load-whisper", "stt-audio"]: whisper(args.device, args.audio)
        else: pyannote(args.device, args.audio, args.num_speakers)
