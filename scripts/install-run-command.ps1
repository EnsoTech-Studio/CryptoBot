[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targetScript = Join-Path $repoRoot "backend.ps1"
$profilePath = $PROFILE
$startMarker = "# >>> CryptoBot run command >>>"
$endMarker = "# <<< CryptoBot run command <<<"
$escapedTarget = $targetScript.Replace("'", "''")
$profileBlock = @"
$startMarker
function global:run {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$Arguments)
    & '$escapedTarget' @Arguments
}
$endMarker
"@

if ($Remove) {
    if (Test-Path -LiteralPath $profilePath) {
        $existing = Get-Content -LiteralPath $profilePath -Raw
        $pattern = "(?s)\r?\n?$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))\r?\n?"
        $updated = [regex]::Replace($existing, $pattern, "")
        if ($updated -ne $existing) {
            Set-Content -LiteralPath $profilePath -Value $updated -Encoding UTF8
        }
    }
    Remove-Item -Path Function:\global:run -ErrorAction SilentlyContinue
    Write-Host "Removed the CryptoBot 'run' command from the PowerShell profile."
    return
}

if (-not (Test-Path -LiteralPath $profilePath)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $profilePath) | Out-Null
    New-Item -ItemType File -Force -Path $profilePath | Out-Null
}

$existing = Get-Content -LiteralPath $profilePath -Raw
if ($existing -notmatch [regex]::Escape($startMarker)) {
    Add-Content -LiteralPath $profilePath -Value ("`r`n" + $profileBlock) -Encoding UTF8
}

$functionBody = [scriptblock]::Create(
    "param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$Arguments)`n& '$escapedTarget' @Arguments"
)
Set-Item -Path Function:\global:run -Value $functionBody
Write-Host "Installed the PowerShell command: run <command>"
Write-Host "Examples: run up | run api | run workers | run stop workers"
