# Dot-source from the same shell that will launch the backend or diagnostics.
# Existing computer: pass -VenvPath C:\Users\Amankos\Downloads\Hakaton\.venv
param([string]$VenvPath = $env:HACKALEM_VENV)

$localAiRepo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $VenvPath) { $VenvPath = Join-Path $localAiRepo 'backend\.venv' }
if (-not (Test-Path -LiteralPath (Join-Path $VenvPath 'Scripts\python.exe'))) {
    throw 'Python environment missing. Create backend/.venv or pass -VenvPath to the existing environment.'
}
$env:HACKALEM_VENV = (Resolve-Path -LiteralPath $VenvPath).Path
$env:HACKALEM_PYTHON = Join-Path $env:HACKALEM_VENV 'Scripts\python.exe'
if (-not $env:HACKALEM_AI_HOME) { $env:HACKALEM_AI_HOME = Join-Path $env:LOCALAPPDATA 'HackAlemAI' }
$env:HF_HOME = Join-Path $env:HACKALEM_AI_HOME 'huggingface'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
$env:PYANNOTE_METRICS_ENABLED = '0'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $env:HACKALEM_AI_HOME 'models\ollama'
$env:OLLAMA_MODEL = 'qwen3:4b'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$env:OLLAMA_KEEP_ALIVE = '0'
$env:PYTHONUTF8 = '1'
$env:WHISPER_MODEL_PATH = Join-Path $env:HACKALEM_AI_HOME 'models\faster-whisper-large-v3'
$env:PYANNOTE_MODEL_PATH = Join-Path $env:HACKALEM_AI_HOME 'models\speaker-diarization-community-1'
$env:WHISPER_DEVICE = 'cuda'
$env:WHISPER_COMPUTE_TYPE = 'int8_float16'
$localAiTorchLib = Join-Path $env:HACKALEM_VENV 'Lib\site-packages\torch\lib'
$localAiFFmpegBin = Join-Path $env:HACKALEM_AI_HOME 'tools\ffmpeg-n8.1-latest-win64-gpl-shared-8.1\bin'
$localAiOllamaBin = Join-Path $env:HACKALEM_AI_HOME 'tools\ollama'
$env:PATH = "$localAiTorchLib;$localAiFFmpegBin;$localAiOllamaBin;$env:PATH"
