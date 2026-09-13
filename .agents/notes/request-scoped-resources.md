# Request-scoped resources

Design notes for how `FilePersistence` should be expressed. Describes an
intended change; remove or rewrite once the change lands.

## The problem

`FilePersistence` holds an exclusive `flock` for the duration of a request. It
must acquire the lock before any component's `before` hook and release it after
every `after` hook, because `data.Component` and `session.Component` both load
and save through `ctx.persistence`.

`Component` cannot express this. Its vocabulary is `before` and `after`, two
separate calls, and a lock is something you *hold* — it needs a live stack
frame spanning the rest of the chain. So persistence was lifted out of the
component list into a public `middleware=` parameter on `Application`.

That parameter is the wrong shape for application code. Middleware is the
framework's own spine — `ensure_content_length`, `capture_errors`,
`adapt_artificial_method`. `Component` exists so application developers never
have to think in terms of `(req, ctx, next)`. Cork now has to, for one feature.

## Why the obvious fixes are wrong

The tempting move is to give `Component` a wrapping hook: a `scope()` returning
a context manager, a generator-based `around()`, or a `before` that returns a
teardown callable.

All three exist for the same reason — to give a component somewhere to stand
while a resource stays open — and all three tax every component with a concept
almost none of them need. `persist.Lock` is already a context manager. A
wrapping hook adds nothing to it but a place to put the `with`.

Putting persistence back into `Application.__init__` as a dedicated parameter
is worse. It makes one feature privileged in the framework core, and it
inverts the dependency: `helios.persist` imports `Context` and `Next` from
`helios.app`, so `helios.app` cannot import `Files` without a cycle. That cycle
is why the parameter came out in the first place.

## The change

The missing concept is not a component hook. It is a request-scoped resource
with deterministic teardown, and it belongs to `Context`.

`Context` gains one method. Its lookup also simplifies, because `__getattr__`
only fires when normal attribute lookup fails, so the `"provided"` special
cases are unnecessary:

```python
class Context:
	def __init__(self):
		self.__dict__["provided"] = {}
		self.__dict__["resources"] = ExitStack()

	def __getattr__(self, name: str) -> Any:
		if name in self.provided:
			return self.provided[name]
		raise AttributeError(f"nothing provides '{name}' on the request context")

	def __setattr__(self, name: str, val: Any):
		self.provided[name] = val

	def use[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)
```

The stack is entered by one new entry in the fixed spine:

```python
def scope_resources(req: Request, ctx: Context, next: Next) -> Response:
	with ctx.resources:
		return next(req, ctx)
```

Its position matters. It sits *inside* `capture_errors`, so resources unwind
with the exception still in flight and a future transactional resource can
distinguish rollback from commit. Outside `capture_errors`, the failure would
already have become a 500 response and every resource would see a clean exit.

`FilePersistence` becomes an ordinary component:

```python
class Component(BaseComponent):
	def __init__(self, files: Files):
		self.files = files

	def before(self, req: Request, ctx: Context):
		ctx.persistence = ctx.use(self.files.lock())
```

`middleware=` is removed from `Application.__init__`, and Cork wires every
capability in one list, where reading order is execution order:

```python
[
	helios.persist.Component(self.persistence),
	helios.data.Component(self.store_data),
	helios.views.Component(views_dir),
	helios.session.Component(self.sessions_data),
	helios.flash.Component(),
	helios.auth.Component(User),
]
```

## The argument

- `Component` keeps a single vocabulary. No optional third hook left empty by
  most components, no generator protocol inside a subclass override.
- Resource acquisition composes flatly. Five components acquiring resources is
  five `ExitStack` entries, not five nested `Thread` frames, and teardown is
  LIFO for free.
- `helios.app` learns nothing about persistence, so the import cycle stays
  broken and no feature is privileged in the core.
- It generalizes to the next resource — a connection, a request-scoped temp
  directory, an open file, a tracing span — without a new framework concept.
- `middleware=` can close again. Nothing in application code needs it once
  resources have a home.

This is also the closer reading of Laravel, which `Component` came from.
Laravel keeps service providers separate from middleware precisely because "I
supply a thing" and "I wrap the pipeline" are different jobs, and request-
lifetime instances are a container concern (`scoped()` bindings) rather than a
middleware one. `Context` is Helios's container; `use` is `scoped()` with
deterministic teardown instead of a flush between requests.

## What this deliberately does not solve

`use` buys acquisition and release. It does not let a component short-circuit
the chain or inspect the response mid-flight.

Components cannot cleanly short-circuit today either. `handle_http_errors` sits
inside the component chain, so an `HTTPError` raised by a route guard is
converted with every `after` hook intact, while the same error raised from a
component's `before` escapes to `capture_errors` and becomes a 500.

That is a real gap, but it is about control flow, not resources. If a component
ever needs to redirect an unauthenticated request, the fix is to move the
HTTP-error boundary outward — not to add a wrapping hook to `Component` and
hope it covers both concerns.

## Implementation order

1. Add `Context.use` and `scope_resources`; simplify `Context` lookup.
2. Replace `persist.FilePersistence` with `persist.Component`.
3. Remove `middleware=` from `Application.__init__`.
4. Restore the persistence-scope coverage deleted from `test/app_test.py` and
   `test/persistence_integration_test.py` against the new shape.
5. Rewire Cork's `app/__init__.py` as a single component list.
