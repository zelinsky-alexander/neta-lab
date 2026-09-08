param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "..\server\payload\neta-lab-004-payload.exe")
)

$ErrorActionPreference = "Stop"
$sourcePath = Join-Path $PSScriptRoot "..\payload\NetaLab004Payload.cs"
$sourcePath = [System.IO.Path]::GetFullPath($sourcePath)
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $OutputPath

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Payload source not found: $sourcePath"
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue

$source = Get-Content -LiteralPath $sourcePath -Raw
Add-Type `
    -TypeDefinition $source `
    -ReferencedAssemblies "System.Net.Http.dll" `
    -OutputAssembly $OutputPath `
    -OutputType ConsoleApplication

$hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $OutputPath).Length

Write-Host "NETA-LAB-004 benign payload built"
Write-Host "path=$OutputPath"
Write-Host "sha256=$hash"
Write-Host "bytes=$size"
