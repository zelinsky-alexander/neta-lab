param(
    [Parameter(Mandatory = $true)]
    [string]$PipeName,
    [Parameter(Mandatory = $true)]
    [string]$ReadyFile
)

$ErrorActionPreference = "Stop"
$Pipe = New-Object System.IO.Pipes.NamedPipeServerStream(
    $PipeName,
    [System.IO.Pipes.PipeDirection]::InOut,
    1,
    [System.IO.Pipes.PipeTransmissionMode]::Message,
    [System.IO.Pipes.PipeOptions]::Asynchronous
)
try {
    Set-Content -LiteralPath $ReadyFile -Value "ready" -Encoding Ascii
    while ($true) { Start-Sleep -Seconds 1 }
}
finally {
    $Pipe.Dispose()
}
