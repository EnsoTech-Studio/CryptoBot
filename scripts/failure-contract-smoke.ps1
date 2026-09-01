[CmdletBinding()]
param(
    [switch]$IncludeIntegration
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    # These cases prove lease fencing, retry/isolation, outbox idempotency and
    # unavailable-AI honesty without stopping a developer's running stack.
    $tests = @(
        "tests/test_backtest_worker.py",
        "tests/test_agent_orchestrator.py",
        "tests/test_news_sentiment.py",
        "tests/test_adaptive_news.py"
    )
    & uv run pytest @tests -q
    if ($LASTEXITCODE -ne 0) {
        throw "Failure contract tests failed with exit code $LASTEXITCODE."
    }
    if ($IncludeIntegration) {
        & uv run pytest tests/integration/test_queue_integration.py -q
        if ($LASTEXITCODE -ne 0) {
            throw "Failure integration tests failed with exit code $LASTEXITCODE."
        }
    }
}
finally {
    Pop-Location
}
