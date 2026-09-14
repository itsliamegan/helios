# Helios

Helios is a small Python web framework. It includes:

- [HTTP request and response handling](src/helios/http/)
- [Routing with optionally typed parameters](src/helios/routing/)
- [Application, dependency container, and request contexts](src/helios/app/)
- [WSGI adapter](src/helios/wsgi.py)
- [Data storage and model definitions](src/helios/data/)
- [View rendering](src/helios/views/)
- [Form validation](src/helios/form/)
- [Cookie-backed sessions](src/helios/session/)
- [Authentication](src/helios/auth/)

It is small enough to read and understand in an afternoon.

## Applications and providers

An `Application` owns its dependency `Container`, HTTP pipeline, and lifecycle.
Feature `Provider` objects register application singleton or request-scoped
services, then install middleware during boot. Construction registers and boots
all providers synchronously, so an application can handle requests immediately.
The host calls `close()` during shutdown. Helios expects applications and
providers to follow this sequence; lifecycle misuse is unsupported rather than
explicitly detected. Standalone middleware can be passed as a fourth constructor
argument and runs inside provider-installed middleware.

```python
import helios.app
import helios.data
import helios.persist
from helios.persist.files import Files
from helios.routing import Router

files = Files(persistence_config)
app = helios.app.Application(
	helios.app.Config(base_url=base_url),
	Router(routes),
	[
		helios.persist.Provider(files),
		helios.data.Provider(data_config, files, schema),
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
	store = context.get(Store)
	return Response.text(str(store.find_all(Post)))
```

`Container.enter()` owns application-lifetime context-managed resources, while
`Context.enter()` owns request resources. Each owner releases its resources in
reverse acquisition order.

## Tests

Tests for each module sit in `test/` and are the fastest way to see intended
usage. Run them with:

```
mise run test
```
