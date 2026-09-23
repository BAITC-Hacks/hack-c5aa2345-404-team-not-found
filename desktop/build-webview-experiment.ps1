param([string]$Python = "", [switch]$SkipInstall)
Write-Warning 'Historical WebView experiment; the verified client uses build-native.ps1.'
$ErrorActionPreference = "Stop"
$taskRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$taskVenv = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$taskOutput = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "out\SAMRUK-KAZYNA"))
# PyInstaller --noconfirm can replace this directory. Validate the final path.
if (-not $taskOutput.StartsWith(($taskRoot.TrimEnd('\') + '\desktop\out\'), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace a build directory outside this workspace"
}
foreach ($taskProcess in (Get-Process SAMRUK-KAZYNA -ErrorAction SilentlyContinue)) {
    if ($taskProcess.Path -eq (Join-Path $taskOutput "SAMRUK-KAZYNA.exe")) {
        throw "Close the built SAMRUK KAZYNA application before rebuilding"
    }
}
Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath $taskVenv)) {
        if ($Python) { & $Python -m venv (Join-Path $PSScriptRoot ".venv") }
        else { & py -3.12 -m venv (Join-Path $PSScriptRoot ".venv") }
        if ($LASTEXITCODE -ne 0) { throw "Creating Python 3.12 venv failed" }
    }
    & $taskVenv -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Use Python 3.12 x64'"
    if ($LASTEXITCODE -ne 0) { throw "Unsupported build interpreter" }
    if (-not $SkipInstall) {
        & $taskVenv -m pip install -r desktop/requirements-lock.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    }
    & $taskVenv -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
    & $taskVenv -m PyInstaller --noconfirm --distpath desktop/out --workpath desktop/build desktop/SAMRUK-KAZYNA.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    & $taskVenv desktop/package.py
    if ($LASTEXITCODE -ne 0) { throw "Portable archive packaging failed" }
} finally {
    Pop-Location
}
