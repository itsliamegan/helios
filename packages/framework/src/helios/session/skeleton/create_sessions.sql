CREATE TABLE sessions (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	token TEXT NOT NULL UNIQUE,
	items TEXT NOT NULL,
	last_active_at TEXT NOT NULL
) STRICT;

CREATE INDEX sessions_last_active_at ON sessions (last_active_at);
