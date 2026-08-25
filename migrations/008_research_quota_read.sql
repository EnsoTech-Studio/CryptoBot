-- Research enforces experiment/search quotas atomically but never mutates the
-- Go-owned auth/quota records. Per-owner advisory transaction locks serialize
-- decisions, so read-only access is sufficient.
GRANT SELECT ON user_quotas TO research_runtime;
