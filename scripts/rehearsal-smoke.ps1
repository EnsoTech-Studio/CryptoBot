param(
    [string]$ApiBaseUrl = "http://127.0.0.1:18081",
    [string]$WebBaseUrl = "http://127.0.0.1:13000",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$origin = $WebBaseUrl.Replace("127.0.0.1", "localhost")
$csrf = $null

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [switch]$Command
    )
    $headers = @{ Origin = $origin; "X-Request-ID" = [guid]::NewGuid().ToString() }
    if ($Command) {
        $headers["X-CSRF-Token"] = $script:csrf
        $headers["Idempotency-Key"] = [guid]::NewGuid().ToString()
    }
    $parameters = @{
        Uri = "$ApiBaseUrl$Path"
        Method = $Method
        WebSession = $session
        Headers = $headers
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json"
        $parameters.Body = $Body | ConvertTo-Json -Depth 12 -Compress
    }
    $response = Invoke-WebRequest @parameters
    $payload = if ($response.Content) { $response.Content | ConvertFrom-Json } else { $null }
    return [pscustomobject]@{ StatusCode = [int]$response.StatusCode; Payload = $payload }
}

function Wait-ForTerminal {
    param([string]$Path)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $current = Invoke-Api -Method Get -Path $Path
        if ($current.Payload.status -in @("completed", "failed", "cancelled")) {
            return $current.Payload
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for terminal state: $Path"
}

$web = Invoke-WebRequest -Uri $WebBaseUrl -UseBasicParsing
$health = Invoke-Api -Method Get -Path "/health"
$ready = Invoke-Api -Method Get -Path "/ready"
if ($web.StatusCode -ne 200 -or $health.StatusCode -ne 200 -or $ready.StatusCode -ne 200) {
    throw "Web/API health or readiness check failed"
}

$email = "rehearsal-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())@example.test"
$registration = Invoke-Api -Method Post -Path "/api/v1/auth/register" -Body @{
    email = $email
    password = "CorrectHorseBatteryStaple!"
    display_name = "Rehearsal User"
}
if ($registration.StatusCode -ne 201) { throw "Registration failed" }
$csrfCookie = $session.Cookies.GetCookies($ApiBaseUrl)["csrf_token"]
if ($null -eq $csrfCookie) { throw "CSRF cookie was not issued" }
$csrf = $csrfCookie.Value

$me = Invoke-Api -Method Get -Path "/api/v1/auth/me"
$pairs = Invoke-Api -Method Get -Path "/api/v1/markets/pairs"
$datasets = Invoke-Api -Method Get -Path "/api/v1/markets/datasets?provider=binance_usdm&symbol=ETHUSDT&timeframe=5m"
$strategies = Invoke-Api -Method Get -Path "/api/v1/strategies"
if ($datasets.Payload.datasets.Count -lt 1) { throw "No immutable 5m dataset available" }
$datasetVersion = $datasets.Payload.datasets[0].dataset_version

$experimentResponse = Invoke-Api -Method Post -Path "/api/v1/experiments" -Command -Body @{
    dataset_version = $datasetVersion
    provider = "binance_usdm"
    symbol = "ETHUSDT"
    timeframe = "5m"
    strategy_id = "ma_cross"
    strategy_version = "v1"
    initial_equity = 100
    fixed_notional = 10
    leverage = 1
    fee_bps = 10
    slippage_bps = 0
    intrabar_priority = "stop_loss_first"
    idempotency_key = "rehearsal-experiment-$([guid]::NewGuid())"
}
if ($experimentResponse.StatusCode -notin @(200, 202)) { throw "Experiment command failed" }
$experimentId = $experimentResponse.Payload.experiment_id
$experiment = Wait-ForTerminal -Path "/api/v1/experiments/$experimentId"
if ($experiment.status -ne "completed" -or -not $experiment.result_hash) {
    throw "Experiment did not complete with provenance"
}
$candles = Invoke-Api -Method Get -Path "/api/v1/experiments/$experimentId/candles"
$trades = Invoke-Api -Method Get -Path "/api/v1/experiments/$experimentId/trades"
$equity = Invoke-Api -Method Get -Path "/api/v1/experiments/$experimentId/equity"
$overlays = Invoke-Api -Method Get -Path "/api/v1/experiments/$experimentId/overlays"

$searchResponse = Invoke-Api -Method Post -Path "/api/v1/search-runs" -Command -Body @{
    generator_id = "domain_guided"
    search_space = @{
        strategy_ids = @("ma_cross", "rsi")
        cardinality = @(2)
        policies = @("weighted_vote")
        parameter_grid = @{
            ma_cross = @{ fast = @(10, 20); slow = @(30, 50) }
            rsi = @{ period = @(14); buy_below = @(30); sell_above = @(70) }
        }
    }
    stop_conditions = @{ max_candidates = 2; max_duration_sec = 300; max_non_improving = 2 }
    market = @{
        provider = "binance_usdm"
        symbol = "ETHUSDT"
        timeframe = "5m"
        dataset_version = $datasetVersion
        range_from = "2026-01-01T00:00:00Z"
        range_to = "2026-01-02T00:00:00Z"
    }
    execution = @{}
    seed = 7
    idempotency_key = "rehearsal-search-$([guid]::NewGuid())"
}
if ($searchResponse.StatusCode -notin @(200, 202)) { throw "Search command failed" }
$search = Wait-ForTerminal -Path "/api/v1/search-runs/$($searchResponse.Payload.search_run_id)"
if ($search.status -ne "completed") { throw "Search did not complete" }

$leaderboard = Invoke-Api -Method Get -Path "/api/v1/leaderboard?dataset_version=$([uri]::EscapeDataString($datasetVersion))"
$news = Invoke-Api -Method Get -Path "/api/v1/news"
$newsAggregate = Invoke-Api -Method Get -Path "/api/v1/news/aggregate"
$prediction = Invoke-Api -Method Post -Path "/api/v1/ai/predict" -Command -Body @{
    text = "Ethereum adoption and market demand are improving."
}
if ($prediction.StatusCode -ne 200) { throw "Sentiment inference failed" }

$refresh = Invoke-Api -Method Post -Path "/api/v1/auth/refresh" -Command
if ($refresh.StatusCode -ne 200) { throw "Refresh-token rotation failed" }
$csrf = $session.Cookies.GetCookies($ApiBaseUrl)["csrf_token"].Value
$logout = Invoke-Api -Method Post -Path "/api/v1/auth/logout" -Command
if ($logout.StatusCode -ne 200) { throw "Logout failed" }
$sessionRejected = $false
try {
    Invoke-Api -Method Get -Path "/api/v1/auth/me" | Out-Null
} catch {
    $sessionRejected = [int]$_.Exception.Response.StatusCode -eq 401
}
if (-not $sessionRejected) { throw "Logged-out session was still accepted" }

[ordered]@{
    web_status = [int]$web.StatusCode
    readiness = $ready.Payload.ready
    user_id = $me.Payload.user.id
    pair_count = $pairs.Payload.pairs.Count
    strategy_count = $strategies.Payload.strategies.Count
    dataset_version = $datasetVersion
    experiment_id = $experimentId
    experiment_status = $experiment.status
    result_hash = $experiment.result_hash
    candle_count = $candles.Payload.candles.Count
    trade_count = $trades.Payload.trades.Count
    equity_points = $equity.Payload.equity.Count
    overlay_points = $overlays.Payload.overlays.Count
    search_status = $search.status
    search_generated = $search.generated
    search_tested = $search.tested
    leaderboard_entries = $leaderboard.Payload.entries.Count
    news_items = $news.Payload.items.Count
    sentiment_coverage = $newsAggregate.Payload.coverage
    prediction_model = $prediction.Payload.model
    prediction_version = $prediction.Payload.model_version
    refresh_rotation = $refresh.StatusCode -eq 200
    logout_revocation = $sessionRejected
} | ConvertTo-Json -Depth 8
