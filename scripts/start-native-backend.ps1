[CmdletBinding()]
param(
    [string]$EnvFile = ".env",
    [ValidateSet("api", "research", "ai", "worker", "event-worker", "news-worker")]
    [string[]]$Services = @(),
    [switch]$SkipAI,
    [switch]$SkipWorkers,
    [switch]$SkipMigrations,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeDirectory = Join-Path $repoRoot ".runtime"
$binaryDirectory = Join-Path $runtimeDirectory "bin"
$logDirectory = Join-Path $runtimeDirectory "logs"
$statePath = Join-Path $runtimeDirectory "native-backend-processes.json"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$allServices = @("research", "ai", "worker", "event-worker", "news-worker", "api")
$trackedProcesses = [System.Collections.Generic.List[object]]::new()
$newProcesses = [System.Collections.Generic.List[object]]::new()

function Import-EnvFile {
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
            throw "Invalid environment entry in ${Path}: $line"
        }
        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            throw "Invalid environment variable name in ${Path}: $name"
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

function Get-ProcessEnvironment {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [Environment]::GetEnvironmentVariable($Name, "Process")
}

function Set-DefaultEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )
    if ([string]::IsNullOrWhiteSpace((Get-ProcessEnvironment $Name))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Get-Port {
    param([Parameter(Mandatory = $true)][string]$Name)
    $value = Get-ProcessEnvironment $Name
    $parsed = 0
    if (-not [int]::TryParse($value, [ref]$parsed) -or $parsed -lt 1 -or $parsed -gt 65535) {
        throw "$Name must be a valid TCP port; received '$value'."
    }
    return $parsed
}

function Test-TrackedProcess {
    param([Parameter(Mandatory = $true)]$Record)
    $process = Get-Process -Id ([int]$Record.id) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }
    try {
        return $process.StartTime.ToUniversalTime().ToString("o") -eq [string]$Record.start_time_utc
    }
    catch {
        return $false
    }
}

function Save-ProcessState {
    if ($trackedProcesses.Count -eq 0) {
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        return
    }
    $state = [pscustomobject]@{
        created_at = [DateTime]::UtcNow.ToString("o")
        processes = @($trackedProcesses)
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Stop-NewProcesses {
    for ($index = $newProcesses.Count - 1; $index -ge 0; $index--) {
        $record = $newProcesses[$index]
        if (Test-TrackedProcess $record) {
            Stop-Process -Id ([int]$record.id) -ErrorAction SilentlyContinue
        }
        [void]$trackedProcesses.Remove($record)
    }
    Save-ProcessState
}

function Start-BackendProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $stdoutPath = Join-Path $logDirectory "${Name}.out.log"
    $stderrPath = Join-Path $logDirectory "${Name}.err.log"
    $startParameters = @{
        FilePath = $FilePath
        WorkingDirectory = $WorkingDirectory
        WindowStyle = "Hidden"
        RedirectStandardOutput = $stdoutPath
        RedirectStandardError = $stderrPath
        PassThru = $true
    }
    if ($Arguments.Count -gt 0) {
        $startParameters.ArgumentList = $Arguments
    }
    $process = Start-Process @startParameters
    $process.Refresh()
    $record = [pscustomobject]@{
        name = $Name
        id = $process.Id
        start_time_utc = $process.StartTime.ToUniversalTime().ToString("o")
        executable = $FilePath
        stdout = $stdoutPath
        stderr = $stderrPath
    }
    $trackedProcesses.Add($record)
    $newProcesses.Add($record)
    Save-ProcessState
    Write-Host ("Started {0,-12} PID {1}" -f $Name, $process.Id)
}

function Wait-Database {
    param([int]$TimeoutSeconds = 45)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        & $venvPython -c "import os, psycopg; connection = psycopg.connect(os.environ['MIGRATION_DATABASE_URL'], connect_timeout=2); connection.close()" *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "PostgreSQL did not become reachable within ${TimeoutSeconds}s. Run 'docker compose up -d' first."
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri,
        [int]$TimeoutSeconds = 60
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Host "$Name ready at $Uri"
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "$Name did not become ready within ${TimeoutSeconds}s. Inspect $logDirectory."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Missing .venv. Run scripts/setup-native-backend.ps1 first."
}

New-Item -ItemType Directory -Force -Path $runtimeDirectory, $binaryDirectory, $logDirectory | Out-Null
if (Test-Path -LiteralPath $statePath) {
    try {
        $existingState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        foreach ($record in @($existingState.processes)) {
            if (Test-TrackedProcess $record) {
                $trackedProcesses.Add($record)
            }
            else {
                Write-Warning "Dropped stale process record: $($record.name) PID $($record.id)."
            }
        }
        Save-ProcessState
    }
    catch {
        throw "Cannot read $statePath. Refusing to start alongside unverified process IDs. $($_.Exception.Message)"
    }
}

$resolvedEnvFile = $EnvFile
if (-not [System.IO.Path]::IsPathRooted($resolvedEnvFile)) {
    $resolvedEnvFile = Join-Path $repoRoot $resolvedEnvFile
}
Import-EnvFile $resolvedEnvFile

Set-DefaultEnvironment "POSTGRES_USER" "cryptobot"
Set-DefaultEnvironment "POSTGRES_PASSWORD" "cryptobot"
Set-DefaultEnvironment "POSTGRES_DB" "cryptobot"
Set-DefaultEnvironment "POSTGRES_PORT" "5432"
Set-DefaultEnvironment "RESEARCH_DATABASE_USER" "research_service"
Set-DefaultEnvironment "RESEARCH_DATABASE_PASSWORD" "research_service"
Set-DefaultEnvironment "API_DATABASE_USER" "api_service"
Set-DefaultEnvironment "API_DATABASE_PASSWORD" "api_service"

$postgresPort = Get-Port "POSTGRES_PORT"
$postgresUser = Get-ProcessEnvironment "POSTGRES_USER"
$postgresPassword = Get-ProcessEnvironment "POSTGRES_PASSWORD"
$postgresDatabase = Get-ProcessEnvironment "POSTGRES_DB"
$researchDatabaseUser = Get-ProcessEnvironment "RESEARCH_DATABASE_USER"
$researchDatabasePassword = Get-ProcessEnvironment "RESEARCH_DATABASE_PASSWORD"
$apiDatabaseUser = Get-ProcessEnvironment "API_DATABASE_USER"
$apiDatabasePassword = Get-ProcessEnvironment "API_DATABASE_PASSWORD"

Set-DefaultEnvironment "MIGRATION_DATABASE_URL" "postgres://${postgresUser}:${postgresPassword}@127.0.0.1:${postgresPort}/${postgresDatabase}?sslmode=disable"
Set-DefaultEnvironment "DATABASE_URL" "postgres://${researchDatabaseUser}:${researchDatabasePassword}@127.0.0.1:${postgresPort}/${postgresDatabase}?sslmode=disable"
Set-DefaultEnvironment "MARKET_DATABASE_URL" "postgres://${apiDatabaseUser}:${apiDatabasePassword}@127.0.0.1:${postgresPort}/${postgresDatabase}?sslmode=disable"
Set-DefaultEnvironment "API_PORT" "8080"
Set-DefaultEnvironment "AI_PORT" "8000"
if ([string]::IsNullOrWhiteSpace((Get-ProcessEnvironment "RESEARCH_PORT"))) {
    $defaultResearchPort = if ((Get-ProcessEnvironment "AI_PORT") -eq "8001") { "8002" } else { "8001" }
    Set-DefaultEnvironment "RESEARCH_PORT" $defaultResearchPort
}
Set-DefaultEnvironment "PORT" (Get-ProcessEnvironment "API_PORT")
Set-DefaultEnvironment "RESEARCH_SERVICE_URL" "http://127.0.0.1:$(Get-ProcessEnvironment 'RESEARCH_PORT')"
Set-DefaultEnvironment "AI_SERVICE_URL" "http://127.0.0.1:$(Get-ProcessEnvironment 'AI_PORT')"
Set-DefaultEnvironment "INTERNAL_SERVICE_TOKEN" "development-internal-token"
Set-DefaultEnvironment "CORS_ALLOWED_ORIGINS" "http://localhost:3000"
Set-DefaultEnvironment "COOKIE_SECURE" "false"
Set-DefaultEnvironment "SHUTDOWN_TIMEOUT" "10s"
Set-DefaultEnvironment "RESEARCH_REQUEST_TIMEOUT" "15s"
Set-DefaultEnvironment "RESEARCH_MAX_BODY_BYTES" "4194304"
Set-DefaultEnvironment "MAX_REQUEST_BYTES" "1048576"
Set-DefaultEnvironment "WORKER_ID" "worker-1"
Set-DefaultEnvironment "EVENT_WORKER_ID" "events-1"
Set-DefaultEnvironment "WORKER_LEASE_SECONDS" "120"
Set-DefaultEnvironment "WORKER_HEARTBEAT_SECONDS" "30"
Set-DefaultEnvironment "AI_REQUEST_TIMEOUT_SECONDS" "5"
Set-DefaultEnvironment "SENTIMENT_MODEL" "sentiment-v1"
Set-DefaultEnvironment "SENTIMENT_MODEL_VERSION" "2026-08-01"
Set-DefaultEnvironment "NEWS_COLLECTION_INTERVAL_SECONDS" "900"
Set-DefaultEnvironment "SENTIMENT_BACKFILL_INTERVAL_SECONDS" "60"
Set-DefaultEnvironment "PYTHONUNBUFFERED" "1"
Set-DefaultEnvironment "JWT_PRIVATE_KEY_FILE" (Join-Path $runtimeDirectory "jwt-private.pem")

$jwtPath = Get-ProcessEnvironment "JWT_PRIVATE_KEY_FILE"
if (-not [System.IO.Path]::IsPathRooted($jwtPath)) {
    $jwtPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $jwtPath))
    [Environment]::SetEnvironmentVariable("JWT_PRIVATE_KEY_FILE", $jwtPath, "Process")
}

$apiPort = Get-Port "API_PORT"
$researchPort = Get-Port "RESEARCH_PORT"
$aiPort = Get-Port "AI_PORT"
$runningNames = @($trackedProcesses | ForEach-Object { $_.name })
$targetServices = @()
if ($Services.Count -gt 0) {
    $targetServices += @($Services | Select-Object -Unique)
}
else {
    $targetServices += $allServices
}
if ($SkipAI) {
    $targetServices = @($targetServices | Where-Object { $_ -ne "ai" })
}
if ($SkipWorkers) {
    $targetServices = @($targetServices | Where-Object { $_ -notin @("worker", "event-worker", "news-worker") })
}
if ($targetServices.Count -eq 0) {
    throw "No services selected after applying skip switches."
}
if ($targetServices -contains "api" -and $runningNames -notcontains "research" -and $targetServices -notcontains "research") {
    $targetServices += "research"
    Write-Host "Added research because the Go API requires it."
}
$servicesToStart = @($targetServices | Where-Object { $_ -notin $runningNames })
if ($servicesToStart.Count -eq 0) {
    Write-Host "Requested services are already running: $($targetServices -join ', ')."
    return
}

$portByService = @{ api = $apiPort; research = $researchPort; ai = $aiPort }
$listeningPorts = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners().Port
foreach ($service in $servicesToStart) {
    if ($portByService.ContainsKey($service) -and $listeningPorts -contains $portByService[$service]) {
        throw "TCP port $($portByService[$service]) is already in use. Stop the conflicting service or change the port in .env."
    }
}

$databaseServices = @("api", "research", "worker", "event-worker", "news-worker")
$needsDatabase = @($servicesToStart | Where-Object { $_ -in $databaseServices }).Count -gt 0
$apiBinary = Join-Path $binaryDirectory "cryptobot-api.exe"
$go = $null
if ($servicesToStart -contains "api" -and -not $SkipBuild) {
    $go = Get-Command "go" -ErrorAction SilentlyContinue
    if ($null -eq $go) {
        throw "Go 1.23 is required on PATH to build the native API. Use -SkipBuild only when $apiBinary is already available."
    }
}
if ($servicesToStart -contains "api" -and $SkipBuild -and -not (Test-Path -LiteralPath $apiBinary)) {
    throw "Missing $apiBinary. Start without -SkipBuild once."
}

if ($needsDatabase) {
    Wait-Database
    if (-not $SkipMigrations) {
        & $venvPython -m app.migrate
        if ($LASTEXITCODE -ne 0) {
            throw "Database migration failed with exit code $LASTEXITCODE."
        }
    }
}
if ($servicesToStart -contains "api" -and -not $SkipBuild) {
    Push-Location (Join-Path $repoRoot "server")
    try {
        & $go.Source build -o $apiBinary ./cmd/api
        if ($LASTEXITCODE -ne 0) {
            throw "Go API build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

try {
    if ($servicesToStart -contains "research") {
        Start-BackendProcess -Name "research" -FilePath $venvPython -Arguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$researchPort") -WorkingDirectory $repoRoot
    }
    if ($servicesToStart -contains "ai") {
        Start-BackendProcess -Name "ai" -FilePath $venvPython -Arguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$aiPort") -WorkingDirectory (Join-Path $repoRoot "ai")
    }
    if ($servicesToStart -contains "research") {
        Wait-HttpReady "research" "http://127.0.0.1:${researchPort}/ready"
    }
    if ($servicesToStart -contains "ai") {
        Wait-HttpReady "ai" "http://127.0.0.1:${aiPort}/health"
    }
    if ($servicesToStart -contains "worker") {
        Start-BackendProcess -Name "worker" -FilePath $venvPython -Arguments @("-m", "app.worker", "queue") -WorkingDirectory $repoRoot
    }
    if ($servicesToStart -contains "event-worker") {
        Start-BackendProcess -Name "event-worker" -FilePath $venvPython -Arguments @("-m", "app.event_worker") -WorkingDirectory $repoRoot
    }
    if ($servicesToStart -contains "news-worker") {
        Start-BackendProcess -Name "news-worker" -FilePath $venvPython -Arguments @("-m", "app.news_worker") -WorkingDirectory $repoRoot
    }
    if ($servicesToStart -contains "api") {
        if ($runningNames -contains "research") {
            Wait-HttpReady "research" "http://127.0.0.1:${researchPort}/ready"
        }
        Start-BackendProcess -Name "api" -FilePath $apiBinary -WorkingDirectory $repoRoot
        Wait-HttpReady "api" "http://127.0.0.1:${apiPort}/ready"
    }
}
catch {
    Stop-NewProcesses
    throw
}

Write-Host "Requested services are ready: $($servicesToStart -join ', ')."
Write-Host "Logs: $logDirectory"
