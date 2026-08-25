[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $repoRoot ".runtime\native-backend-processes.json"

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host "Native backend: stopped"
    return
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$rows = foreach ($record in @($state.processes)) {
    $process = Get-Process -Id ([int]$record.id) -ErrorAction SilentlyContinue
    $running = $false
    if ($null -ne $process) {
        try {
            $running = $process.StartTime.ToUniversalTime().ToString("o") -eq [string]$record.start_time_utc
        }
        catch {
            $running = $false
        }
    }
    [pscustomobject]@{
        Service = $record.name
        PID = $record.id
        Status = if ($running) { "running" } else { "stopped" }
    }
}

$rows | Format-Table -AutoSize
Write-Host "Logs: $(Join-Path $repoRoot '.runtime\logs')"
