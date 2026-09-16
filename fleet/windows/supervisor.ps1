param(
    [Parameter(Mandatory = $true)]
    [string]$ControlDir
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$CommandsDir = Join-Path $ControlDir "commands"
$ResponsesDir = Join-Path $ControlDir "responses"
$LogsDir = "C:\neta-state\logs"
$AgentPath = "C:\neta-agent\neta-agent.exe"
$DatabasePath = "C:\neta-state\neta.db"
$IdentityDir = "C:\neta-state\identity"
$AgentProcess = $null

New-Item -ItemType Directory -Force -Path $ControlDir, $CommandsDir, $ResponsesDir, $LogsDir, $IdentityDir | Out-Null

function Write-AtomicJson {
    param([string]$Path, [object]$Value)
    $Temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 10 -Compress | Set-Content -LiteralPath $Temporary -Encoding UTF8
    Move-Item -LiteralPath $Temporary -Destination $Path -Force
}

function New-Response {
    param([string]$Id, [string]$Status, [hashtable]$Extra = @{})
    $Result = [ordered]@{ id = $Id; status = $Status; timestamp = [DateTime]::UtcNow.ToString("o") }
    foreach ($Key in $Extra.Keys) { $Result[$Key] = $Extra[$Key] }
    return $Result
}

function Stop-Agent {
    if ($null -eq $script:AgentProcess) { return }
    try {
        if (-not $script:AgentProcess.HasExited) {
            $script:AgentProcess.Kill()
            $script:AgentProcess.WaitForExit(10000) | Out-Null
        }
    }
    catch { }
    $script:AgentProcess = $null
}

function Start-Agent {
    param([object]$Command)
    Stop-Agent
    $Duration = if ($null -ne $Command.duration_seconds) { [int]$Command.duration_seconds } else { 86400 }
    $PollMs = if ($null -ne $Command.poll_ms) { [int]$Command.poll_ms } else { 100 }
    $MaxDbMb = if ($null -ne $Command.max_db_mb) { [int]$Command.max_db_mb } else { 200 }
    $Stdout = Join-Path $LogsDir "agent.stdout.log"
    $Stderr = Join-Path $LogsDir "agent.stderr.log"
    $Arguments = @(
        "observe", "--all",
        "--duration", [string]$Duration,
        "--poll-ms", [string]$PollMs,
        "--db", $DatabasePath,
        "--max-db-mb", [string]$MaxDbMb
    )
    $script:AgentProcess = Start-Process -FilePath $AgentPath -ArgumentList $Arguments -PassThru `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    return $script:AgentProcess.Id
}

function Invoke-AgentCommand {
    param([object]$Command)
    $Arguments = @()
    foreach ($Argument in $Command.arguments) { $Arguments += [string]$Argument }
    $Stdout = Join-Path $LogsDir ("command-{0}.stdout.log" -f $Command.id)
    $Stderr = Join-Path $LogsDir ("command-{0}.stderr.log" -f $Command.id)
    $Process = Start-Process -FilePath $AgentPath -ArgumentList $Arguments -PassThru -Wait `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    return @{ exit_code = $Process.ExitCode; stdout_log = $Stdout; stderr_log = $Stderr }
}

function Invoke-Scenario {
    param([object]$Command)
    $ScriptPath = [string]$Command.script
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        throw "scenario script not found: $ScriptPath"
    }
    $Arguments = @("-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath)
    foreach ($Argument in $Command.arguments) { $Arguments += [string]$Argument }
    $Stdout = Join-Path $LogsDir ("scenario-{0}.stdout.log" -f $Command.id)
    $Stderr = Join-Path $LogsDir ("scenario-{0}.stderr.log" -f $Command.id)
    $Process = Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments -PassThru -Wait `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    return @{ exit_code = $Process.ExitCode; process_id = $Process.Id; stdout_log = $Stdout; stderr_log = $Stderr }
}

Write-AtomicJson -Path (Join-Path $ControlDir "ready.json") -Value ([ordered]@{
    status = "ready"
    slot = $env:NETA_ENDPOINT_SLOT
    supervisor_pid = $PID
    timestamp = [DateTime]::UtcNow.ToString("o")
})

try {
    while ($true) {
        $CommandFiles = @(Get-ChildItem -LiteralPath $CommandsDir -Filter "*.json" -File -ErrorAction SilentlyContinue | Sort-Object Name)
        if ($CommandFiles.Count -eq 0) {
            Start-Sleep -Milliseconds 100
            continue
        }
        foreach ($CommandFile in $CommandFiles) {
            $Command = $null
            try {
                $Command = Get-Content -LiteralPath $CommandFile.FullName -Raw | ConvertFrom-Json
                $Response = switch ([string]$Command.type) {
                    "start-agent" {
                        $Pid = Start-Agent -Command $Command
                        New-Response -Id $Command.id -Status "ok" -Extra @{ agent_pid = $Pid }
                    }
                    "stop-agent" {
                        Stop-Agent
                        New-Response -Id $Command.id -Status "ok"
                    }
                    "agent-command" {
                        $Result = Invoke-AgentCommand -Command $Command
                        if ($Result.exit_code -ne 0) {
                            throw "neta-agent command failed with exit code $($Result.exit_code); stderr=$($Result.stderr_log)"
                        }
                        New-Response -Id $Command.id -Status "ok" -Extra $Result
                    }
                    "scenario" {
                        $Result = Invoke-Scenario -Command $Command
                        if ($Result.exit_code -ne 0) {
                            throw "scenario failed with exit code $($Result.exit_code); stderr=$($Result.stderr_log)"
                        }
                        New-Response -Id $Command.id -Status "ok" -Extra $Result
                    }
                    "shutdown" {
                        Stop-Agent
                        New-Response -Id $Command.id -Status "ok" -Extra @{ shutdown = $true }
                    }
                    default { throw "unsupported supervisor command type: $($Command.type)" }
                }
            }
            catch {
                $Id = if ($null -ne $Command -and $null -ne $Command.id) { [string]$Command.id } else { $CommandFile.BaseName }
                $Response = New-Response -Id $Id -Status "error" -Extra @{ error = $_.Exception.Message }
            }
            $ResponsePath = Join-Path $ResponsesDir ("{0}.json" -f $Response.id)
            Write-AtomicJson -Path $ResponsePath -Value $Response
            Remove-Item -LiteralPath $CommandFile.FullName -Force -ErrorAction SilentlyContinue
            if ($Response.Contains("shutdown") -and $Response["shutdown"] -eq $true) { exit 0 }
        }
    }
}
finally {
    Stop-Agent
}
