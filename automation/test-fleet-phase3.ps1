$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ([string]::IsNullOrEmpty($PreviousPythonPath)) { $Root } else { "$Root;$PreviousPythonPath" }
    & python.exe -m compileall -q (Join-Path $Root "fleet")
    if ($LASTEXITCODE -ne 0) { throw "Python compileall failed" }
    & python.exe -m unittest discover -s (Join-Path $Root "tests") -p "test_fleet_phase3.py" -v
    if ($LASTEXITCODE -ne 0) { throw "Phase 3 unit tests failed" }
    Write-Host "NETA fleet Phase 3 non-container tests passed"
}
finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
