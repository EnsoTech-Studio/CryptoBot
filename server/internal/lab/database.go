package lab

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

func OpenDatabase(ctx context.Context, databaseURL string) (*sql.DB, error) {
	if strings.TrimSpace(databaseURL) == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}

	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(12)
	db.SetMaxIdleConns(6)
	db.SetConnMaxLifetime(30 * time.Minute)

	deadline := time.Now().Add(45 * time.Second)
	for {
		if err := db.PingContext(ctx); err == nil {
			return db, nil
		}
		if time.Now().After(deadline) {
			_ = db.Close()
			return nil, fmt.Errorf("database is not ready")
		}
		select {
		case <-ctx.Done():
			_ = db.Close()
			return nil, ctx.Err()
		case <-time.After(750 * time.Millisecond):
		}
	}
}

func MigrateAndSeed(ctx context.Context, db *sql.DB) error {
	if _, err := db.ExecContext(ctx, schemaSQL); err != nil {
		return err
	}
	if err := seedUsers(ctx, db); err != nil {
		return err
	}
	if err := seedStrategies(ctx, db); err != nil {
		return err
	}
	if err := seedMarket(ctx, db); err != nil {
		return err
	}
	if err := seedNews(ctx, db); err != nil {
		return err
	}
	return seedLeaderboard(ctx, db)
}

const schemaSQL = `
CREATE SCHEMA IF NOT EXISTS read;

CREATE TABLE IF NOT EXISTS users (
	id TEXT PRIMARY KEY,
	email TEXT UNIQUE NOT NULL,
	display_name TEXT NOT NULL,
	password_hash TEXT NOT NULL,
	role TEXT NOT NULL CHECK (role IN ('RESEARCHER','OPERATOR','ADMIN')),
	is_active BOOLEAN NOT NULL DEFAULT true,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_quotas (
	user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
	max_concurrent_runs INT NOT NULL DEFAULT 2,
	max_candidates_per_run INT NOT NULL DEFAULT 50,
	max_candles_per_experiment INT NOT NULL DEFAULT 20000
);

CREATE TABLE IF NOT EXISTS market_pairs (
	provider TEXT NOT NULL,
	symbol TEXT NOT NULL,
	base_asset TEXT NOT NULL,
	quote_asset TEXT NOT NULL,
	timeframes TEXT[] NOT NULL,
	is_active BOOLEAN NOT NULL DEFAULT true,
	PRIMARY KEY (provider, symbol)
);

CREATE TABLE IF NOT EXISTS candles (
	provider TEXT NOT NULL,
	symbol TEXT NOT NULL,
	timeframe TEXT NOT NULL,
	open_time TIMESTAMPTZ NOT NULL,
	close_time TIMESTAMPTZ NOT NULL,
	open NUMERIC(24,8) NOT NULL,
	high NUMERIC(24,8) NOT NULL,
	low NUMERIC(24,8) NOT NULL,
	close NUMERIC(24,8) NOT NULL,
	volume NUMERIC(24,8) NOT NULL,
	trade_count INT NOT NULL,
	PRIMARY KEY (provider, symbol, timeframe, open_time),
	CHECK (high >= low)
);
CREATE INDEX IF NOT EXISTS idx_candles_range ON candles(provider, symbol, timeframe, open_time DESC);

CREATE TABLE IF NOT EXISTS stream_checkpoints (
	provider TEXT NOT NULL,
	symbol TEXT NOT NULL,
	timeframe TEXT NOT NULL,
	last_closed_at TIMESTAMPTZ,
	is_stale BOOLEAN NOT NULL DEFAULT false,
	reconnect_count INT NOT NULL DEFAULT 0,
	source_fetched_at TIMESTAMPTZ,
	PRIMARY KEY (provider, symbol, timeframe)
);
ALTER TABLE stream_checkpoints ADD COLUMN IF NOT EXISTS source_fetched_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS strategy_versions (
	id TEXT PRIMARY KEY,
	strategy_id TEXT NOT NULL,
	version TEXT NOT NULL,
	family TEXT,
	display_name TEXT NOT NULL,
	description TEXT NOT NULL,
	parameters_schema JSONB NOT NULL,
	input_requirements JSONB NOT NULL,
	overlay_types JSONB NOT NULL,
	warm_up_candles INT NOT NULL,
	is_composite BOOLEAN NOT NULL DEFAULT false,
	code_fingerprint TEXT NOT NULL,
	UNIQUE(strategy_id, version)
);

CREATE TABLE IF NOT EXISTS experiments (
	id TEXT PRIMARY KEY,
	owner_id TEXT NOT NULL REFERENCES users(id),
	strategy_id TEXT NOT NULL,
	strategy_version TEXT NOT NULL,
	candidate_definition JSONB NOT NULL,
	candidate_hash TEXT NOT NULL,
	provider TEXT NOT NULL,
	symbol TEXT NOT NULL,
	timeframe TEXT NOT NULL,
	dataset_version TEXT NOT NULL,
	content_hash TEXT NOT NULL,
	range_from TIMESTAMPTZ NOT NULL,
	range_to TIMESTAMPTZ NOT NULL,
	initial_equity NUMERIC(20,8) NOT NULL,
	fixed_notional NUMERIC(20,8) NOT NULL,
	leverage NUMERIC(12,4) NOT NULL,
	fee_bps INT NOT NULL,
	slippage_bps INT NOT NULL,
	fill_policy TEXT NOT NULL DEFAULT 'bbo_limit',
	position_policy TEXT NOT NULL DEFAULT 'one_net_position',
	open_position_at_end TEXT NOT NULL DEFAULT 'last_executable_bbo',
	risk_policy JSONB,
	evaluator_version TEXT NOT NULL DEFAULT '1.0.0',
	search_run_id TEXT,
	generated_by TEXT,
	generation_meta JSONB,
	idempotency_key TEXT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	UNIQUE(owner_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_experiments_owner ON experiments(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_hash ON experiments(candidate_hash, dataset_version);

CREATE TABLE IF NOT EXISTS backtest_jobs (
	id TEXT PRIMARY KEY,
	experiment_id TEXT UNIQUE NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','leased','completed','failed','cancelled')),
	priority INT NOT NULL DEFAULT 100,
	attempt INT NOT NULL DEFAULT 0,
	max_attempts INT NOT NULL DEFAULT 3,
	leased_by TEXT,
	lease_token TEXT,
	lease_expires_at TIMESTAMPTZ,
	last_error TEXT,
	enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_claimable ON backtest_jobs(priority, enqueued_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_jobs_expired_lease ON backtest_jobs(lease_expires_at) WHERE status = 'leased';

CREATE TABLE IF NOT EXISTS backtest_runs (
	id TEXT PRIMARY KEY,
	experiment_id TEXT UNIQUE NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed','cancelled')),
	worker_id TEXT,
	lease_token TEXT,
	attempt INT NOT NULL DEFAULT 0,
	candles_read INT NOT NULL DEFAULT 0,
	signals_count INT NOT NULL DEFAULT 0,
	duration_ms INT NOT NULL DEFAULT 0,
	error_code TEXT,
	error_detail TEXT,
	started_at TIMESTAMPTZ,
	finished_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trades (
	id TEXT PRIMARY KEY,
	experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	sequence_no INT NOT NULL,
	side TEXT NOT NULL,
	entry_time TIMESTAMPTZ NOT NULL,
	exit_time TIMESTAMPTZ NOT NULL,
	entry_price NUMERIC(24,8) NOT NULL,
	exit_price NUMERIC(24,8) NOT NULL,
	quantity NUMERIC(24,8) NOT NULL,
	pnl NUMERIC(20,8) NOT NULL,
	pnl_pct NUMERIC(12,6) NOT NULL,
	exit_reason TEXT NOT NULL,
	signal_t TIMESTAMPTZ NOT NULL,
	child_signals JSONB NOT NULL DEFAULT '{}',
	UNIQUE(experiment_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS run_signals (
	id TEXT PRIMARY KEY,
	experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	t TIMESTAMPTZ NOT NULL,
	action TEXT NOT NULL,
	confidence NUMERIC(8,4),
	evidence JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_run_signals_exp_t ON run_signals(experiment_id, t);

CREATE TABLE IF NOT EXISTS equity_points (
	experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	t TIMESTAMPTZ NOT NULL,
	equity NUMERIC(20,8) NOT NULL,
	drawdown_pct NUMERIC(12,6) NOT NULL,
	PRIMARY KEY(experiment_id, t)
);

CREATE TABLE IF NOT EXISTS evaluations (
	id TEXT PRIMARY KEY,
	experiment_id TEXT UNIQUE NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
	evaluator_version TEXT NOT NULL,
	total_return_pct NUMERIC(12,6) NOT NULL,
	win_rate_pct NUMERIC(12,6) NOT NULL,
	max_drawdown_pct NUMERIC(12,6) NOT NULL,
	trade_count INT NOT NULL,
	profit_factor NUMERIC(12,6) NOT NULL,
	sharpe_ratio NUMERIC(12,6) NOT NULL,
	score NUMERIC(12,6) NOT NULL,
	computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leaderboard_entries (
	id TEXT PRIMARY KEY,
	evaluation_id TEXT UNIQUE NOT NULL REFERENCES evaluations(id) ON DELETE RESTRICT,
	experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE RESTRICT,
	score_policy_version TEXT NOT NULL DEFAULT 'v1',
	score NUMERIC(12,6) NOT NULL,
	dataset_version TEXT NOT NULL,
	observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leaderboard_topk ON leaderboard_entries(dataset_version, score_policy_version, score DESC, observed_at DESC);

CREATE TABLE IF NOT EXISTS search_runs (
	id TEXT PRIMARY KEY,
	owner_id TEXT NOT NULL REFERENCES users(id),
	generator_id TEXT NOT NULL,
	status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('queued','running','paused','completed','failed','cancelled')),
	generated INT NOT NULL DEFAULT 0,
	tested INT NOT NULL DEFAULT 0,
	failed INT NOT NULL DEFAULT 0,
	best_score NUMERIC(12,6),
	current_candidate TEXT,
	stop_conditions JSONB NOT NULL,
	dataset_version TEXT NOT NULL,
	content_hash TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	stop_reason TEXT,
	idempotency_key TEXT,
	UNIQUE(owner_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS search_actions (
	command_id TEXT PRIMARY KEY,
	search_run_id TEXT NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
	action TEXT NOT NULL,
	actor_id TEXT NOT NULL REFERENCES users(id),
	requested_from TEXT,
	resulted_in TEXT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS news_sources (
	id TEXT PRIMARY KEY,
	source_key TEXT UNIQUE NOT NULL,
	display_name TEXT NOT NULL,
	kind TEXT NOT NULL,
	allowed_origin TEXT NOT NULL,
	url_template TEXT NOT NULL,
	is_active BOOLEAN NOT NULL DEFAULT true,
	last_collected_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS news_collection_jobs (
	id TEXT PRIMARY KEY,
	source_id TEXT NOT NULL REFERENCES news_sources(id),
	status TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
	items_found INT NOT NULL DEFAULT 0,
	items_new INT NOT NULL DEFAULT 0,
	failure_reason TEXT,
	started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS news_items (
	id TEXT PRIMARY KEY,
	source_id TEXT NOT NULL REFERENCES news_sources(id),
	url TEXT NOT NULL,
	url_hash TEXT UNIQUE NOT NULL,
	title TEXT NOT NULL,
	content TEXT,
	published_at TIMESTAMPTZ NOT NULL,
	related_coins TEXT[] NOT NULL DEFAULT '{}',
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_time ON news_items(published_at DESC);

CREATE TABLE IF NOT EXISTS sentiment_results (
	id TEXT PRIMARY KEY,
	news_item_id TEXT NOT NULL REFERENCES news_items(id) ON DELETE CASCADE,
	label TEXT NOT NULL CHECK (label IN ('POSITIVE','NEUTRAL','NEGATIVE')),
	score NUMERIC(8,4) NOT NULL,
	model TEXT NOT NULL,
	model_version TEXT NOT NULL,
	analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	UNIQUE(news_item_id, model, model_version)
);

CREATE TABLE IF NOT EXISTS domain_events (
	event_id TEXT PRIMARY KEY,
	event_type TEXT NOT NULL,
	schema_version INT NOT NULL DEFAULT 1,
	aggregate_type TEXT NOT NULL,
	aggregate_id TEXT NOT NULL,
	correlation_id TEXT,
	payload JSONB NOT NULL,
	occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_consumptions (
	event_id TEXT NOT NULL REFERENCES domain_events(event_id) ON DELETE CASCADE,
	consumer TEXT NOT NULL,
	consumed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	PRIMARY KEY(event_id, consumer)
);

CREATE OR REPLACE VIEW read.candles_v1 AS SELECT * FROM candles;
CREATE OR REPLACE VIEW read.experiment_summary_v1 AS
	SELECT e.*, br.id AS run_id, br.status, br.started_at, br.finished_at, br.candles_read, br.signals_count, br.error_code,
	       ev.id AS evaluation_id, ev.total_return_pct, ev.win_rate_pct, ev.max_drawdown_pct,
	       ev.trade_count, ev.profit_factor, ev.sharpe_ratio, ev.score, ev.evaluator_version AS computed_evaluator_version
	FROM experiments e
	LEFT JOIN backtest_runs br ON br.experiment_id = e.id
	LEFT JOIN evaluations ev ON ev.experiment_id = e.id;
CREATE OR REPLACE VIEW read.trades_v1 AS SELECT * FROM trades;
CREATE OR REPLACE VIEW read.run_signals_v1 AS SELECT * FROM run_signals;
CREATE OR REPLACE VIEW read.equity_v1 AS SELECT * FROM equity_points;
CREATE OR REPLACE VIEW read.leaderboard_v1 AS
	SELECT le.*, ev.total_return_pct, ev.win_rate_pct, ev.max_drawdown_pct, ev.trade_count, ev.profit_factor, ev.sharpe_ratio,
	       e.strategy_id, e.strategy_version, e.candidate_hash, e.dataset_version AS experiment_dataset_version
	FROM leaderboard_entries le
	JOIN evaluations ev ON ev.id = le.evaluation_id
	JOIN experiments e ON e.id = le.experiment_id;
CREATE OR REPLACE VIEW read.news_v1 AS
	SELECT ni.*, ns.source_key, ns.display_name
	FROM news_items ni JOIN news_sources ns ON ns.id = ni.source_id;
CREATE OR REPLACE VIEW read.search_run_v1 AS SELECT * FROM search_runs;
`

func seedUsers(ctx context.Context, db *sql.DB) error {
	users := []struct {
		email, name, role, password string
	}{
		{"researcher@example.com", "Demo Researcher", "RESEARCHER", "Research#2026"},
		{"operator@example.com", "Demo Operator", "OPERATOR", "Operator#2026"},
		{"admin@example.com", "Demo Admin", "ADMIN", "Admin#2026"},
	}
	for _, u := range users {
		id := uuid.NewString()
		hash := hashPassword(u.password)
		if _, err := db.ExecContext(ctx, `
			INSERT INTO users(id,email,display_name,password_hash,role)
			VALUES($1,$2,$3,$4,$5)
			ON CONFLICT(email) DO UPDATE SET display_name=EXCLUDED.display_name, password_hash=EXCLUDED.password_hash, role=EXCLUDED.role, is_active=true
		`, id, u.email, u.name, hash, u.role); err != nil {
			return err
		}
		if _, err := db.ExecContext(ctx, `
			INSERT INTO user_quotas(user_id)
			SELECT id FROM users WHERE email=$1
			ON CONFLICT(user_id) DO NOTHING
		`, u.email); err != nil {
			return err
		}
	}
	return nil
}

func seedStrategies(ctx context.Context, db *sql.DB) error {
	strategies := BuiltInStrategies()
	for _, s := range strategies {
		params, _ := json.Marshal(s.ParametersSchema)
		inputs, _ := json.Marshal(s.InputRequirements)
		overlays, _ := json.Marshal(s.OverlayTypes)
		id := s.StrategyID + "@" + s.Version
		if _, err := db.ExecContext(ctx, `
			INSERT INTO strategy_versions(id,strategy_id,version,family,display_name,description,parameters_schema,input_requirements,overlay_types,warm_up_candles,is_composite,code_fingerprint)
			VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11,$12)
			ON CONFLICT(strategy_id, version) DO UPDATE SET
				display_name=EXCLUDED.display_name,
				description=EXCLUDED.description,
				parameters_schema=EXCLUDED.parameters_schema,
				input_requirements=EXCLUDED.input_requirements,
				overlay_types=EXCLUDED.overlay_types,
				warm_up_candles=EXCLUDED.warm_up_candles,
				code_fingerprint=EXCLUDED.code_fingerprint
		`, id, s.StrategyID, s.Version, s.Family, s.DisplayName, s.Description, string(params), string(inputs), string(overlays), s.WarmUpCandles, s.IsComposite, s.CodeFingerprint); err != nil {
			return err
		}
	}
	return nil
}

func seedMarket(ctx context.Context, db *sql.DB) error {
	if _, err := db.ExecContext(ctx, `
		INSERT INTO market_pairs(provider,symbol,base_asset,quote_asset,timeframes)
		VALUES($1,$2,'ETH','USDT',ARRAY['1m','5m','15m','1h','4h'])
		ON CONFLICT(provider, symbol) DO UPDATE SET timeframes=EXCLUDED.timeframes, is_active=true
	`, ProviderBinance, SymbolETHUSDT); err != nil {
		return err
	}
	for _, tf := range []string{"1m", "5m", "15m", "1h", "4h"} {
		_ = EnsureCandles(ctx, db, ProviderBinance, SymbolETHUSDT, tf, 260)
	}
	return nil
}

func seedNews(ctx context.Context, db *sql.DB) error {
	sourceID := "coindesk_rss"
	if _, err := db.ExecContext(ctx, `
		INSERT INTO news_sources(id, source_key, display_name, kind, allowed_origin, url_template, last_collected_at)
		VALUES($1,$1,'CoinDesk RSS','rss','https://www.coindesk.com','https://www.coindesk.com/arc/outboundfeeds/rss/', NULL)
		ON CONFLICT(id) DO UPDATE SET
			display_name=EXCLUDED.display_name,
			kind=EXCLUDED.kind,
			allowed_origin=EXCLUDED.allowed_origin,
			url_template=EXCLUDED.url_template,
			is_active=true
	`, sourceID); err != nil {
		return err
	}
	if _, err := db.ExecContext(ctx, `
		DELETE FROM sentiment_results WHERE news_item_id IN (
			SELECT id FROM news_items WHERE url LIKE 'https://www.coindesk.com/demo/%'
		)
	`); err != nil {
		return err
	}
	if _, err := db.ExecContext(ctx, `DELETE FROM news_items WHERE url LIKE 'https://www.coindesk.com/demo/%'`); err != nil {
		return err
	}
	_ = CollectApprovedNews(ctx, db)
	return nil
}

func seedLeaderboard(ctx context.Context, db *sql.DB) error {
	if err := resetSeedLeaderboard(ctx, db); err != nil {
		return err
	}

	var candleCount int
	if err := db.QueryRowContext(ctx, `
		SELECT count(*) FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe='5m'
	`, ProviderBinance, SymbolETHUSDT).Scan(&candleCount); err != nil {
		return err
	}
	if candleCount < 80 {
		return nil
	}

	owner, err := demoResearcherID(ctx, db)
	if err != nil {
		return err
	}
	combos := [][]string{
		{"ma_cross", "rsi", "support_resistance"},
		{"ma_cross", "bollinger"},
		{"rsi", "support_resistance"},
	}
	for idx, combo := range combos {
		req := DefaultExperimentRequest()
		req.Children = nil
		for _, id := range combo {
			req.Children = append(req.Children, StrategyChild{StrategyID: id, Version: "1.0.0", Parameters: DefaultParams(id), Weight: 1})
		}
		req.IdempotencyKey = fmt.Sprintf("seed-leaderboard-%d", idx+1)
		accepted, err := CreateExperiment(ctx, db, owner, req, 90)
		if err != nil {
			if strings.Contains(err.Error(), "market_data_unavailable") || strings.Contains(err.Error(), "dataset_too_small") {
				return nil
			}
			return err
		}
		if err := RunExperimentNow(ctx, db, accepted.ExperimentID, "seed-worker"); err != nil {
			if strings.Contains(err.Error(), "market_data_unavailable") || strings.Contains(err.Error(), "dataset_too_small") {
				return nil
			}
			return err
		}
	}
	return nil
}

func resetSeedLeaderboard(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, `
		DELETE FROM leaderboard_entries
		WHERE experiment_id IN (SELECT id FROM experiments WHERE idempotency_key LIKE 'seed-leaderboard-%')
	`); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		DELETE FROM evaluations
		WHERE experiment_id IN (SELECT id FROM experiments WHERE idempotency_key LIKE 'seed-leaderboard-%')
	`); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		DELETE FROM experiments WHERE idempotency_key LIKE 'seed-leaderboard-%'
	`); err != nil {
		return err
	}
	return tx.Commit()
}

func EnsureCandles(ctx context.Context, db *sql.DB, provider, symbol, timeframe string, desired int) error {
	if desired <= 0 {
		desired = 180
	}
	var existing int
	var fetchedAt sql.NullTime
	err := db.QueryRowContext(ctx, `
		SELECT
			(SELECT count(*) FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe=$3),
			source_fetched_at
		FROM stream_checkpoints
		WHERE provider=$1 AND symbol=$2 AND timeframe=$3
	`, provider, symbol, timeframe).Scan(&existing, &fetchedAt)
	if err != nil && err != sql.ErrNoRows {
		return err
	}
	if existing >= desired && fetchedAt.Valid && time.Since(fetchedAt.Time) < 20*time.Second {
		return nil
	}
	candles, err := FetchBinanceCandles(ctx, provider, symbol, timeframe, desired)
	if err != nil {
		_, _ = db.ExecContext(ctx, `
			INSERT INTO stream_checkpoints(provider,symbol,timeframe,last_closed_at,is_stale,reconnect_count)
			VALUES($1,$2,$3,(SELECT max(open_time) FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe=$3),true,1)
			ON CONFLICT(provider, symbol, timeframe) DO UPDATE SET is_stale=true, reconnect_count=stream_checkpoints.reconnect_count+1
		`, provider, symbol, timeframe)
		if existing >= desired && fetchedAt.Valid {
			return nil
		}
		return fmt.Errorf("market_data_unavailable: %w", err)
	}
	if len(candles) == 0 {
		return fmt.Errorf("market_data_unavailable: no closed candles returned")
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, `DELETE FROM candles WHERE provider=$1 AND symbol=$2 AND timeframe=$3`, provider, symbol, timeframe); err != nil {
		return err
	}
	for _, c := range candles {
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO candles(provider,symbol,timeframe,open_time,close_time,open,high,low,close,volume,trade_count)
			VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
			ON CONFLICT(provider, symbol, timeframe, open_time) DO UPDATE SET
				close_time=EXCLUDED.close_time,
				open=EXCLUDED.open,
				high=EXCLUDED.high,
				low=EXCLUDED.low,
				close=EXCLUDED.close,
				volume=EXCLUDED.volume,
				trade_count=EXCLUDED.trade_count
		`, c.Provider, c.Symbol, c.Timeframe, c.OpenTime, c.CloseTime, c.Open, c.High, c.Low, c.Close, c.Volume, c.TradeCount); err != nil {
			return err
		}
	}
	lastClosed := candles[len(candles)-1].OpenTime
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO stream_checkpoints(provider,symbol,timeframe,last_closed_at,is_stale,reconnect_count,source_fetched_at)
		VALUES($1,$2,$3,$4,false,0,now())
		ON CONFLICT(provider, symbol, timeframe) DO UPDATE SET last_closed_at=$4, is_stale=false, source_fetched_at=now()
	`, provider, symbol, timeframe, lastClosed); err != nil {
		return err
	}
	return tx.Commit()
}

func RefreshRealMarket(ctx context.Context, db *sql.DB) error {
	for _, tf := range []string{"1m", "5m", "15m", "1h", "4h"} {
		if err := EnsureCandles(ctx, db, ProviderBinance, SymbolETHUSDT, tf, 260); err != nil {
			return err
		}
	}
	return nil
}

func timeframeDuration(tf string) time.Duration {
	switch tf {
	case "1m":
		return time.Minute
	case "5m":
		return 5 * time.Minute
	case "15m":
		return 15 * time.Minute
	case "1h":
		return time.Hour
	case "4h":
		return 4 * time.Hour
	default:
		return 5 * time.Minute
	}
}

func demoResearcherID(ctx context.Context, db *sql.DB) (string, error) {
	var id string
	err := db.QueryRowContext(ctx, `SELECT id FROM users WHERE email='researcher@example.com'`).Scan(&id)
	return id, err
}

func hashPassword(password string) string {
	sum := sha256.Sum256([]byte("cryptobot-demo:" + password))
	return "sha256:" + hex.EncodeToString(sum[:])
}

func verifyPassword(hash, password string) bool {
	return hash == hashPassword(password)
}

func sha256Hex(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}
