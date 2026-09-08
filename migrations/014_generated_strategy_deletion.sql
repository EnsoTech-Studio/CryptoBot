-- Generated strategies may be withdrawn only before they become experiment
-- evidence.  The repository scopes this setting with SET LOCAL.
CREATE OR REPLACE FUNCTION reject_immutable_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'strategy_versions'
       AND TG_OP = 'DELETE'
       AND current_setting('cryptobot.allow_generated_strategy_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE='55000';
END $$;

GRANT DELETE ON strategy_definitions, strategy_versions, strategy_runtime_specs TO research_runtime;
