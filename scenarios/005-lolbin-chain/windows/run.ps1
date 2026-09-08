param(
    [Parameter(Mandatory = $true)]
    [string]$HostAddress,
    [int]$Port = 18580,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
$runId = "{0}-{1}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ"), $PID
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("neta-lab-005-{0}" -f $runId)
$stage = Join-Path $root "stage.txt"
$encoded = Join-Path $root "stage.b64"
$decoded = Join-Path $root "stage.decoded.txt"
$downloadUrl = "http://$HostAddress`:$Port/stage.txt?run_id=$runId"
$callbackUrl = "http://$HostAddress`:$Port/callback?run_id=$runId"
$certutil = Join-Path $env:SystemRoot "System32\certutil.exe"

New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "NETA-LAB-005 run_id=$runId"
Write-Host "artifact_dir=$root"
Write-Host "download_url=$downloadUrl"

try {
    if (-not (Test-Path -LiteralPath $certutil)) {
        throw "certutil.exe not found at $certutil"
    }

    $signature = Get-AuthenticodeSignature -FilePath $certutil
    $signerSubject = ""
    if ($null -ne $signature.SignerCertificate) {
        $signerSubject = $signature.SignerCertificate.Subject
    }
    Write-Host "certutil_signature_status=$($signature.Status)"
    Write-Host "certutil_signer_subject=$signerSubject"

    & $certutil -urlcache -split -f $downloadUrl $stage | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "certutil download failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $stage)) {
        throw "downloaded stage file was not created"
    }

    $stageHash = (Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "stage_sha256=$stageHash"

    & $certutil -encode $stage $encoded | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "certutil encode failed with exit code $LASTEXITCODE"
    }

    & $certutil -decode $encoded $decoded | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "certutil decode failed with exit code $LASTEXITCODE"
    }

    $decodedHash = (Get-FileHash -LiteralPath $decoded -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "decoded_sha256=$decodedHash"
    if ($decodedHash -ne $stageHash) {
        throw "encode/decode round trip changed the staged content"
    }

    $headers = @{
        "X-NETA-Lab-Scenario" = "NETA-LAB-005"
        "X-NETA-Lab-Run" = $runId
        "X-NETA-Lab-Stage-Sha256" = $stageHash
    }

    $response = Invoke-WebRequest -UseBasicParsing -Uri $callbackUrl -Headers $headers -TimeoutSec 15
    if ($response.StatusCode -ne 200) {
        throw "callback returned HTTP $($response.StatusCode)"
    }

    Write-Host "NETA-LAB-005 complete run_id=$runId callback_status=$($response.StatusCode)"
}
finally {
    if ($KeepArtifacts) {
        Write-Host "NETA-LAB-005 keeping artifacts at $root"
    }
    else {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
