# Helios

Helios is a small Python web framework. It includes:

- [HTTP request and response handling](src/helios/http/)
- [Routing with optionally typed parameters](src/helios/routing/)
- [Application, dependency container, and request contexts](src/helios/app/)
- [WSGI adapter](src/helios/wsgi.py)
- [SQLite-backed models and queries](src/helios/database/)
- [View rendering](src/helios/views/)
- [Form validation](src/helios/form/)
- [File-backed sessions](src/helios/session/)
- [Authentication](src/helios/auth/)

It is small enough to read and understand in an afternoon.

## Applications and providers

An `Application` owns its dependency `Container`, HTTP pipeline, and lifecycle.
Feature `Provider` objects register application singleton or request-scoped
services, then install middleware during boot. Construction registers and boots
all providers synchronously, so an application can handle requests immediately.
The host calls `close()` during shutdown.

```python
from pathlib import Path

import helios.app
import helios.database
import helios.session
import helios.session.file
from helios.routing import Router


class Post(helios.database.Model):
	table = "posts"

	title = helios.database.attr(str)
	body = helios.database.attr(str)


database_config = helios.database.Config(Path("var/application.sqlite"))
session_config = helios.session.Config(secure=True)
session_driver = helios.session.file.Driver(
	Path("var/sessions.json"),
	Path("var/sessions.lock"),
)

app = helios.app.Application(
	helios.app.Config(base_url=base_url),
	Router(routes),
	[
		helios.session.Provider(session_config, driver=session_driver),
		helios.database.Provider(database_config, [Post]),
	],
)

try:
	response = app.handle(request)
finally:
	app.close()
```

Services are keyed by Python types and use explicit factories. Singleton
services live in the application container. Scoped services are constructed
lazily once per request and are available through the request `Context`:

```python
def handler(request, context):
	store = context.get(helios.database.Store)
	posts = store.query(Post).order_by("created_at", "desc").all()
	return Response.text(str(posts))
```

`Container.enter()` owns application-lifetime context-managed resources, while
`Context.enter()` owns request resources. Each owner releases its resources in
reverse acquisition order.

## Database schema and transactions

Applications own their SQL DDL and every schema migration. Helios does not
infer tables, generate DDL, apply migrations, or support interchangeable
relational drivers. Each registered model must declare its own table and the
application schema must provide `id`, `created_at`, and every declared model
attribute as same-named columns. For example:

```sql
CREATE TABLE posts (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	title TEXT NOT NULL,
	body TEXT NOT NULL
);
```

Database access is lazy. Resolving `helios.database.Store` opens one SQLite
connection and starts one `BEGIN IMMEDIATE` transaction for the request. Normal
returns—including redirects, handled HTTP errors, and explicitly returned error
responses—commit. Unexpected exceptions roll back. Every connection enables
foreign keys and uses the configured busy timeout.

Sessions are also lazy and remain file-backed. A request using both sessions and
the database must resolve the session first, then the database store. This keeps
the session file lock before the database transaction and avoids inconsistent
lock ordering. Authentication follows this order automatically.

## Tests

Tests for each module sit in `test/` and are the fastest way to see intended
usage. Run them with:

```
mise run test
```
