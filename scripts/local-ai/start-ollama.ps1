param([string]$VenvPath = $env:HACKALEM_VENV)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ai-env.ps1') -VenvPath $VenvPath
$localAiOllama = Join-Path $env:HACKALEM_AI_HOME 'tools\ollama\ollama.exe'
$localAiLogs = Join-Path $env:HACKALEM_AI_HOME 'logs'
New-Item -ItemType Directory -Force -Path $localAiLogs | Out-Null
try {
    $localAiExisting = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    Write-Output "Ollama already running: $($localAiExisting.version). Existing process settings are unchanged; verify cloud is disabled."
    return
} catch {}
if (-not (Test-Path -LiteralPath $localAiOllama)) { throw 'Install the official Ollama CLI first; see docs/local-ai/handoff.md.' }
$localAiProcess = Start-Process -FilePath $localAiOllama -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localAiLogs 'ollama.stdout.log') -RedirectStandardError (Join-Path $localAiLogs 'ollama.stderr.log')
for ($localAiAttempt = 0; $localAiAttempt -lt 20; $localAiAttempt++) {
    if ($localAiProcess.HasExited) { throw 'Ollama stopped. See local logs.' }
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 1
        Write-Output "Local Ollama ready: PID $($localAiProcess.Id), http://127.0.0.1:11434"
        return
    } catch { Start-Sleep -Milliseconds 500 }
}
throw 'Ollama startup timed out. See local logs.'
