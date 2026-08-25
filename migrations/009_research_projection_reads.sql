-- Research owns leaderboard calculation and may read its versioned projection.
-- This is read-only and does not widen access to Go-owned operational tables.
GRANT SELECT ON read.leaderboard_v1 TO research_runtime;
