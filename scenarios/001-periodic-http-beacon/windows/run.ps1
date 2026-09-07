param(
    [Parameter(Mandatory = $true)]
    [string]$HostAddress,
    [int]$Port = 18080,
    [int]$Count = 12,
    [int]$IntervalSeconds = 5
)

$ErrorActionPreference = "Stop"
$RunId = [guid]::NewGuid().ToString()
$Url = "http://${HostAddress}:$Port/beacon"

Write-Host "NETA-LAB-001 run_id=$RunId target=$Url count=$Count interval=${IntervalSeconds}s"

for ($i = 1; $i -le $Count; $i++) {
    $Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Write-Host "[$Timestamp] request $i/$Count"

    & curl.exe --silent --show-error --fail `
        --header "X-NETA-Lab-Scenario: NETA-LAB-001" `
        --header "X-NETA-Lab-Run: $RunId" `
        --user-agent "NETA-Lab/001" `
        $Url | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe failed with exit code $LASTEXITCODE"
    }

    if ($i -lt $Count) {
        Start-Sleep -Seconds $IntervalSeconds
    }
}

Write-Host "NETA-LAB-001 complete run_id=$RunId"
