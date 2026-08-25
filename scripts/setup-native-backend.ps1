[CmdletBinding()]
param(
    [switch]$SkipDevDependencies
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDirectory = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
$go = Get-Command "go" -ErrorAction SilentlyContinue
if ($null -eq $go) {
    throw "Go 1.23 is required on PATH before setting up the native backend."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        & $pyLauncher.Source -3.12 -c "import sys; print(sys.version)" *> $null
        if ($LASTEXITCODE -eq 0) {
            Invoke-Checked $pyLauncher.Source @("-3.12", "-m", "venv", $venvDirectory)
        }
        else {
            Invoke-Checked $pyLauncher.Source @("-3", "-m", "venv", $venvDirectory)
        }
    }
    else {
        $python = Get-Command "python" -ErrorAction Stop
        Invoke-Checked $python.Source @("-m", "venv", $venvDirectory)
    }
}

Invoke-Checked $venvPython @("-c", "import sys; assert sys.version_info >= (3, 12), sys.version")
Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $venvPython @(
    "-m", "pip", "install",
    "-r", (Join-Path $repoRoot "requirements.txt"),
    "-r", (Join-Path $repoRoot "ai\requirements.txt")
)

if (-not $SkipDevDependencies) {
    Invoke-Checked $venvPython @(
        "-m", "pip", "install",
        "-r", (Join-Path $repoRoot "requirements-dev.txt"),
        "-r", (Join-Path $repoRoot "ai\requirements-dev.txt")
    )
}

Push-Location (Join-Path $repoRoot "server")
try {
    Invoke-Checked $go.Source @("mod", "download")
}
finally {
    Pop-Location
}

Write-Host "Native backend dependencies are ready."
Write-Host "Next: docker compose up -d"
Write-Host "Then: powershell -ExecutionPolicy Bypass -File scripts/start-native-backend.ps1"
