[CmdletBinding()]
param(
    [ValidateSet("api", "research", "ai", "worker", "event-worker", "news-worker", "agent-worker")]
    [string[]]$Services = @()
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $repoRoot ".runtime\native-backend-processes.json"

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host "Native backend is not running (no process state file)."
    return
}

try {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
}
catch {
    throw "Cannot read $statePath. Refusing to stop unverified process IDs. $($_.Exception.Message)"
}

$requestedServices = @($Services | Select-Object -Unique)
$stopAll = $requestedServices.Count -eq 0
$remaining = [System.Collections.Generic.List[object]]::new()
$records = @($state.processes)
for ($index = $records.Count - 1; $index -ge 0; $index--) {
    $record = $records[$index]
    $process = Get-Process -Id ([int]$record.id) -ErrorAction SilentlyContinue
    $matches = $false
    if ($null -ne $process) {
        try {
            $matches = $process.StartTime.ToUniversalTime().ToString("o") -eq [string]$record.start_time_utc
        }
        catch {
            $matches = $false
        }
    }

    if (-not $matches) {
        Write-Warning "Dropped stale process record: $($record.name) PID $($record.id)."
        continue
    }
    if ($stopAll -or $record.name -in $requestedServices) {
        Stop-Process -Id $process.Id -ErrorAction Stop
        Write-Host ("Stopped         {0,-12} PID {1}" -f $record.name, $record.id)
        continue
    }
    $remaining.Add($record)
}

if ($remaining.Count -eq 0) {
    Remove-Item -LiteralPath $statePath -Force
    Write-Host "Requested native services stopped. Database service was not changed."
    return
}

$nextState = [pscustomobject]@{
    created_at = [DateTime]::UtcNow.ToString("o")
    processes = @($remaining)
}
$nextState | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
Write-Host "Requested native services stopped. Remaining: $($remaining.name -join ', ')."
