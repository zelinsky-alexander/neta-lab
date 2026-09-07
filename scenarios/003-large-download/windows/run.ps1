param(
    [Parameter(Mandatory = $true)]
    [string]$HostAddress,
    [int]$Port = 18080,
    [int]$SizeMiB = 50
)

$ErrorActionPreference = "Stop"
$runId = "{0}-{1}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ"), $PID
$url = "http://$HostAddress`:$Port/large-download?size_mib=$SizeMiB"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("neta-lab-003-{0}.bin" -f $runId)
$expectedBytes = [int64]$SizeMiB * 1024 * 1024

Write-Host "NETA-LAB-003 run_id=$runId target=$url expected_bytes=$expectedBytes"

try {
    & curl.exe --silent --show-error --fail `
        --header "X-NETA-Lab-Scenario: NETA-LAB-003" `
        --header "X-NETA-Lab-Run: $runId" `
        --user-agent "NETA-Lab/003" `
        --output $tmp `
        $url
    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe failed with exit code $LASTEXITCODE"
    }

    $actualBytes = (Get-Item $tmp).Length
    if ($actualBytes -ne $expectedBytes) {
        throw "NETA-LAB-003 FAIL: expected $expectedBytes bytes, got $actualBytes"
    }

    Write-Host "NETA-LAB-003 complete run_id=$runId bytes=$actualBytes"
}
finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
