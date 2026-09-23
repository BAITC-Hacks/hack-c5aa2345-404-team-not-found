# Launch the backend inside the already prepared Local AI environment.
# This script never installs packages, downloads models, or restarts Ollama.
param(
    [string]$VenvPath = $env:HACKALEM_VENV,
    [string]$BindAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$backendRepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $VenvPath) {
    $VenvPath = Join-Path $backendRepoRoot 'backend\.venv'
}
$backendAiEnvironment = Join-Path $backendRepoRoot 'scripts\local-ai\ai-env.ps1'
if (-not (Test-Path -LiteralPath $backendAiEnvironment)) {
    throw 'Missing scripts/local-ai/ai-env.ps1. Update the official team repository first.'
}

. $backendAiEnvironment -VenvPath $VenvPath
$backendPython = $env:HACKALEM_PYTHON
if (-not $backendPython -or -not (Test-Path -LiteralPath $backendPython)) {
    throw 'Prepared Python environment is missing. Pass -VenvPath to the existing Local AI venv.'
}

# Model installation is a separate explicit operation. Runtime must use local files.
$env:HF_HUB_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'

Push-Location -LiteralPath $backendRepoRoot
try {
    Write-Output "Starting SAMRUK KAZYNA backend on ${BindAddress}:$Port (one worker)."
    Write-Output 'Ollama must already be running locally. Press Ctrl+C to stop this backend.'
    & $backendPython -m uvicorn app.main:app --app-dir backend --host $BindAddress --port $Port --workers 1 --no-access-log
    if ($LASTEXITCODE -ne 0) {
        throw "Backend exited with code $LASTEXITCODE. Check runtime dependencies and model configuration."
    }
}
finally {
    Pop-Location
}
