-- The research-owned public-news query uses the versioned read projection.
GRANT SELECT ON read.news_v1 TO research_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA read GRANT SELECT ON TABLES TO research_runtime;
