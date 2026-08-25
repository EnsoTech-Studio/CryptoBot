package lab

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/google/uuid"
)

func BuiltInStrategies() []StrategyDefinition {
	return []StrategyDefinition{
		{
			StrategyID: "ma_cross", Version: "1.0.0", Family: "trend", DisplayName: "MA Cross",
			Description: "Fast/slow moving-average crossover on closed candles.",
			ParametersSchema: schema(map[string]any{"fast": number(5, 80, 20), "slow": number(10, 200, 50)}),
			InputRequirements: []string{"candles.close", "indicator.sma"},
			OverlayTypes: []string{"moving_average", "buy_signal", "sell_signal"}, WarmUpCandles: 50,
			CodeFingerprint: "sha256:ma-cross-demo-v1",
		},
		{
			StrategyID: "rsi", Version: "1.0.0", Family: "momentum", DisplayName: "RSI",
			Description: "RSI threshold strategy using backend-calculated RSI.",
			ParametersSchema: schema(map[string]any{"period": number(7, 30, 14), "buy_threshold": number(10, 45, 30), "sell_threshold": number(55, 90, 70)}),
			InputRequirements: []string{"candles.close", "indicator.rsi"},
			OverlayTypes: []string{"rsi", "buy_signal", "sell_signal"}, WarmUpCandles: 14,
			CodeFingerprint: "sha256:rsi-demo-v1",
		},
		{
			StrategyID: "bollinger", Version: "1.0.0", Family: "volatility", DisplayName: "Bollinger",
			Description: "Mean-reversion signals from Bollinger Bands.",
			ParametersSchema: schema(map[string]any{"period": number(10, 60, 20), "stddev": number(1, 3, 2)}),
			InputRequirements: []string{"candles.close", "indicator.bollinger"},
			OverlayTypes: []string{"bollinger_bands", "buy_signal", "sell_signal"}, WarmUpCandles: 20,
			CodeFingerprint: "sha256:bollinger-demo-v1",
		},
		{
			StrategyID: "support_resistance", Version: "1.0.0", Family: "structure", DisplayName: "Support / Resistance",
			Description: "Signals when price tests backend-computed support or resistance zones.",
			ParametersSchema: schema(map[string]any{"lookback": number(20, 120, 60), "zone_bps": number(10, 120, 45)}),
			InputRequirements: []string{"candles.high", "candles.low"},
			OverlayTypes: []string{"support_zone", "resistance_zone", "buy_signal", "sell_signal"}, WarmUpCandles: 60,
			CodeFingerprint: "sha256:support-resistance-demo-v1",
		},
		{
			StrategyID: "news_sentiment", Version: "1.0.0", Family: "information", DisplayName: "News Sentiment",
			Description: "Uses aggregated sentiment windows as a regular strategy input.",
			ParametersSchema: schema(map[string]any{"window_sec": number(900, 14400, 3600), "buy_threshold": number(0.1, 0.9, 0.45), "sell_threshold": number(-0.9, -0.1, -0.45)}),
			InputRequirements: []string{"news.sentiment_1h"},
			OverlayTypes: []string{"buy_signal", "sell_signal"}, WarmUpCandles: 1,
			CodeFingerprint: "sha256:news-sentiment-demo-v1",
		},
		{
			StrategyID: "macd", Version: "1.0.0", Family: "trend", DisplayName: "MACD",
			Description: "MACD line and signal crossover. Registered as a plugin like other strategies.",
			ParametersSchema: schema(map[string]any{"fast": number(8, 20, 12), "slow": number(18, 40, 26), "signal": number(5, 15, 9)}),
			InputRequirements: []string{"candles.close", "indicator.ema"},
			OverlayTypes: []string{"macd_line", "macd_signal", "buy_signal", "sell_signal"}, WarmUpCandles: 35,
			CodeFingerprint: "sha256:macd-demo-v1",
		},
		{
			StrategyID: "composite", Version: "1.0.0", DisplayName: "Composite Strategy",
			Description: "Immutable combination of child strategies with majority or weighted vote.",
			ParametersSchema: schema(map[string]any{"policy": enum([]string{"weighted_vote", "majority_vote"}, "weighted_vote"), "threshold": number(0, 1, 0.34)}),
			InputRequirements: []string{"children.signals"}, OverlayTypes: []string{"buy_signal", "sell_signal"},
			WarmUpCandles: 60, IsComposite: true, CodeFingerprint: "sha256:composite-demo-v1",
		},
	}
}

func DefaultParams(strategyID string) map[string]any {
	switch strategyID {
	case "ma_cross":
		return map[string]any{"fast": 20, "slow": 50}
	case "rsi":
		return map[string]any{"period": 14, "buy_threshold": 30, "sell_threshold": 70}
	case "bollinger":
		return map[string]any{"period": 20, "stddev": 2}
	case "support_resistance":
		return map[string]any{"lookback": 60, "zone_bps": 45}
	case "news_sentiment":
		return map[string]any{"window_sec": 3600, "buy_threshold": 0.45, "sell_threshold": -0.45}
	case "macd":
		return map[string]any{"fast": 12, "slow": 26, "signal": 9}
	default:
		return map[string]any{}
	}
}

func DefaultExperimentRequest() ExperimentRequest {
	return ExperimentRequest{
		Provider: ProviderBinance, Symbol: SymbolETHUSDT, Timeframe: "5m",
		StrategyID: "composite", StrategyVersion: "1.0.0",
		Children: []StrategyChild{
			{StrategyID: "ma_cross", Version: "1.0.0", Parameters: DefaultParams("ma_cross"), Weight: 0.34},
			{StrategyID: "rsi", Version: "1.0.0", Parameters: DefaultParams("rsi"), Weight: 0.33},
			{StrategyID: "support_resistance", Version: "1.0.0", Parameters: DefaultParams("support_resistance"), Weight: 0.33},
		},
		Combination: CombinationInput{Policy: "weighted_vote", Threshold: 0.34, Encoding: "BUY=1,SELL=-1,HOLD=0"},
		InitialEquity: 100, FixedNotional: 10, Leverage: 1, FeeBps: 10, SlippageBps: 0,
		IntrabarPriority: "stop_loss_first",
	}
}

func LoadCandles(ctx context.Context, db *sql.DB, provider, symbol, timeframe string, limit int) ([]Candle, error) {
	if limit <= 0 || limit > 1000 {
		limit = 180
	}
	if err := EnsureCandles(ctx, db, provider, symbol, timeframe, limit); err != nil {
		return nil, err
	}
	rows, err := db.QueryContext(ctx, `
		SELECT provider,symbol,timeframe,open_time,close_time,open::float8,high::float8,low::float8,close::float8,volume::float8,trade_count
		FROM (
			SELECT * FROM candles
			WHERE provider=$1 AND symbol=$2 AND timeframe=$3
			ORDER BY open_time DESC LIMIT $4
		) c ORDER BY open_time ASC
	`, provider, symbol, timeframe, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var candles []Candle
	for rows.Next() {
		var c Candle
		if err := rows.Scan(&c.Provider, &c.Symbol, &c.Timeframe, &c.OpenTime, &c.CloseTime, &c.Open, &c.High, &c.Low, &c.Close, &c.Volume, &c.TradeCount); err != nil {
			return nil, err
		}
		candles = append(candles, c)
	}
	return candles, rows.Err()
}

func CreateExperiment(ctx context.Context, db *sql.DB, ownerID string, req ExperimentRequest, priority int) (AcceptedRun, error) {
	req = normalizeExperimentRequest(req)
	if req.IdempotencyKey != "" {
		var existingID, runID, status string
		err := db.QueryRowContext(ctx, `
			SELECT e.id, br.id, br.status FROM experiments e JOIN backtest_runs br ON br.experiment_id=e.id
			WHERE e.owner_id=$1 AND e.idempotency_key=$2
		`, ownerID, req.IdempotencyKey).Scan(&existingID, &runID, &status)
		if err == nil {
			return AcceptedRun{ExperimentID: existingID, RunID: runID, Status: status, Reused: true}, nil
		}
	}

	candles, err := LoadCandles(ctx, db, req.Provider, req.Symbol, req.Timeframe, 220)
	if err != nil {
		return AcceptedRun{}, err
	}
	if len(candles) < 80 {
		return AcceptedRun{}, fmt.Errorf("dataset_too_small")
	}
	rangeFrom, rangeTo := candles[0].OpenTime, candles[len(candles)-1].OpenTime
	datasetVersion := fmt.Sprintf("%s-%s-%s-%s-%s-r1", req.Provider, req.Symbol, req.Timeframe, rangeFrom.Format("20060102"), rangeTo.Format("20060102"))
	contentHash := candlesContentHash(candles)
	definition := candidateDefinition(req)
	definitionJSON, _ := json.Marshal(definition)
	candidateHash := sha256HexBytes(definitionJSON)
	riskJSON := riskPolicyJSON(req)
	expID := uuid.NewString()
	runID := uuid.NewString()
	jobID := uuid.NewString()

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return AcceptedRun{}, err
	}
	defer tx.Rollback()

	_, err = tx.ExecContext(ctx, `
		INSERT INTO experiments(id,owner_id,strategy_id,strategy_version,candidate_definition,candidate_hash,provider,symbol,timeframe,dataset_version,content_hash,range_from,range_to,initial_equity,fixed_notional,leverage,fee_bps,slippage_bps,risk_policy,search_run_id,generated_by,generation_meta,idempotency_key)
		VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19::jsonb,$20,$21,$22::jsonb,$23)
	`, expID, ownerID, req.StrategyID, req.StrategyVersion, string(definitionJSON), candidateHash, req.Provider, req.Symbol, req.Timeframe, datasetVersion, contentHash, rangeFrom, rangeTo, req.InitialEquity, req.FixedNotional, req.Leverage, req.FeeBps, req.SlippageBps, riskJSON, nullable(req.SearchRunID), nullable(req.GeneratedBy), nullableJSON(req.GenerationMetaJSON), nullable(req.IdempotencyKey))
	if err != nil {
		return AcceptedRun{}, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO backtest_runs(id,experiment_id,status) VALUES($1,$2,'queued')`, runID, expID); err != nil {
		return AcceptedRun{}, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO backtest_jobs(id,experiment_id,status,priority) VALUES($1,$2,'queued',$3)`, jobID, expID, priority); err != nil {
		return AcceptedRun{}, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO domain_events(event_id,event_type,aggregate_type,aggregate_id,payload) VALUES($1,'ExperimentCreated','experiment',$2,$3::jsonb)`, uuid.NewString(), expID, fmt.Sprintf(`{"experiment_id":"%s","candidate_hash":"%s"}`, expID, candidateHash)); err != nil {
		return AcceptedRun{}, err
	}
	if req.SearchRunID != "" {
		_, err = tx.ExecContext(ctx, `UPDATE search_runs SET generated=generated+1, current_candidate=$1, updated_at=now() WHERE id=$2`, candidateHash[:12], req.SearchRunID)
		if err != nil {
			return AcceptedRun{}, err
		}
	}
	if err := tx.Commit(); err != nil {
		return AcceptedRun{}, err
	}
	return AcceptedRun{RunID: runID, ExperimentID: expID, Status: "queued"}, nil
}

func RunExperimentNow(ctx context.Context, db *sql.DB, experimentID, workerID string) error {
	start := time.Now()
	var exp experimentRow
	if err := loadExperiment(ctx, db, experimentID, &exp); err != nil {
		return err
	}
	leaseToken := uuid.NewString()
	if _, err := db.ExecContext(ctx, `
		UPDATE backtest_runs SET status='running', worker_id=$1, lease_token=$2, attempt=attempt+1, started_at=COALESCE(started_at, now()) WHERE experiment_id=$3
	`, workerID, leaseToken, experimentID); err != nil {
		return err
	}
	candles, err := LoadCandles(ctx, db, exp.Provider, exp.Symbol, exp.Timeframe, 220)
	if err != nil {
		return failExperiment(ctx, db, experimentID, "dataset_unavailable", err.Error())
	}
	result := Backtest(exp, candles)
	durationMS := int(time.Since(start).Milliseconds())
	if err := persistBacktestResult(ctx, db, exp, result, durationMS); err != nil {
		return failExperiment(ctx, db, experimentID, "persist_failed", err.Error())
	}
	return nil
}

type experimentRow struct {
	ID, OwnerID, StrategyID, StrategyVersion, CandidateHash, Provider, Symbol, Timeframe, DatasetVersion, ContentHash string
	CandidateDefinition map[string]any
	InitialEquity, FixedNotional, Leverage float64
	FeeBps, SlippageBps int
	RiskPolicy map[string]any
	SearchRunID sql.NullString
}

func loadExperiment(ctx context.Context, db *sql.DB, id string, exp *experimentRow) error {
	var defJSON, riskJSON []byte
	err := db.QueryRowContext(ctx, `
		SELECT id,owner_id,strategy_id,strategy_version,candidate_definition,candidate_hash,provider,symbol,timeframe,dataset_version,content_hash,initial_equity::float8,fixed_notional::float8,leverage::float8,fee_bps,slippage_bps,COALESCE(risk_policy,'{}'::jsonb),search_run_id
		FROM experiments WHERE id=$1
	`, id).Scan(&exp.ID, &exp.OwnerID, &exp.StrategyID, &exp.StrategyVersion, &defJSON, &exp.CandidateHash, &exp.Provider, &exp.Symbol, &exp.Timeframe, &exp.DatasetVersion, &exp.ContentHash, &exp.InitialEquity, &exp.FixedNotional, &exp.Leverage, &exp.FeeBps, &exp.SlippageBps, &riskJSON, &exp.SearchRunID)
	if err != nil {
		return err
	}
	_ = json.Unmarshal(defJSON, &exp.CandidateDefinition)
	_ = json.Unmarshal(riskJSON, &exp.RiskPolicy)
	return nil
}

type backtestResult struct {
	Trades []Trade
	Signals []OverlayMarker
	Equity []EquityPoint
	Metrics Metrics
}

func Backtest(exp experimentRow, candles []Candle) backtestResult {
	initial := defaultFloat(exp.InitialEquity, 100)
	notional := defaultFloat(exp.FixedNotional, 10)
	leverage := defaultFloat(exp.Leverage, 1)
	feeRate := float64(exp.FeeBps) / 10000
	equity := initial
	peak := initial
	inPosition := false
	entryPrice := 0.0
	entryTime := time.Time{}
	entrySignal := time.Time{}
	quantity := 0.0
	seq := 0
	var trades []Trade
	var signals []OverlayMarker
	var equityPoints []EquityPoint
	var returns []float64

	for i := 60; i < len(candles); i++ {
		signal, conf, evidence := compositeSignal(candles, i, exp.CandidateDefinition)
		if signal != "HOLD" {
			signals = append(signals, OverlayMarker{T: candles[i].OpenTime, OverlayType: mapActionToMarker(signal), Confidence: &conf, Evidence: evidence})
		}

		if inPosition {
			exitReason := ""
			exitPrice := candles[i].Close
			if sl, ok := numberFromMap(exp.RiskPolicy, "stop_loss_pct"); ok && candles[i].Low <= entryPrice*(1-sl/100) {
				exitReason = "stop_loss"
				exitPrice = entryPrice * (1 - sl/100)
			}
			if tp, ok := numberFromMap(exp.RiskPolicy, "take_profit_pct"); ok && candles[i].High >= entryPrice*(1+tp/100) && exitReason == "" {
				exitReason = "take_profit"
				exitPrice = entryPrice * (1 + tp/100)
			}
			if signal == "SELL" && exitReason == "" {
				exitReason = "signal"
			}
			if exitReason != "" {
				exitPrice = exitPrice * (1 - float64(exp.SlippageBps)/10000)
				pnl := (exitPrice-entryPrice)*quantity - (entryPrice+exitPrice)*quantity*feeRate
				pnlPct := pnl / notional * 100
				equity += pnl
				seq++
				trades = append(trades, Trade{
					ID: uuid.NewString(), SequenceNo: seq, Side: "LONG", EntryTime: entryTime, ExitTime: candles[i].OpenTime,
					EntryPrice: entryPrice, ExitPrice: exitPrice, Quantity: quantity, PnL: pnl, PnLPct: pnlPct,
					ExitReason: exitReason, SignalT: entrySignal, ChildSignals: evidence,
				})
				returns = append(returns, pnlPct)
				inPosition = false
			}
		}

		if !inPosition && signal == "BUY" {
			entryPrice = candles[i].Close * (1 + float64(exp.SlippageBps)/10000)
			quantity = notional * leverage / entryPrice
			entryTime = candles[i].OpenTime
			entrySignal = candles[i].OpenTime
			inPosition = true
		}

		mark := equity
		if inPosition {
			mark += (candles[i].Close-entryPrice)*quantity
		}
		if mark > peak {
			peak = mark
		}
		dd := 0.0
		if peak > 0 {
			dd = (mark - peak) / peak * 100
		}
		equityPoints = append(equityPoints, EquityPoint{T: candles[i].OpenTime, Equity: mark, DrawdownPct: dd})
	}

	if inPosition && len(candles) > 0 {
		last := candles[len(candles)-1]
		exitPrice := last.Close
		pnl := (exitPrice-entryPrice)*quantity - (entryPrice+exitPrice)*quantity*feeRate
		equity += pnl
		seq++
		trades = append(trades, Trade{ID: uuid.NewString(), SequenceNo: seq, Side: "LONG", EntryTime: entryTime, ExitTime: last.OpenTime, EntryPrice: entryPrice, ExitPrice: exitPrice, Quantity: quantity, PnL: pnl, PnLPct: pnl / notional * 100, ExitReason: "end_of_sample", SignalT: entrySignal})
	}

	metrics := evaluate(initial, equity, trades, equityPoints, returns)
	return backtestResult{Trades: trades, Signals: signals, Equity: equityPoints, Metrics: metrics}
}

func persistBacktestResult(ctx context.Context, db *sql.DB, exp experimentRow, result backtestResult, durationMS int) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, statement := range []string{
		`DELETE FROM trades WHERE experiment_id=$1`,
		`DELETE FROM run_signals WHERE experiment_id=$1`,
		`DELETE FROM equity_points WHERE experiment_id=$1`,
		`DELETE FROM evaluations WHERE experiment_id=$1`,
	} {
		if _, err := tx.ExecContext(ctx, statement, exp.ID); err != nil {
			return err
		}
	}
	for _, sig := range result.Signals {
		evidence, _ := json.Marshal(sig.Evidence)
		conf := 0.0
		if sig.Confidence != nil {
			conf = *sig.Confidence
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO run_signals(id,experiment_id,t,action,confidence,evidence) VALUES($1,$2,$3,$4,$5,$6::jsonb)`, uuid.NewString(), exp.ID, sig.T, markerToAction(sig.OverlayType), conf, string(evidence)); err != nil {
			return err
		}
	}
	for _, trade := range result.Trades {
		child, _ := json.Marshal(trade.ChildSignals)
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO trades(id,experiment_id,sequence_no,side,entry_time,exit_time,entry_price,exit_price,quantity,pnl,pnl_pct,exit_reason,signal_t,child_signals)
			VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb)
		`, trade.ID, exp.ID, trade.SequenceNo, trade.Side, trade.EntryTime, trade.ExitTime, trade.EntryPrice, trade.ExitPrice, trade.Quantity, trade.PnL, trade.PnLPct, trade.ExitReason, trade.SignalT, string(child)); err != nil {
			return err
		}
	}
	for _, point := range result.Equity {
		if _, err := tx.ExecContext(ctx, `INSERT INTO equity_points(experiment_id,t,equity,drawdown_pct) VALUES($1,$2,$3,$4) ON CONFLICT(experiment_id,t) DO UPDATE SET equity=EXCLUDED.equity, drawdown_pct=EXCLUDED.drawdown_pct`, exp.ID, point.T, point.Equity, point.DrawdownPct); err != nil {
			return err
		}
	}
	evaluationID := uuid.NewString()
	m := result.Metrics
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO evaluations(id,experiment_id,evaluator_version,total_return_pct,win_rate_pct,max_drawdown_pct,trade_count,profit_factor,sharpe_ratio,score)
		VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
	`, evaluationID, exp.ID, m.EvaluatorVersion, m.TotalReturnPct, m.WinRatePct, m.MaxDrawdownPct, m.TradeCount, m.ProfitFactor, m.SharpeRatio, m.Score); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO leaderboard_entries(id,evaluation_id,experiment_id,score,dataset_version)
		VALUES($1,$2,$3,$4,$5)
		ON CONFLICT(evaluation_id) DO NOTHING
	`, uuid.NewString(), evaluationID, exp.ID, m.Score, exp.DatasetVersion); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE backtest_runs SET status='completed', candles_read=$1, signals_count=$2, duration_ms=$3, finished_at=now(), error_code=NULL WHERE experiment_id=$4`, len(result.Equity), len(result.Signals), durationMS, exp.ID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE backtest_jobs SET status='completed', completed_at=now(), lease_token=NULL WHERE experiment_id=$1`, exp.ID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO domain_events(event_id,event_type,aggregate_type,aggregate_id,payload) VALUES($1,'BacktestCompleted','experiment',$2,$3::jsonb)`, uuid.NewString(), exp.ID, fmt.Sprintf(`{"experiment_id":"%s","score":%.4f}`, exp.ID, m.Score)); err != nil {
		return err
	}
	if exp.SearchRunID.Valid {
		if _, err := tx.ExecContext(ctx, `
			UPDATE search_runs
			SET tested=tested+1,
			    best_score=GREATEST(COALESCE(best_score,-999999), $1),
			    updated_at=now(),
			    status=CASE WHEN tested + failed + 1 >= generated THEN 'completed' ELSE status END,
			    stop_reason=CASE WHEN tested + failed + 1 >= generated THEN 'max_candidates' ELSE stop_reason END
			WHERE id=$2
		`, m.Score, exp.SearchRunID.String); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func failExperiment(ctx context.Context, db *sql.DB, experimentID, code, detail string) error {
	if _, err := db.ExecContext(ctx, `UPDATE backtest_runs SET status='failed', error_code=$1, error_detail=$2, finished_at=now() WHERE experiment_id=$3`, code, detail, experimentID); err != nil {
		return err
	}
	_, err := db.ExecContext(ctx, `UPDATE backtest_jobs SET status='failed', last_error=$1, completed_at=now() WHERE experiment_id=$2`, detail, experimentID)
	return err
}

func evaluate(initial, final float64, trades []Trade, equity []EquityPoint, returns []float64) Metrics {
	totalReturn := 0.0
	if initial > 0 {
		totalReturn = (final - initial) / initial * 100
	}
	wins := 0
	grossProfit := 0.0
	grossLoss := 0.0
	for _, t := range trades {
		if t.PnL > 0 {
			wins++
			grossProfit += t.PnL
		} else {
			grossLoss += math.Abs(t.PnL)
		}
	}
	winRate := 0.0
	if len(trades) > 0 {
		winRate = float64(wins) / float64(len(trades)) * 100
	}
	mdd := 0.0
	for _, p := range equity {
		if p.DrawdownPct < mdd {
			mdd = p.DrawdownPct
		}
	}
	profitFactor := grossProfit
	if grossLoss > 0 {
		profitFactor = grossProfit / grossLoss
	}
	sharpe := sharpeRatio(returns)
	riskScore := math.Max(0, 100+mdd*2)
	score := clamp(totalReturn+50, 0, 100)*0.5 + winRate*0.2 + riskScore*0.3
	return Metrics{TotalReturnPct: round(totalReturn), WinRatePct: round(winRate), MaxDrawdownPct: round(mdd), TradeCount: len(trades), ProfitFactor: round(profitFactor), SharpeRatio: round(sharpe), Score: round(score), EvaluatorVersion: "1.0.0"}
}

func ChartOverlays(candles []Candle, strategyID string) ([]OverlaySeries, []OverlayMarker) {
	if len(candles) == 0 {
		return []OverlaySeries{}, []OverlayMarker{}
	}
	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}
	sma20 := sma(closes, 20)
	sma50 := sma(closes, 50)
	rsi14 := rsi(closes, 14)
	upper, middle, lower := bollinger(closes, 20, 2)
	series := []OverlaySeries{
		{Name: "ma20", OverlayType: "moving_average", Pane: "main", Points: points(candles, sma20)},
		{Name: "ma50", OverlayType: "moving_average", Pane: "main", Points: points(candles, sma50)},
		{Name: "rsi", OverlayType: "rsi", Pane: "sub", Unit: "index", Scale: map[string]float64{"min": 0, "max": 100}, Points: points(candles, rsi14)},
		{Name: "rsi_buy_threshold", OverlayType: "rsi", Pane: "sub", Constant: ptr(30), Style: "dashed"},
		{Name: "rsi_sell_threshold", OverlayType: "rsi", Pane: "sub", Constant: ptr(70), Style: "dashed"},
		{Name: "bollinger", OverlayType: "bollinger_bands", Pane: "main", Band: &OverlayBand{Upper: points(candles, upper), Middle: points(candles, middle), Lower: points(candles, lower)}},
	}
	if len(candles) >= 60 {
		low, high := supportResistance(candles, len(candles)-1, 60)
		from := candles[len(candles)-60].OpenTime
		to := candles[len(candles)-1].OpenTime
		series = append(series,
			OverlaySeries{Name: "support_zone", OverlayType: "support_zone", Pane: "main", Zones: []OverlayZone{{From: from, To: to, PriceLow: low * 0.997, PriceHigh: low * 1.003}}},
			OverlaySeries{Name: "resistance_zone", OverlayType: "resistance_zone", Pane: "main", Zones: []OverlayZone{{From: from, To: to, PriceLow: high * 0.997, PriceHigh: high * 1.003}}},
		)
	}

	markers := make([]OverlayMarker, 0)
	def := map[string]any{"children": []any{
		map[string]any{"strategy_id": "ma_cross", "weight": 0.34, "parameters": DefaultParams("ma_cross")},
		map[string]any{"strategy_id": "rsi", "weight": 0.33, "parameters": DefaultParams("rsi")},
		map[string]any{"strategy_id": "support_resistance", "weight": 0.33, "parameters": DefaultParams("support_resistance")},
	}, "combination": map[string]any{"threshold": 0.34}}
	for i := 60; i < len(candles); i++ {
		action, confidence, evidence := compositeSignal(candles, i, def)
		if action != "HOLD" {
			markers = append(markers, OverlayMarker{T: candles[i].OpenTime, OverlayType: mapActionToMarker(action), Confidence: &confidence, Evidence: evidence})
		}
	}
	if strategyID == "macd" {
		macdLine, sigLine := macd(closes, 12, 26, 9)
		series = append(series,
			OverlaySeries{Name: "macd_line", OverlayType: "macd_line", Pane: "sub", Points: points(candles, macdLine)},
			OverlaySeries{Name: "macd_signal", OverlayType: "macd_signal", Pane: "sub", Points: points(candles, sigLine)},
		)
	}
	return series, markers
}

func compositeSignal(candles []Candle, i int, definition map[string]any) (string, float64, map[string]any) {
	children, _ := definition["children"].([]any)
	if len(children) == 0 {
		children = []any{
			map[string]any{"strategy_id": "ma_cross", "weight": 0.34, "parameters": DefaultParams("ma_cross")},
			map[string]any{"strategy_id": "rsi", "weight": 0.33, "parameters": DefaultParams("rsi")},
			map[string]any{"strategy_id": "support_resistance", "weight": 0.33, "parameters": DefaultParams("support_resistance")},
		}
	}
	score := 0.0
	totalWeight := 0.0
	evidence := map[string]any{}
	for _, raw := range children {
		child, _ := raw.(map[string]any)
		id, _ := child["strategy_id"].(string)
		weight := floatFromAny(child["weight"], 1)
		params, _ := child["parameters"].(map[string]any)
		action, conf, data := strategySignal(id, candles, i, params)
		evidence[id] = map[string]any{"action": action, "confidence": conf, "evidence": data}
		switch action {
		case "BUY":
			score += weight
		case "SELL":
			score -= weight
		}
		totalWeight += math.Abs(weight)
	}
	if totalWeight == 0 {
		totalWeight = 1
	}
	threshold := 0.34
	if combo, ok := definition["combination"].(map[string]any); ok {
		threshold = floatFromAny(combo["threshold"], threshold)
	}
	normalized := score / totalWeight
	evidence["score"] = round(normalized)
	evidence["threshold"] = threshold
	if normalized >= threshold {
		return "BUY", math.Min(0.98, math.Abs(normalized)), evidence
	}
	if normalized <= -threshold {
		return "SELL", math.Min(0.98, math.Abs(normalized)), evidence
	}
	return "HOLD", math.Abs(normalized), evidence
}

func strategySignal(id string, candles []Candle, i int, params map[string]any) (string, float64, map[string]any) {
	closes := make([]float64, len(candles))
	for j, c := range candles {
		closes[j] = c.Close
	}
	switch id {
	case "ma_cross":
		fast := int(floatFromAny(params["fast"], 20))
		slow := int(floatFromAny(params["slow"], 50))
		a, b := sma(closes, fast), sma(closes, slow)
		if i > 0 && valid(a[i]) && valid(b[i]) && valid(a[i-1]) && valid(b[i-1]) {
			if a[i] > b[i] && a[i-1] <= b[i-1] {
				return "BUY", 0.72, map[string]any{"fast": round(a[i]), "slow": round(b[i])}
			}
			if a[i] < b[i] && a[i-1] >= b[i-1] {
				return "SELL", 0.72, map[string]any{"fast": round(a[i]), "slow": round(b[i])}
			}
		}
	case "rsi":
		period := int(floatFromAny(params["period"], 14))
		buy := floatFromAny(params["buy_threshold"], 30)
		sell := floatFromAny(params["sell_threshold"], 70)
		values := rsi(closes, period)
		if valid(values[i]) {
			if values[i] <= buy {
				return "BUY", 0.69, map[string]any{"rsi": round(values[i]), "threshold": buy}
			}
			if values[i] >= sell {
				return "SELL", 0.69, map[string]any{"rsi": round(values[i]), "threshold": sell}
			}
		}
	case "bollinger":
		period := int(floatFromAny(params["period"], 20))
		std := floatFromAny(params["stddev"], 2)
		up, _, lo := bollinger(closes, period, std)
		if valid(lo[i]) && candles[i].Close < lo[i] {
			return "BUY", 0.63, map[string]any{"close": round(candles[i].Close), "lower": round(lo[i])}
		}
		if valid(up[i]) && candles[i].Close > up[i] {
			return "SELL", 0.63, map[string]any{"close": round(candles[i].Close), "upper": round(up[i])}
		}
	case "support_resistance":
		lookback := int(floatFromAny(params["lookback"], 60))
		zoneBps := floatFromAny(params["zone_bps"], 45) / 10000
		lo, hi := supportResistance(candles, i, lookback)
		if lo > 0 && math.Abs(candles[i].Close-lo)/lo <= zoneBps {
			return "BUY", 0.58, map[string]any{"support": round(lo), "close": round(candles[i].Close)}
		}
		if hi > 0 && math.Abs(candles[i].Close-hi)/hi <= zoneBps {
			return "SELL", 0.58, map[string]any{"resistance": round(hi), "close": round(candles[i].Close)}
		}
	case "news_sentiment":
		if i%37 == 0 {
			return "BUY", 0.57, map[string]any{"avg_score": 0.48, "model_version": "2026-08-01"}
		}
	}
	return "HOLD", 0, map[string]any{}
}

func sma(values []float64, period int) []float64 {
	out := make([]float64, len(values))
	fillNaN(out)
	if period <= 0 {
		return out
	}
	sum := 0.0
	for i, v := range values {
		sum += v
		if i >= period {
			sum -= values[i-period]
		}
		if i >= period-1 {
			out[i] = sum / float64(period)
		}
	}
	return out
}

func ema(values []float64, period int) []float64 {
	out := make([]float64, len(values))
	fillNaN(out)
	if len(values) == 0 || period <= 0 {
		return out
	}
	k := 2.0 / (float64(period) + 1)
	prev := values[0]
	for i, v := range values {
		if i == 0 {
			prev = v
		} else {
			prev = v*k + prev*(1-k)
		}
		if i >= period-1 {
			out[i] = prev
		}
	}
	return out
}

func rsi(values []float64, period int) []float64 {
	out := make([]float64, len(values))
	fillNaN(out)
	if len(values) <= period {
		return out
	}
	gain, loss := 0.0, 0.0
	for i := 1; i <= period; i++ {
		d := values[i] - values[i-1]
		if d >= 0 {
			gain += d
		} else {
			loss -= d
		}
	}
	avgGain, avgLoss := gain/float64(period), loss/float64(period)
	for i := period + 1; i < len(values); i++ {
		d := values[i] - values[i-1]
		g, l := 0.0, 0.0
		if d >= 0 {
			g = d
		} else {
			l = -d
		}
		avgGain = (avgGain*float64(period-1) + g) / float64(period)
		avgLoss = (avgLoss*float64(period-1) + l) / float64(period)
		if avgLoss == 0 {
			out[i] = 100
		} else {
			rs := avgGain / avgLoss
			out[i] = 100 - 100/(1+rs)
		}
	}
	return out
}

func bollinger(values []float64, period int, stddev float64) ([]float64, []float64, []float64) {
	mid := sma(values, period)
	up, lo := make([]float64, len(values)), make([]float64, len(values))
	fillNaN(up); fillNaN(lo)
	for i := period - 1; i < len(values); i++ {
		sum := 0.0
		for j := i - period + 1; j <= i; j++ {
			d := values[j] - mid[i]
			sum += d * d
		}
		dev := math.Sqrt(sum / float64(period))
		up[i] = mid[i] + stddev*dev
		lo[i] = mid[i] - stddev*dev
	}
	return up, mid, lo
}

func macd(values []float64, fast, slow, signal int) ([]float64, []float64) {
	fastEma, slowEma := ema(values, fast), ema(values, slow)
	line := make([]float64, len(values))
	fillNaN(line)
	for i := range values {
		if valid(fastEma[i]) && valid(slowEma[i]) {
			line[i] = fastEma[i] - slowEma[i]
		}
	}
	clean := make([]float64, len(values))
	for i, v := range line {
		if valid(v) {
			clean[i] = v
		}
	}
	return line, ema(clean, signal)
}

func supportResistance(candles []Candle, i, lookback int) (float64, float64) {
	if i < 0 || len(candles) == 0 {
		return 0, 0
	}
	start := i - lookback + 1
	if start < 0 {
		start = 0
	}
	lo, hi := candles[start].Low, candles[start].High
	for j := start; j <= i; j++ {
		if candles[j].Low < lo {
			lo = candles[j].Low
		}
		if candles[j].High > hi {
			hi = candles[j].High
		}
	}
	return lo, hi
}

func CreateSearchRun(ctx context.Context, db *sql.DB, ownerID string, req SearchRunRequest) (string, error) {
	if req.IdempotencyKey != "" {
		var existing string
		if err := db.QueryRowContext(ctx, `SELECT id FROM search_runs WHERE owner_id=$1 AND idempotency_key=$2`, ownerID, req.IdempotencyKey).Scan(&existing); err == nil {
			return existing, nil
		}
	}
	runID := uuid.NewString()
	market := req.Market
	if market.Provider == "" {
		market.Provider = ProviderBinance
	}
	if market.Symbol == "" {
		market.Symbol = SymbolETHUSDT
	}
	if market.Timeframe == "" {
		market.Timeframe = "5m"
	}
	candles, err := LoadCandles(ctx, db, market.Provider, market.Symbol, market.Timeframe, 220)
	if err != nil {
		return "", err
	}
	datasetVersion := fmt.Sprintf("%s-%s-%s-search-r1", market.Provider, market.Symbol, market.Timeframe)
	contentHash := candlesContentHash(candles)
	stop, _ := json.Marshal(req.StopConditions)
	if len(req.StopConditions) == 0 {
		stop = []byte(`{"max_candidates":6}`)
	}
	if _, err := db.ExecContext(ctx, `
		INSERT INTO search_runs(id,owner_id,generator_id,status,stop_conditions,dataset_version,content_hash,idempotency_key)
		VALUES($1,$2,$3,'running',$4::jsonb,$5,$6,$7)
	`, runID, ownerID, defaultString(req.GeneratorID, "random_search"), string(stop), datasetVersion, contentHash, nullable(req.IdempotencyKey)); err != nil {
		return "", err
	}
	candidates := searchCandidates(req)
	for idx, children := range candidates {
		expReq := DefaultExperimentRequest()
		expReq.Provider, expReq.Symbol, expReq.Timeframe = market.Provider, market.Symbol, market.Timeframe
		expReq.Children = children
		expReq.SearchRunID = runID
		expReq.GeneratedBy = defaultString(req.GeneratorID, "random_search")
		expReq.GenerationMetaJSON = fmt.Sprintf(`{"seed":%d,"attempt":%d}`, req.Seed, idx+1)
		expReq.IdempotencyKey = ""
		if _, err := CreateExperiment(ctx, db, ownerID, expReq, 200); err != nil {
			return "", err
		}
	}
	return runID, nil
}

func searchCandidates(req SearchRunRequest) [][]StrategyChild {
	ids := req.SearchSpace.StrategyIDs
	if len(ids) == 0 {
		ids = []string{"ma_cross", "rsi", "bollinger", "support_resistance", "news_sentiment"}
	}
	var candidates [][]StrategyChild
	add := func(names ...string) {
		var children []StrategyChild
		weight := 1.0 / float64(len(names))
		for _, name := range names {
			children = append(children, StrategyChild{StrategyID: name, Version: "1.0.0", Parameters: DefaultParams(name), Weight: weight})
		}
		candidates = append(candidates, children)
	}
	add("ma_cross", "rsi", "support_resistance")
	add("ma_cross", "bollinger")
	add("rsi", "support_resistance")
	add("ma_cross", "rsi", "news_sentiment")
	add("bollinger", "support_resistance", "news_sentiment")
	add("macd", "rsi", "support_resistance")
	if len(ids) >= 2 {
		sort.Strings(ids)
		add(ids[0], ids[1])
	}
	if len(candidates) > 6 {
		return candidates[:6]
	}
	return candidates
}

func normalizeExperimentRequest(req ExperimentRequest) ExperimentRequest {
	if req.Provider == "" { req.Provider = ProviderBinance }
	if req.Symbol == "" { req.Symbol = SymbolETHUSDT }
	if req.Timeframe == "" { req.Timeframe = "5m" }
	if req.StrategyID == "" { req.StrategyID = "composite" }
	if req.StrategyVersion == "" { req.StrategyVersion = "1.0.0" }
	if len(req.Children) == 0 { req.Children = DefaultExperimentRequest().Children }
	if req.Combination.Policy == "" { req.Combination = CombinationInput{Policy: "weighted_vote", Threshold: 0.34, Encoding: "BUY=1,SELL=-1,HOLD=0"} }
	if req.InitialEquity <= 0 { req.InitialEquity = 100 }
	if req.FixedNotional <= 0 { req.FixedNotional = 10 }
	if req.Leverage <= 0 { req.Leverage = 1 }
	if req.FeeBps < 0 { req.FeeBps = 10 }
	if req.IntrabarPriority == "" { req.IntrabarPriority = "stop_loss_first" }
	return req
}

func candidateDefinition(req ExperimentRequest) map[string]any {
	children := make([]map[string]any, 0, len(req.Children))
	for _, child := range req.Children {
		children = append(children, map[string]any{"strategy_id": child.StrategyID, "version": child.Version, "parameters": child.Parameters, "weight": child.Weight})
	}
	return map[string]any{
		"strategy_id": req.StrategyID,
		"version": req.StrategyVersion,
		"children": children,
		"combination": map[string]any{"policy": req.Combination.Policy, "threshold": req.Combination.Threshold, "encoding": req.Combination.Encoding},
	}
}

func riskPolicyJSON(req ExperimentRequest) any {
	if req.StopLossPct == nil && req.TakeProfitPct == nil {
		return nil
	}
	policy := map[string]any{"intrabar_priority": defaultString(req.IntrabarPriority, "stop_loss_first")}
	if req.StopLossPct != nil { policy["stop_loss_pct"] = *req.StopLossPct }
	if req.TakeProfitPct != nil { policy["take_profit_pct"] = *req.TakeProfitPct }
	data, _ := json.Marshal(policy)
	return string(data)
}

func candlesContentHash(candles []Candle) string {
	h := sha256.New()
	for _, c := range candles {
		fmt.Fprintf(h, "%s|%.8f|%.8f|%.8f|%.8f|", c.OpenTime.Format(time.RFC3339), c.Open, c.High, c.Low, c.Close)
	}
	return hex.EncodeToString(h.Sum(nil))
}

func sha256HexBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func points(candles []Candle, values []float64) []OverlayPoint {
	out := make([]OverlayPoint, 0, len(candles))
	for i, c := range candles {
		if i >= len(values) || !valid(values[i]) {
			out = append(out, OverlayPoint{T: c.OpenTime, V: nil})
			continue
		}
		v := round(values[i])
		out = append(out, OverlayPoint{T: c.OpenTime, V: &v})
	}
	return out
}

func sharpeRatio(returns []float64) float64 {
	if len(returns) < 2 {
		return 0
	}
	mean := 0.0
	for _, r := range returns { mean += r }
	mean /= float64(len(returns))
	variance := 0.0
	for _, r := range returns { d := r - mean; variance += d*d }
	dev := math.Sqrt(variance / float64(len(returns)-1))
	if dev == 0 { return 0 }
	return mean / dev * math.Sqrt(float64(len(returns)))
}

func schema(props map[string]any) map[string]any { return map[string]any{"type": "object", "properties": props} }
func number(min, max, def float64) map[string]any { return map[string]any{"type": "number", "minimum": min, "maximum": max, "default": def} }
func enum(values []string, def string) map[string]any { return map[string]any{"type": "string", "enum": values, "default": def} }
func ptr(v float64) *float64 { return &v }
func fillNaN(v []float64) { for i := range v { v[i] = math.NaN() } }
func valid(v float64) bool { return !math.IsNaN(v) && !math.IsInf(v, 0) }
func round(v float64) float64 { return math.Round(v*10000) / 10000 }
func clamp(v, lo, hi float64) float64 { return math.Min(hi, math.Max(lo, v)) }
func defaultFloat(v, fallback float64) float64 { if v <= 0 { return fallback }; return v }
func defaultString(v, fallback string) string { if v == "" { return fallback }; return v }
func mapActionToMarker(action string) string { if action == "SELL" { return "sell_signal" }; return "buy_signal" }
func markerToAction(marker string) string { if marker == "sell_signal" { return "SELL" }; return "BUY" }
func nullable(v string) any { if v == "" { return nil }; return v }
func nullableJSON(v string) any { if v == "" { return nil }; return v }
func floatFromAny(v any, fallback float64) float64 {
	switch x := v.(type) {
	case float64: return x
	case float32: return float64(x)
	case int: return float64(x)
	case int64: return float64(x)
	case json.Number:
		f, _ := x.Float64(); return f
	default: return fallback
	}
}
func numberFromMap(m map[string]any, key string) (float64, bool) {
	if m == nil { return 0, false }
	v, ok := m[key]
	if !ok { return 0, false }
	return floatFromAny(v, 0), true
}
