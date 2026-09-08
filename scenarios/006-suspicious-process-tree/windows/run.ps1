param(
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"

$runId = "{0}-{1}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ"), $PID
$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("neta-lab-006-{0}" -f $runId)
$sourceCmd = Join-Path $env:SystemRoot "System32\cmd.exe"
$copiedCmd = Join-Path $workDir "windows-update-helper.exe"
$whoamiOutput = Join-Path $workDir "whoami.txt"
$hostnameOutput = Join-Path $workDir "hostname.txt"
$ipconfigOutput = Join-Path $workDir "ipconfig.txt"

if (-not (Test-Path -LiteralPath $sourceCmd -PathType Leaf)) {
    throw "System cmd.exe not found at $sourceCmd"
}

New-Item -ItemType Directory -Path $workDir -Force | Out-Null

try {
    Copy-Item -LiteralPath $sourceCmd -Destination $copiedCmd -Force

    $sourceHash = (Get-FileHash -LiteralPath $sourceCmd -Algorithm SHA256).Hash.ToLowerInvariant()
    $copiedHash = (Get-FileHash -LiteralPath $copiedCmd -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -ne $copiedHash) {
        throw "Copied executable hash mismatch: source=$sourceHash copy=$copiedHash"
    }

    $signature = Get-AuthenticodeSignature -FilePath $copiedCmd
    $signerSubject = if ($null -ne $signature.SignerCertificate) {
        $signature.SignerCertificate.Subject
    }
    else {
        ""
    }

    $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($copiedCmd)
    $originalFilename = $versionInfo.OriginalFilename

    $childCommand = 'whoami.exe > "{0}" & hostname.exe > "{1}" & ipconfig.exe /all > "{2}"' -f `
        $whoamiOutput, $hostnameOutput, $ipconfigOutput

    Write-Host "NETA-LAB-006 run_id=$runId"
    Write-Host "source_executable=$sourceCmd"
    Write-Host "copied_executable=$copiedCmd"
    Write-Host "source_sha256=$sourceHash"
    Write-Host "copied_sha256=$copiedHash"
    Write-Host "authenticode_status=$($signature.Status)"
    Write-Host "signer_subject=$signerSubject"
    Write-Host "original_filename=$originalFilename"
    Write-Host "requested_children=whoami.exe,hostname.exe,ipconfig.exe"

    $process = Start-Process `
        -FilePath $copiedCmd `
        -ArgumentList @('/d', '/c', $childCommand) `
        -PassThru `
        -Wait

    if ($process.ExitCode -ne 0) {
        throw "Renamed cmd.exe exited with code $($process.ExitCode)"
    }

    foreach ($path in @($whoamiOutput, $hostnameOutput, $ipconfigOutput)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Expected child-process output was not created: $path"
        }
    }

    $groundTruth = [ordered]@{
        scenario = "NETA-LAB-006"
        run_id = $runId
        source_executable = $sourceCmd
        copied_executable = $copiedCmd
        source_sha256 = $sourceHash
        copied_sha256 = $copiedHash
        hashes_equal = ($sourceHash -eq $copiedHash)
        authenticode_status = [string]$signature.Status
        signer_subject = $signerSubject
        original_filename = $originalFilename
        copied_process_pid = $process.Id
        copied_process_exit_code = $process.ExitCode
        requested_children = @("whoami.exe", "hostname.exe", "ipconfig.exe")
        network_required = $false
    }

    Write-Host "NETA-LAB-006 ground_truth_json=$($groundTruth | ConvertTo-Json -Compress)"
    Write-Host "NETA-LAB-006 complete run_id=$runId"
}
finally {
    if ($KeepArtifacts) {
        Write-Host "NETA-LAB-006 retained_artifacts=$workDir"
    }
    else {
        Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
