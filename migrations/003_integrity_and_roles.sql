DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='api_runtime') THEN
        CREATE ROLE api_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='research_runtime') THEN
        CREATE ROLE research_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='api_reader') THEN
        CREATE ROLE api_reader NOLOGIN;
    END IF;
END $$;

CREATE FUNCTION reject_immutable_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE='55000';
END $$;

CREATE TRIGGER strategy_versions_immutable
BEFORE UPDATE OR DELETE ON strategy_versions
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER market_datasets_immutable
BEFORE UPDATE OR DELETE ON market_datasets
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER market_dataset_candles_immutable
BEFORE UPDATE OR DELETE ON market_dataset_candles
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER market_dataset_bbo_immutable
BEFORE UPDATE OR DELETE ON market_dataset_bbo
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER experiments_immutable
BEFORE UPDATE OR DELETE ON experiments
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER trades_immutable
BEFORE UPDATE OR DELETE ON trades
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER run_signals_immutable
BEFORE UPDATE OR DELETE ON run_signals
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER equity_points_immutable
BEFORE UPDATE OR DELETE ON equity_points
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER evaluations_immutable
BEFORE UPDATE OR DELETE ON evaluations
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();
CREATE TRIGGER leaderboard_entries_immutable
BEFORE UPDATE OR DELETE ON leaderboard_entries
FOR EACH ROW EXECUTE FUNCTION reject_immutable_mutation();

CREATE FUNCTION validate_score_policy() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    total NUMERIC;
BEGIN
    IF NEW.weights = '{}'::jsonb THEN
        RAISE EXCEPTION 'score policy weights are required' USING ERRCODE='23514';
    END IF;
    SELECT sum(value::numeric) INTO total FROM jsonb_each_text(NEW.weights);
    IF abs(total - 1.0) > 0.000000001 THEN
        RAISE EXCEPTION 'score policy weights must sum to 1.0' USING ERRCODE='23514';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each_text(NEW.weights) WHERE value::numeric < 0) THEN
        RAISE EXCEPTION 'score policy weights must be non-negative' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER score_policy_validate
BEFORE INSERT ON score_policies
FOR EACH ROW EXECUTE FUNCTION validate_score_policy();

CREATE FUNCTION guard_score_policy_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'score_policies is append-only' USING ERRCODE='55000';
    END IF;
    IF COALESCE(current_setting('cryptobot.policy_activation', TRUE), '') <> 'on'
       OR NEW.version <> OLD.version
       OR NEW.min_trades <> OLD.min_trades
       OR NEW.weights <> OLD.weights
       OR NEW.formula <> OLD.formula
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'score policy activation must use activate_score_policy()'
            USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER score_policies_immutable
BEFORE UPDATE OR DELETE ON score_policies
FOR EACH ROW EXECUTE FUNCTION guard_score_policy_mutation();

CREATE FUNCTION activate_score_policy(target_version VARCHAR) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('score-policy-activation'));
    IF NOT EXISTS (SELECT 1 FROM score_policies WHERE version=target_version) THEN
        RAISE EXCEPTION 'score policy not found' USING ERRCODE='P0002';
    END IF;
    PERFORM set_config('cryptobot.policy_activation','on',TRUE);
    UPDATE score_policies SET is_active=FALSE WHERE is_active AND version<>target_version;
    UPDATE score_policies SET is_active=TRUE WHERE version=target_version AND NOT is_active;
    IF (SELECT count(*) FROM score_policies WHERE is_active) <> 1 THEN
        RAISE EXCEPTION 'exactly one score policy must be active' USING ERRCODE='23514';
    END IF;
END $$;

CREATE FUNCTION validate_leaderboard_dataset() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    expected UUID;
BEGIN
    SELECT x.market_dataset_id INTO expected
    FROM evaluations e
    JOIN backtest_runs r ON r.id=e.backtest_run_id
    JOIN experiments x ON x.id=r.experiment_id
    WHERE e.id=NEW.evaluation_id;
    IF expected IS NULL OR expected <> NEW.market_dataset_id THEN
        RAISE EXCEPTION 'leaderboard dataset does not match evaluation provenance'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER leaderboard_dataset_match
BEFORE INSERT ON leaderboard_entries
FOR EACH ROW EXECUTE FUNCTION validate_leaderboard_dataset();

GRANT USAGE ON SCHEMA public,read TO api_runtime,research_runtime,api_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA read TO api_runtime,api_reader;

GRANT SELECT,INSERT,UPDATE ON users,refresh_tokens,user_quotas,market_pairs,candles,
    stream_checkpoints,market_datasets,market_dataset_candles,market_dataset_bbo
    TO api_runtime;
GRANT SELECT ON strategy_definitions,strategy_versions,experiments,backtest_jobs,
    backtest_runs,trades,run_signals,equity_points,evaluations,search_runs,
    leaderboard_entries,news_items,sentiment_results,score_policies TO api_runtime;

GRANT SELECT ON users,market_pairs,candles,stream_checkpoints,market_datasets,
    market_dataset_candles,market_dataset_bbo TO research_runtime;
GRANT SELECT,INSERT,UPDATE ON strategy_definitions,experiments,backtest_jobs,
    backtest_runs,domain_events,event_consumptions,search_runs,search_candidates,
    search_actions,news_sources,news_collection_jobs,news_items TO research_runtime;
GRANT SELECT,INSERT ON strategy_versions,trades,run_signals,equity_points,evaluations,
    leaderboard_entries,sentiment_results,score_policies TO research_runtime;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO api_runtime,research_runtime;
GRANT EXECUTE ON FUNCTION activate_score_policy(VARCHAR) TO research_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA read GRANT SELECT ON TABLES TO api_runtime,api_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO api_runtime,research_runtime;
