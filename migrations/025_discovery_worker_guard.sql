-- Prevent the legacy worker identity from claiming discovery partitions.
-- The old worker-1 implementation completes discovery candidates as ordinary
-- searches, which can bypass validation and sealed-test orchestration.

CREATE OR REPLACE FUNCTION public.reject_legacy_discovery_worker()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.status = 'leased'
       AND NEW.leased_by = 'worker-1'
       AND EXISTS (
           SELECT 1
           FROM experiments e
           JOIN search_candidates c ON c.id = e.search_candidate_id
           JOIN search_runs s ON s.id = c.search_run_id
           WHERE e.id = NEW.experiment_id
             AND s.generator_id = 'discovery'
       ) THEN
        RAISE EXCEPTION
            'legacy worker identity worker-1 cannot claim discovery jobs; use worker-v2'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discovery_worker_identity_guard ON backtest_jobs;
CREATE TRIGGER discovery_worker_identity_guard
    BEFORE UPDATE OF status, leased_by ON backtest_jobs
    FOR EACH ROW
    EXECUTE FUNCTION public.reject_legacy_discovery_worker();

CREATE OR REPLACE FUNCTION public.reject_legacy_discovery_event_worker()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.dispatch_status = 'claimed'
       AND NEW.claimed_by = 'events-1'
       AND NEW.event_type = 'BacktestCompleted'
       AND EXISTS (
           SELECT 1
           FROM backtest_runs r
           JOIN experiments e ON e.id = r.experiment_id
           JOIN search_candidates c ON c.id = e.search_candidate_id
           JOIN search_runs s ON s.id = c.search_run_id
           WHERE r.id = NEW.aggregate_id
             AND s.generator_id = 'discovery'
       ) THEN
        RAISE EXCEPTION
            'legacy event worker identity events-1 cannot claim discovery events; use events-v2'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discovery_event_worker_identity_guard ON domain_events;
CREATE TRIGGER discovery_event_worker_identity_guard
    BEFORE UPDATE OF dispatch_status, claimed_by ON domain_events
    FOR EACH ROW
    EXECUTE FUNCTION public.reject_legacy_discovery_event_worker();

GRANT EXECUTE ON FUNCTION public.reject_legacy_discovery_worker() TO research_runtime;
GRANT EXECUTE ON FUNCTION public.reject_legacy_discovery_event_worker() TO research_runtime;
