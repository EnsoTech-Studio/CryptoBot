package lab

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"
)

type App struct {
	DB           *sql.DB
	AIServiceURL string
	Client       *http.Client
	Signer       *Signer
	StartedAt    time.Time
}

func NewApp(db *sql.DB, aiURL string, client *http.Client, signer *Signer) *App {
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	return &App{DB: db, AIServiceURL: strings.TrimRight(aiURL, "/"), Client: client, Signer: signer, StartedAt: time.Now().UTC()}
}

func (a *App) StartMarketClock(ctx context.Context) {
	ticker := time.NewTicker(20 * time.Second)
	go func() {
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				_ = RefreshRealMarket(ctx, a.DB)
				_ = CollectApprovedNews(ctx, a.DB)
				_ = AnalyzeNewsSentiment(ctx, a.DB, a.AIServiceURL)
			}
		}
	}()
}

func (a *App) Health() map[string]any {
	return map[string]any{"status": "ok", "service": "api", "time": time.Now().UTC()}
}

func (a *App) Ready(ctx context.Context) (map[string]any, int) {
	status := http.StatusOK
	dbOK := a.DB.PingContext(ctx) == nil
	if !dbOK {
		status = http.StatusServiceUnavailable
	}
	return map[string]any{
		"status": map[bool]string{true: "ready", false: "not_ready"}[dbOK],
		"checks": map[string]any{
			"database":  map[string]any{"ok": dbOK},
			"migration": map[string]any{"ok": dbOK},
			"ai":        map[string]any{"ok": true, "required_for_core": false},
		},
	}, status
}

func (a *App) Metrics(ctx context.Context) string {
	var jobsFailed, jobsQueued, experiments, leaderboard int
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM backtest_jobs WHERE status='failed'`).Scan(&jobsFailed)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM backtest_jobs WHERE status='queued'`).Scan(&jobsQueued)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM experiments`).Scan(&experiments)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM leaderboard_entries`).Scan(&leaderboard)
	return fmt.Sprintf(`# HELP cryptobot_backtest_jobs_failed_total Failed backtest jobs.
# TYPE cryptobot_backtest_jobs_failed_total counter
cryptobot_backtest_jobs_failed_total %d
# HELP cryptobot_backtest_jobs_queued Current queued backtest jobs.
# TYPE cryptobot_backtest_jobs_queued gauge
cryptobot_backtest_jobs_queued %d
# HELP cryptobot_experiments_total Experiments created.
# TYPE cryptobot_experiments_total gauge
cryptobot_experiments_total %d
# HELP cryptobot_leaderboard_entries_total Leaderboard entries.
# TYPE cryptobot_leaderboard_entries_total gauge
cryptobot_leaderboard_entries_total %d
`, jobsFailed, jobsQueued, experiments, leaderboard)
}

func (a *App) MarketPairs(ctx context.Context) ([]MarketPair, error) {
	rows, err := a.DB.QueryContext(ctx, `SELECT provider,symbol,base_asset,quote_asset,array_to_string(timeframes, ',') FROM market_pairs WHERE is_active ORDER BY provider,symbol`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var pairs []MarketPair
	for rows.Next() {
		var p MarketPair
		var timeframes string
		if err := rows.Scan(&p.Provider, &p.Symbol, &p.BaseAsset, &p.QuoteAsset, &timeframes); err != nil {
			return nil, err
		}
		p.Timeframes = strings.Split(timeframes, ",")
		pairs = append(pairs, p)
	}
	return pairs, rows.Err()
}

func (a *App) Candles(ctx context.Context, provider, symbol, timeframe string, limit int) ([]Candle, error) {
	return LoadCandles(ctx, a.DB, defaultString(provider, ProviderBinance), defaultString(symbol, SymbolETHUSDT), defaultString(timeframe, "5m"), limit)
}

func (a *App) ChartOverlayPayload(ctx context.Context, provider, symbol, timeframe, strategy string, limit int) (map[string]any, error) {
	candles, err := a.Candles(ctx, provider, symbol, timeframe, limit)
	if err != nil {
		return nil, err
	}
	if len(candles) == 0 {
		return nil, fmt.Errorf("no_candles_available")
	}
	if strategy == "" {
		strategy = "composite@1.0.0"
	}
	strategyID := strings.Split(strategy, "@")[0]
	series, markers := ChartOverlays(candles, strategyID)
	lastClosed := time.Now().UTC()
	seq := time.Now().Unix()
	if len(candles) > 0 {
		lastClosed = candles[len(candles)-1].OpenTime
		seq = candles[len(candles)-1].OpenTime.Unix()
	}
	isStale := false
	var checkpointStale sql.NullBool
	if err := a.DB.QueryRowContext(ctx, `
		SELECT is_stale FROM stream_checkpoints
		WHERE provider=$1 AND symbol=$2 AND timeframe=$3
	`, defaultString(provider, ProviderBinance), defaultString(symbol, SymbolETHUSDT), defaultString(timeframe, "5m")).Scan(&checkpointStale); err == nil && checkpointStale.Valid {
		isStale = checkpointStale.Bool
	}
	return map[string]any{
		"provider": defaultString(provider, ProviderBinance), "symbol": defaultString(symbol, SymbolETHUSDT), "timeframe": defaultString(timeframe, "5m"),
		"strategy": strategy, "config_hash": "sha256:" + strings.Repeat("4", 64),
		"range":          map[string]any{"from": candles[0].OpenTime, "to": candles[len(candles)-1].OpenTime},
		"warmup_candles": 60, "first_valid_at": candles[min(60, len(candles)-1)].OpenTime,
		"last_closed_at": lastClosed, "is_stale": isStale, "seq": seq,
		"series": series, "markers": markers, "gaps": []any{},
	}, nil
}

func (a *App) Strategies(ctx context.Context) ([]StrategyDefinition, error) {
	rows, err := a.DB.QueryContext(ctx, `
		SELECT strategy_id,version,COALESCE(family,''),display_name,description,parameters_schema,input_requirements,overlay_types,warm_up_candles,is_composite,code_fingerprint
		FROM strategy_versions ORDER BY is_composite, family, strategy_id
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []StrategyDefinition
	for rows.Next() {
		var s StrategyDefinition
		var params, inputs, overlays []byte
		if err := rows.Scan(&s.StrategyID, &s.Version, &s.Family, &s.DisplayName, &s.Description, &params, &inputs, &overlays, &s.WarmUpCandles, &s.IsComposite, &s.CodeFingerprint); err != nil {
			return nil, err
		}
		_ = json.Unmarshal(params, &s.ParametersSchema)
		_ = json.Unmarshal(inputs, &s.InputRequirements)
		_ = json.Unmarshal(overlays, &s.OverlayTypes)
		list = append(list, s)
	}
	return list, rows.Err()
}

func (a *App) CreateExperiment(ctx context.Context, ownerID string, req ExperimentRequest) (AcceptedRun, error) {
	return CreateExperiment(ctx, a.DB, ownerID, req, 100)
}

func (a *App) ExperimentSummary(ctx context.Context, id string, principal *Principal) (ExperimentSummary, error) {
	var s ExperimentSummary
	var defJSON, riskJSON []byte
	var metrics Metrics
	var metricNullable = struct {
		total, win, mdd, pf, sharpe, score sql.NullFloat64
		trades                             sql.NullInt64
		evaluator                          sql.NullString
	}{}
	var started, finished sql.NullTime
	var errCode sql.NullString
	var owner string
	err := a.DB.QueryRowContext(ctx, `
		SELECT e.id, COALESCE(br.id,''), COALESCE(br.status,'queued'), e.owner_id, e.provider,e.symbol,e.timeframe,e.strategy_id,e.strategy_version,e.candidate_hash,e.dataset_version,e.content_hash,e.created_at,br.started_at,br.finished_at,COALESCE(br.candles_read,0),COALESCE(br.signals_count,0),e.candidate_definition,COALESCE(e.risk_policy,'{}'::jsonb),br.error_code,
		       ev.total_return_pct::float8, ev.win_rate_pct::float8, ev.max_drawdown_pct::float8, ev.trade_count, ev.profit_factor::float8, ev.sharpe_ratio::float8, ev.score::float8, ev.evaluator_version
		FROM experiments e
		LEFT JOIN backtest_runs br ON br.experiment_id=e.id
		LEFT JOIN evaluations ev ON ev.experiment_id=e.id
		WHERE e.id=$1
	`, id).Scan(&s.ID, &s.RunID, &s.Status, &owner, &s.Provider, &s.Symbol, &s.Timeframe, &s.StrategyID, &s.StrategyVersion, &s.CandidateHash, &s.DatasetVersion, &s.ContentHash, &s.CreatedAt, &started, &finished, &s.CandlesRead, &s.SignalsCount, &defJSON, &riskJSON, &errCode, &metricNullable.total, &metricNullable.win, &metricNullable.mdd, &metricNullable.trades, &metricNullable.pf, &metricNullable.sharpe, &metricNullable.score, &metricNullable.evaluator)
	if err != nil {
		return s, err
	}
	if principal != nil && owner != principal.ID && principal.Role != "OPERATOR" && principal.Role != "ADMIN" {
		return s, sql.ErrNoRows
	}
	_ = json.Unmarshal(defJSON, &s.CandidateDefinition)
	var risk map[string]any
	_ = json.Unmarshal(riskJSON, &risk)
	if started.Valid {
		s.StartedAt = &started.Time
	}
	if finished.Valid {
		s.FinishedAt = &finished.Time
	}
	if errCode.Valid {
		s.ErrorCode = &errCode.String
	}
	s.Execution = map[string]any{"fill_policy": "bbo_limit", "position_policy": "one_net_position", "initial_equity": 100, "fixed_notional": 10, "fee_bps": 10, "slippage_bps": 0, "risk_policy": risk}
	if metricNullable.total.Valid {
		metrics.TotalReturnPct = metricNullable.total.Float64
		metrics.WinRatePct = metricNullable.win.Float64
		metrics.MaxDrawdownPct = metricNullable.mdd.Float64
		metrics.TradeCount = int(metricNullable.trades.Int64)
		metrics.ProfitFactor = metricNullable.pf.Float64
		metrics.SharpeRatio = metricNullable.sharpe.Float64
		metrics.Score = metricNullable.score.Float64
		metrics.EvaluatorVersion = metricNullable.evaluator.String
		s.Metrics = &metrics
	}
	return s, nil
}

func (a *App) ExperimentCandles(ctx context.Context, id string) ([]Candle, error) {
	var provider, symbol, timeframe string
	if err := a.DB.QueryRowContext(ctx, `SELECT provider,symbol,timeframe FROM experiments WHERE id=$1`, id).Scan(&provider, &symbol, &timeframe); err != nil {
		return nil, err
	}
	return LoadCandles(ctx, a.DB, provider, symbol, timeframe, 220)
}

func (a *App) ExperimentTrades(ctx context.Context, id string) ([]Trade, error) {
	rows, err := a.DB.QueryContext(ctx, `SELECT id,sequence_no,side,entry_time,exit_time,entry_price::float8,exit_price::float8,quantity::float8,pnl::float8,pnl_pct::float8,exit_reason,signal_t,child_signals FROM trades WHERE experiment_id=$1 ORDER BY sequence_no`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var trades []Trade
	for rows.Next() {
		var t Trade
		var child []byte
		if err := rows.Scan(&t.ID, &t.SequenceNo, &t.Side, &t.EntryTime, &t.ExitTime, &t.EntryPrice, &t.ExitPrice, &t.Quantity, &t.PnL, &t.PnLPct, &t.ExitReason, &t.SignalT, &child); err != nil {
			return nil, err
		}
		_ = json.Unmarshal(child, &t.ChildSignals)
		trades = append(trades, t)
	}
	return trades, rows.Err()
}

func (a *App) ExperimentEquity(ctx context.Context, id string) (map[string]any, error) {
	rows, err := a.DB.QueryContext(ctx, `SELECT t,equity::float8,drawdown_pct::float8 FROM equity_points WHERE experiment_id=$1 ORDER BY t`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var points []EquityPoint
	minDD := EquityPoint{DrawdownPct: 0}
	for rows.Next() {
		var p EquityPoint
		if err := rows.Scan(&p.T, &p.Equity, &p.DrawdownPct); err != nil {
			return nil, err
		}
		if p.DrawdownPct < minDD.DrawdownPct {
			minDD = p
		}
		points = append(points, p)
	}
	return map[string]any{"points": points, "max_drawdown": minDD, "decimation": map[string]any{"original_count": len(points), "returned_count": len(points), "stride": 1}}, rows.Err()
}

func (a *App) ExperimentOverlays(ctx context.Context, id string) (map[string]any, error) {
	candles, err := a.ExperimentCandles(ctx, id)
	if err != nil {
		return nil, err
	}
	series, markers := ChartOverlays(candles, "composite")
	trades, _ := a.ExperimentTrades(ctx, id)
	summary, _ := a.ExperimentSummary(ctx, id, nil)
	risk, _ := summary.Execution["risk_policy"].(map[string]any)
	stopLossPct, hasStopLoss := numberFromMap(risk, "stop_loss_pct")
	takeProfitPct, hasTakeProfit := numberFromMap(risk, "take_profit_pct")
	execMarkers := make([]map[string]any, 0, len(trades)*4)
	for _, t := range trades {
		execMarkers = append(execMarkers, map[string]any{"t": t.EntryTime, "overlay_type": "entry", "trade_id": t.ID, "price": t.EntryPrice, "signal_t": t.SignalT})
		if hasTakeProfit {
			execMarkers = append(execMarkers, map[string]any{"t": t.EntryTime, "line_until": t.ExitTime, "overlay_type": "take_profit", "trade_id": t.ID, "price": t.EntryPrice * (1 + takeProfitPct/100)})
		}
		if hasStopLoss {
			execMarkers = append(execMarkers, map[string]any{"t": t.EntryTime, "line_until": t.ExitTime, "overlay_type": "stop_loss", "trade_id": t.ID, "price": t.EntryPrice * (1 - stopLossPct/100)})
		}
		execMarkers = append(execMarkers, map[string]any{"t": t.ExitTime, "overlay_type": "exit", "trade_id": t.ID, "price": t.ExitPrice, "exit_reason": t.ExitReason})
	}
	return map[string]any{"series": series, "signal_markers": markers, "execution_markers": execMarkers}, nil
}

func (a *App) Leaderboard(ctx context.Context, limit int, sortBy string) ([]LeaderboardEntry, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}
	order := "le.score DESC"
	switch sortBy {
	case "return":
		order = "ev.total_return_pct DESC"
	case "win_rate":
		order = "ev.win_rate_pct DESC"
	case "mdd":
		order = "ev.max_drawdown_pct DESC"
	case "sharpe":
		order = "ev.sharpe_ratio DESC"
	}
	rows, err := a.DB.QueryContext(ctx, fmt.Sprintf(`
		SELECT le.id, le.score::float8, e.strategy_id,e.strategy_version,e.candidate_hash,e.dataset_version,ev.total_return_pct::float8,ev.win_rate_pct::float8,ev.max_drawdown_pct::float8,ev.sharpe_ratio::float8,ev.trade_count,le.observed_at
		FROM leaderboard_entries le
		JOIN evaluations ev ON ev.id=le.evaluation_id
		JOIN experiments e ON e.id=le.experiment_id
		ORDER BY %s, le.observed_at DESC LIMIT $1
	`, order), limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var entries []LeaderboardEntry
	rank := 1
	for rows.Next() {
		var e LeaderboardEntry
		if err := rows.Scan(&e.ID, &e.Score, &e.StrategyID, &e.StrategyVersion, &e.CandidateHash, &e.DatasetVersion, &e.TotalReturnPct, &e.WinRatePct, &e.MaxDrawdownPct, &e.SharpeRatio, &e.TradeCount, &e.ObservedAt); err != nil {
			return nil, err
		}
		e.Rank = rank
		rank++
		entries = append(entries, e)
	}
	return entries, rows.Err()
}

func (a *App) Provenance(ctx context.Context, entryID string) (map[string]any, error) {
	var experimentID string
	if err := a.DB.QueryRowContext(ctx, `SELECT experiment_id FROM leaderboard_entries WHERE id=$1`, entryID).Scan(&experimentID); err != nil {
		return nil, err
	}
	summary, err := a.ExperimentSummary(ctx, experimentID, nil)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"leaderboard_entry_id": entryID,
		"score":                summary.Metrics,
		"experiment":           summary,
		"strategy_versions":    summary.CandidateDefinition,
		"dataset":              map[string]any{"dataset_version": summary.DatasetVersion, "provider": summary.Provider, "symbol": summary.Symbol, "timeframe": summary.Timeframe, "content_hash": summary.ContentHash},
		"execution":            summary.Execution,
		"score_policy_version": "v1",
	}, nil
}

func (a *App) News(ctx context.Context) (map[string]any, error) {
	rows, err := a.DB.QueryContext(ctx, `
		SELECT ni.id, ni.title, ni.url, ni.published_at, ns.source_key, ns.display_name, array_to_string(ni.related_coins, ','),
		       sr.label, sr.score::float8, sr.model, sr.model_version, sr.analyzed_at
		FROM news_items ni
		JOIN news_sources ns ON ns.id=ni.source_id
		LEFT JOIN sentiment_results sr ON sr.news_item_id=ni.id
		ORDER BY ni.published_at DESC LIMIT 50
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var items []NewsItem
	var last time.Time
	for rows.Next() {
		var item NewsItem
		var label, model, version sql.NullString
		var score sql.NullFloat64
		var analyzed sql.NullTime
		var sourceKey, display, coins string
		if err := rows.Scan(&item.ID, &item.Title, &item.URL, &item.PublishedAt, &sourceKey, &display, &coins, &label, &score, &model, &version, &analyzed); err != nil {
			return nil, err
		}
		item.Source = map[string]any{"key": sourceKey, "display_name": display}
		if coins != "" {
			item.RelatedCoins = strings.Split(coins, ",")
		}
		if label.Valid {
			item.Sentiment = &SentimentResult{Label: label.String, Score: score.Float64, Model: model.String, ModelVersion: version.String, AnalyzedAt: analyzed.Time}
		}
		if item.PublishedAt.After(last) {
			last = item.PublishedAt
		}
		items = append(items, item)
	}
	return map[string]any{"items": items, "meta": map[string]any{"total": len(items), "page": 1, "limit": 50, "last_collected_at": last}}, rows.Err()
}

func (a *App) NewsAggregate(ctx context.Context) (map[string]any, error) {
	var pos, neu, neg, total, analyzed int
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM news_items`).Scan(&total)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM sentiment_results`).Scan(&analyzed)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM sentiment_results WHERE label='POSITIVE'`).Scan(&pos)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM sentiment_results WHERE label='NEUTRAL'`).Scan(&neu)
	_ = a.DB.QueryRowContext(ctx, `SELECT count(*) FROM sentiment_results WHERE label='NEGATIVE'`).Scan(&neg)
	avg := 0.0
	if analyzed > 0 {
		avg = float64(pos-neg) / float64(analyzed)
	}
	now := time.Now().UTC()
	return map[string]any{
		"window":       map[string]any{"from": now.Add(-6 * time.Hour), "to": now, "window_sec": 21600},
		"model":        map[string]any{"model": "sentiment-v1", "model_version": "2026-08-01"},
		"distribution": map[string]int{"POSITIVE": pos, "NEUTRAL": neu, "NEGATIVE": neg},
		"avg_score":    round(avg),
		"coverage":     map[string]int{"items_total": total, "items_analyzed": analyzed, "items_unanalyzed": total - analyzed},
	}, nil
}

func (a *App) Predict(ctx context.Context, text string) (map[string]any, int) {
	body, _ := json.Marshal(map[string]string{"text": text})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.AIServiceURL+"/predict", bytes.NewReader(body))
	if err != nil {
		return errorBody("sentiment_unavailable", "AI service URL is invalid"), http.StatusBadGateway
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := a.Client.Do(req)
	if err != nil {
		return errorBody("sentiment_unavailable", "AI service is unavailable"), http.StatusBadGateway
	}
	defer res.Body.Close()
	data, _ := io.ReadAll(res.Body)
	var payload map[string]any
	_ = json.Unmarshal(data, &payload)
	if res.StatusCode >= 300 {
		return errorBody("sentiment_unavailable", "AI service returned an error"), http.StatusBadGateway
	}
	if _, ok := payload["model_version"]; !ok {
		payload["model_version"] = "2026-08-01"
	}
	return payload, http.StatusOK
}

func (a *App) SearchRun(ctx context.Context, id string, principal *Principal) (map[string]any, error) {
	row := a.DB.QueryRowContext(ctx, `SELECT id,owner_id,generator_id,status,generated,tested,failed,best_score,current_candidate,stop_conditions,dataset_version,content_hash,created_at,updated_at,stop_reason FROM search_runs WHERE id=$1`, id)
	var owner, generator, status, current, dataset, hash string
	var generated, tested, failed int
	var best sql.NullFloat64
	var stop []byte
	var created, updated time.Time
	var stopReason sql.NullString
	if err := row.Scan(&id, &owner, &generator, &status, &generated, &tested, &failed, &best, &current, &stop, &dataset, &hash, &created, &updated, &stopReason); err != nil {
		return nil, err
	}
	if principal != nil && owner != principal.ID && principal.Role != "OPERATOR" && principal.Role != "ADMIN" {
		return nil, sql.ErrNoRows
	}
	var stopMap map[string]any
	_ = json.Unmarshal(stop, &stopMap)
	var bestValue any
	if best.Valid {
		bestValue = best.Float64
	}
	return map[string]any{
		"search_run_id": id, "generator_id": generator, "status": status,
		"candidates": map[string]int{"generated": generated, "tested": tested, "failed": failed},
		"best_score": bestValue, "current_candidate": current, "stop_conditions": stopMap,
		"stop_reason": nullableString(stopReason), "dataset": map[string]any{"dataset_version": dataset, "content_hash": hash},
		"created_at": created, "updated_at": updated,
	}, nil
}

func (a *App) SearchAction(ctx context.Context, id string, principal Principal, action, commandID string) (map[string]any, int) {
	if commandID == "" {
		commandID = uuid.NewString()
	}
	valid := map[string]string{"pause": "paused", "resume": "running", "cancel": "cancelled"}
	next, ok := valid[action]
	if !ok {
		return errorBody("invalid_action", "Unsupported search action"), http.StatusUnprocessableEntity
	}
	tx, err := a.DB.BeginTx(ctx, nil)
	if err != nil {
		return errorBody("transaction_failed", err.Error()), http.StatusInternalServerError
	}
	defer tx.Rollback()
	var owner, current string
	if err := tx.QueryRowContext(ctx, `SELECT owner_id,status FROM search_runs WHERE id=$1 FOR UPDATE`, id).Scan(&owner, &current); err != nil {
		return errorBody("not_found", "Search run not found"), http.StatusNotFound
	}
	if owner != principal.ID && principal.Role != "OPERATOR" && principal.Role != "ADMIN" {
		return errorBody("not_found", "Search run not found"), http.StatusNotFound
	}
	if current == "completed" || current == "failed" || current == "cancelled" {
		return errorBody("invalid_transition", "Search run is terminal"), http.StatusConflict
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO search_actions(command_id,search_run_id,action,actor_id,resulted_in) VALUES($1,$2,$3,$4,$5) ON CONFLICT(command_id) DO NOTHING`, commandID, id, action, principal.ID, next); err != nil {
		return errorBody("action_failed", err.Error()), http.StatusInternalServerError
	}
	if _, err := tx.ExecContext(ctx, `UPDATE search_runs SET status=$1, updated_at=now(), stop_reason=CASE WHEN $1='cancelled' THEN 'cancelled_by_user' ELSE stop_reason END WHERE id=$2`, next, id); err != nil {
		return errorBody("action_failed", err.Error()), http.StatusInternalServerError
	}
	if action == "cancel" {
		if _, err := tx.ExecContext(ctx, `
			UPDATE backtest_jobs bj
			SET status='cancelled', completed_at=now(), last_error='cancelled_by_user'
			FROM experiments e
			WHERE bj.experiment_id=e.id AND e.search_run_id=$1 AND bj.status IN ('queued','leased')
		`, id); err != nil {
			return errorBody("action_failed", err.Error()), http.StatusInternalServerError
		}
		if _, err := tx.ExecContext(ctx, `
			UPDATE backtest_runs br
			SET status='cancelled', finished_at=now(), error_code='cancelled_by_user'
			FROM experiments e
			WHERE br.experiment_id=e.id AND e.search_run_id=$1 AND br.status IN ('queued','running')
		`, id); err != nil {
			return errorBody("action_failed", err.Error()), http.StatusInternalServerError
		}
	}
	if err := tx.Commit(); err != nil {
		return errorBody("action_failed", err.Error()), http.StatusInternalServerError
	}
	return map[string]any{"search_run_id": id, "status": next, "command_id": commandID}, http.StatusOK
}

func (a *App) ClaimAndRunOne(ctx context.Context, workerID string) (bool, error) {
	token := uuid.NewString()
	var jobID, experimentID string
	err := a.DB.QueryRowContext(ctx, `
		UPDATE backtest_jobs SET status='leased', leased_by=$1, lease_token=$2, lease_expires_at=now()+interval '120 seconds', attempt=attempt+1
		WHERE id = (
			SELECT bj.id
			FROM backtest_jobs bj
			JOIN experiments e ON e.id=bj.experiment_id
			WHERE bj.status='queued'
			  AND NOT EXISTS (
			    SELECT 1 FROM search_runs sr
			    WHERE sr.id=e.search_run_id AND sr.status IN ('paused','cancelled')
			  )
			ORDER BY bj.priority, bj.enqueued_at
			LIMIT 1 FOR UPDATE OF bj SKIP LOCKED
		)
		RETURNING id, experiment_id
	`, workerID, token).Scan(&jobID, &experimentID)
	if err == sql.ErrNoRows {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if err := RunExperimentNow(ctx, a.DB, experimentID, workerID); err != nil {
		_ = failExperiment(ctx, a.DB, experimentID, "worker_failed", err.Error())
		return true, err
	}
	return true, nil
}

func (a *App) LatestKlinePayload(ctx context.Context, subscriptionKey string) (map[string]any, map[string]any, error) {
	parts := strings.Split(subscriptionKey, "|")
	provider, symbol, timeframe, strategy := ProviderBinance, SymbolETHUSDT, "5m", "composite@1.0.0"
	if len(parts) >= 3 {
		provider, symbol, timeframe = parts[0], parts[1], parts[2]
	}
	if len(parts) >= 4 {
		strategy = parts[3]
	}
	candles, err := LoadCandles(ctx, a.DB, provider, symbol, timeframe, 90)
	if err != nil || len(candles) == 0 {
		return nil, nil, err
	}
	c := candles[len(candles)-1]
	key := subscriptionKey
	if key == "" {
		key = fmt.Sprintf("%s|%s|%s|%s|sha256:%s", provider, symbol, timeframe, strategy, strings.Repeat("4", 64))
	}
	kline := map[string]any{"type": "kline", "key": key, "seq": c.OpenTime.Unix(), "final": true, "kline": map[string]any{
		"open_time": c.OpenTime, "close_time": c.CloseTime, "open": fmt.Sprintf("%.4f", c.Open), "high": fmt.Sprintf("%.4f", c.High), "low": fmt.Sprintf("%.4f", c.Low), "close": fmt.Sprintf("%.4f", c.Close), "volume": fmt.Sprintf("%.4f", c.Volume),
	}}
	series, markers := ChartOverlays(candles, strings.Split(strategy, "@")[0])
	delta := map[string]any{"type": "overlay_delta", "key": key, "seq": c.OpenTime.Unix(), "revised_from": candles[max(0, len(candles)-20)].OpenTime, "series": tailSeries(series), "markers": markers}
	return kline, delta, nil
}

func tailSeries(series []OverlaySeries) []OverlaySeries {
	out := make([]OverlaySeries, 0, len(series))
	for _, s := range series {
		if len(s.Points) > 0 {
			start := max(0, len(s.Points)-2)
			s.Points = s.Points[start:]
		}
		out = append(out, s)
	}
	return out
}

func errorBody(code, message string) map[string]any {
	return map[string]any{"error": map[string]any{"code": code, "message": message, "request_id": "req_" + uuid.NewString()[:8]}}
}

func nullableString(v sql.NullString) any {
	if v.Valid {
		return v.String
	}
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func SortLeaderboardForDisplay(entries []LeaderboardEntry) {
	sort.SliceStable(entries, func(i, j int) bool { return entries[i].Score > entries[j].Score })
	for i := range entries {
		entries[i].Rank = i + 1
	}
}
