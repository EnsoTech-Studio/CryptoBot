-- A backtest range is part of the immutable experiment snapshot, not a UI-only filter.
ALTER TABLE experiments
    ADD COLUMN replay_range_from TIMESTAMPTZ,
    ADD COLUMN replay_range_to TIMESTAMPTZ;

UPDATE experiments e
SET replay_range_from=d.range_from,replay_range_to=d.range_to
FROM market_datasets d
WHERE d.id=e.market_dataset_id;

ALTER TABLE experiments
    ALTER COLUMN replay_range_from SET NOT NULL,
    ALTER COLUMN replay_range_to SET NOT NULL,
    ADD CONSTRAINT experiments_replay_range_check CHECK (replay_range_to > replay_range_from);
