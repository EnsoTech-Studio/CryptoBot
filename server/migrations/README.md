# Database migrations

Production migrations live in the repository-level `migrations/` directory and
are applied by `python -m app.migrate` before the Go API starts. The Go runtime
never creates or alters schema during normal startup.

