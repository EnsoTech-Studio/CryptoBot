-- Artifact bytes can legitimately recur across independently reviewed drafts.
-- Draft/revision is the ownership boundary; artifact_hash remains immutable evidence.
ALTER TABLE strategy_artifacts
    DROP CONSTRAINT IF EXISTS strategy_artifacts_artifact_hash_key;
