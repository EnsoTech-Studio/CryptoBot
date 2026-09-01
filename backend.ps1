[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "db", "api", "research", "ai", "worker", "event-worker", "news-worker", "workers", "stop", "down", "status", "logs", "setup", "help")]
    [string]$Command = "help",
    [Parameter(Position = 1)]
    [ValidateSet("api", "research", "ai", "worker", "event-worker", "news-worker", "workers", "all")]
    [string]$Target = "",
    [string]$EnvFile = ".env",
    [switch]$SkipBuild,
    [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$startScript = Join-Path $repoRoot "scripts\start-native-backend.ps1"
$stopScript = Join-Path $repoRoot "scripts\stop-native-backend.ps1"
$statusScript = Join-Path $repoRoot "scripts\status-native-backend.ps1"
$setupScript = Join-Path $repoRoot "scripts\setup-native-backend.ps1"
$apiBinary = Join-Path $repoRoot ".runtime\bin\cryptobot-api.exe"
$workerServices = @("worker", "event-worker", "news-worker", "agent-worker")

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Import-LauncherEnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            continue
        }
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Test-UsesExternalDatabase {
    $resolvedEnvFile = $EnvFile
    if (-not [System.IO.Path]::IsPathRooted($resolvedEnvFile)) {
        $resolvedEnvFile = Join-Path $repoRoot $resolvedEnvFile
    }
    Import-LauncherEnvFile $resolvedEnvFile

    $sawDatabaseUrl = $false
    foreach ($name in @("MIGRATION_DATABASE_URL", "DATABASE_URL", "MARKET_DATABASE_URL")) {
        $url = [Environment]::GetEnvironmentVariable($name, "Process")
        if ([string]::IsNullOrWhiteSpace($url)) {
            continue
        }
        $sawDatabaseUrl = $true
        $lower = $url.ToLowerInvariant()
        if ($lower -match "//(localhost|127\.0\.0\.1|postgres)(:|/)" -or $lower -match "@(localhost|127\.0\.0\.1|postgres)(:|/)") {
            return $false
        }
    }
    return $sawDatabaseUrl
}

function Start-Database {
    if (Test-UsesExternalDatabase) {
        Write-Host "External PostgreSQL configured; skipping Docker PostgreSQL."
        return
    }
    $docker = Get-Command "docker" -ErrorAction Stop
    Invoke-Checked $docker.Source @("compose", "--profile", "local-db", "up", "-d", "postgres")
}

function Stop-Database {
    if (Test-UsesExternalDatabase) {
        Write-Host "External PostgreSQL configured; no Docker PostgreSQL to stop."
        return
    }
    $docker = Get-Command "docker" -ErrorAction Stop
    Invoke-Checked $docker.Source @("compose", "--profile", "local-db", "down")
}

function Show-DatabaseStatus {
    if (Test-UsesExternalDatabase) {
        Write-Host "External PostgreSQL configured; Docker PostgreSQL is not used."
        return
    }
    $docker = Get-Command "docker" -ErrorAction Stop
    Invoke-Checked $docker.Source @("compose", "--profile", "local-db", "ps")
}

function Resolve-Services {
    param([Parameter(Mandatory = $true)][string]$Name)
    switch ($Name) {
        "workers" { return $workerServices }
        "all" { return @() }
        default { return @($Name) }
    }
}

function Start-NativeServices {
    param([string[]]$Services = @())

    $databaseServices = @("api", "research", "worker", "event-worker", "news-worker")
    $needsDatabase = $Services.Count -eq 0 -or @($Services | Where-Object { $_ -in $databaseServices }).Count -gt 0
    if ($needsDatabase) {
        Start-Database
    }

    $startParameters = @{ EnvFile = $EnvFile }
    if ($Services.Count -gt 0) {
        $startParameters.Services = $Services
    }
    if ($SkipMigrations) {
        $startParameters.SkipMigrations = $true
    }
    if ($SkipBuild) {
        $startParameters.SkipBuild = $true
    }
    elseif ($Services.Count -eq 0 -or $Services -contains "api") {
        if ($null -eq (Get-Command "go" -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $apiBinary)) {
            Write-Warning "Go 1.23 is not on PATH; using the existing native API binary."
            $startParameters.SkipBuild = $true
        }
    }
    & $startScript @startParameters
}

function Stop-NativeServices {
    param([string[]]$Services = @())
    $stopParameters = @{}
    if ($Services.Count -gt 0) {
        $stopParameters.Services = $Services
    }
    & $stopScript @stopParameters
}

switch ($Command) {
    "up" {
        Start-NativeServices
        break
    }
    "db" {
        Start-Database
        break
    }
    "api" { Start-NativeServices -Services @("api"); break }
    "research" { Start-NativeServices -Services @("research"); break }
    "ai" { Start-NativeServices -Services @("ai"); break }
    "worker" { Start-NativeServices -Services @("worker"); break }
    "event-worker" { Start-NativeServices -Services @("event-worker"); break }
    "news-worker" { Start-NativeServices -Services @("news-worker"); break }
    "workers" { Start-NativeServices -Services $workerServices; break }
    "stop" {
        if ($Target) {
            Stop-NativeServices (Resolve-Services $Target)
        }
        else {
            Stop-NativeServices
        }
        break
    }
    "down" {
        Stop-NativeServices
        Stop-Database
        break
    }
    "status" {
        & $statusScript
        Show-DatabaseStatus
        break
    }
    "logs" {
        if (-not $Target -or $Target -in @("workers", "all")) {
            throw "Use one service name, for example: .\backend.ps1 logs api"
        }
        $logPath = Join-Path $repoRoot ".runtime\logs\${Target}.out.log"
        if (-not (Test-Path -LiteralPath $logPath)) {
            throw "No log file found for '$Target': $logPath"
        }
        Get-Content -LiteralPath $logPath -Tail 100 -Wait
        break
    }
    "setup" {
        & $setupScript
        break
    }
    default {
        @"
Run from the repository root:

  run up                            Start all backend services; skips Docker DB for Supabase
  run db                            Start optional local PostgreSQL only
  run api                           Start Go API and its research dependency
  run research | run ai             Start one service
  run worker                        Start the backtest worker
  run event-worker                  Start the outbox worker
  run news-worker                   Start the news worker
  run workers                       Start all three workers
  run stop [service]                Stop all, or one service/group
  run status                        Show native backend and PostgreSQL status
  run logs <service>                Tail a service log
  run down                          Stop backend and optional local PostgreSQL

PowerShell: run .\scripts\install-run-command.ps1 once to register this command.
"@ | Write-Host
    }
}
