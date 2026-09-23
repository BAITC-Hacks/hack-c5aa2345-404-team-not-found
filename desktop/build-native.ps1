$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $taskCompiler)) {
    $taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path -LiteralPath $taskCompiler)) { throw 'Install the official .NET Framework 4.8 Developer Pack to build.' }
$taskRelease = Join-Path $PSScriptRoot 'release'
New-Item -ItemType Directory -Force -Path $taskRelease | Out-Null
$taskExe = Join-Path $taskRelease 'SAMRUK-KAZYNA.exe'
$taskSources = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'native') -Filter '*.cs' -File | ForEach-Object { $_.FullName })
$taskArguments = @('/nologo', '/target:winexe', '/platform:anycpu', '/optimize+', '/utf8output',
    '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll', '/reference:System.Web.Extensions.dll',
    '/reference:System.Net.Http.dll', '/reference:System.IO.Compression.dll',
    '/reference:System.IO.Compression.FileSystem.dll',
    ('/win32manifest:' + (Join-Path $PSScriptRoot 'native\app.manifest')),
    ('/resource:' + (Join-Path $taskRoot 'samples\api\meeting-completed.json') + ',SamrukDesktop.Demo.json'),
    ('/out:' + $taskExe))
& $taskCompiler @taskArguments @taskSources
if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
$taskHash = (Get-FileHash -LiteralPath $taskExe -Algorithm SHA256).Hash.ToLowerInvariant()
("$taskHash  SAMRUK-KAZYNA.exe") | Set-Content -LiteralPath (Join-Path $taskRelease 'SAMRUK-KAZYNA.exe.sha256') -Encoding ascii
Write-Output "Native EXE: $taskExe"
Write-Output "SHA256: $taskHash"
