# Typed component container

## Goal

Replace the string namespace on `Context` with type keys, so that what a
component provides, what it requires, and what handlers read are the same
declaration checked by the type checker:

```python
class Component(Component[Store]):
	provides = Store
	requires = (Persistence,)

	def provide(self, req: Request, ctx: Context) -> Store: ...
```

```python
store = ctx.get(Store)
```

`ctx.get` is typed, `verify` keeps its boot-time ordering check, and
`provides = Store` and `provide() -> Store` are bound to the same parameter so a
mismatch is an author-time error rather than a runtime surprise.

Along the way, remove `Context.own` by making persistence handles recoverable,
and give sessions the dirty check the store already has.

## Current behavior

`Context` keeps `_provided` keyed by string and exposes it through `__getattr__`
and `__setattr__`, so `ctx.store` returns `Any`. `Component` declares
`provides: str` and `requires: tuple[str, ...]`, and `Component.__call__` binds
the provided value with `setattr(ctx, self.provides, provided)`.

`verify` runs in `Application.__init__` and checks, in list order, that every
name in `requires` was provided earlier and that no name is provided twice. This
works, but the names are a nominal type system the checker cannot see, and a
`requires` entry has no relationship to the class it names.

Two components keep request state in `Context.own(self)`, a `SimpleNamespace`
held in `_owned` and keyed by the component instance:

- `data.Component` stores the `Handle[Store]` opened in `provide` so `finish`
  can save through it;
- `session.Component` stores both the `Handle[Sessions]` and the loaded
  `Sessions` collection.

`SimpleNamespace` is untyped, so these are the remaining `Any` values on an
otherwise typed path.

## Handles become recoverable

`Context.own` exists only because a handle opened in `provide` cannot be found
again in `finish`. Make it findable and both users disappear.

`Scope.open` becomes idempotent, keyed by the `JSONFile` declaration rather than
appending to a list, and `Handle.load` caches:

```python
class Scope:
	def __init__(self, files: Files):
		self.files = files
		self.lock: TextIO | None = None
		self.handles: dict[JSONFile[Any], FileHandle[Any]] = {}

	def open[T](self, file: JSONFile[T]) -> Handle[T]:
		if self.lock is None:
			raise RuntimeError("persistence scope is not active")
		if self.files is not file.files:
			raise RuntimeError("persistence file belongs to different files")

		handle = self.handles.get(file)
		if handle is None:
			handle = FileHandle(file)
			self.handles[file] = handle
		return cast(Handle[T], handle)
```

Both properties are correct on their own terms rather than conveniences. The
scope holds an exclusive lock for the request, so the file cannot change
underneath it and a cached load is the accurate reading, not a stale one.
Idempotent `open` also means two components sharing a file share one handle
instead of silently holding two divergent views of it, which today would lose
writes.

`FileHandle` gains a cache, and `save` replaces it so a later `load` sees what
was written:

```python
class FileHandle[T]:
	def __init__(self, file: JSONFile[T]):
		self.file = file
		self.active = True
		self.loaded = False
		self.value: T | None = None
```

`Scope.__exit__` iterates `self.handles.values()` to close them.

`data.Component` and `session.Component` then reopen instead of remembering:

```python
def provide(self, req: Request, ctx: Context) -> Store:
	return ctx.get(Persistence).open(self.file).load()


def finish(self, res: Response, ctx: Context):
	store = ctx.get(Store)
	if store.pending:
		ctx.get(Persistence).open(self.file).save(store)
		store.pending.clear()
```

`Context.own` and `_owned` are deleted, along with the `SimpleNamespace` import.
If per-request component state is ever genuinely needed again, add it as a value
threaded through the `__call__` frame — `provide` returning `tuple[T, S]` and
`finish` receiving both — rather than as a dictionary on the context. That form
is fully typed, needs no hashable owner, and is per-request by construction.

## Persistence becomes a protocol

Declare the two shapes `data` and `session` actually consume, in
`helios.persist`, above `Scope`:

```python
class Handle[T](Protocol):
	def load(self) -> T: ...
	def save(self, value: T): ...


class Persistence(Protocol):
	def open[T](self, file: JSONFile[T]) -> Handle[T]: ...
```

`Handle` is the name the protocol wants, so the existing concrete class is
renamed `FileHandle`, matching `Scope` implementing `Persistence`. `Scope.open`
returns `Handle[T]` and constructs a `FileHandle`; `data` and `session` only
ever see the protocol.

`persist.Component` declares `provides = Persistence` while returning a concrete
`Scope`. This is the case type keys support and strings could not: the key is
the declared interface, not whatever class happened to be constructed.

Be accurate about what this buys. `JSONFile` stays shared vocabulary, so
`data` and `session` still import from `helios.persist`; the gain is
substitutability — an in-memory `Persistence` can be registered under the same
key for tests, and the components hold no reference to `Scope` or to locking.
If import separation is later wanted for its own sake, split `helios.persist`
into a package with the protocols and `JSONFile` in one module and the locking
implementation in another. That is not required here.

## Type keys on Context

```python
class Context:
	def __init__(self):
		self._provided: dict[type, Any] = {}
		self._resources = ExitStack()

	def get[T](self, key: type[T]) -> T:
		if key not in self._provided:
			raise ComponentError(f"nothing provides {key.__qualname__}")
		return self._provided[key]

	def put[T](self, key: type[T], val: T):
		self._provided[key] = val

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self._resources.enter_context(resource)
```

`__getattr__` and `__setattr__` are removed, which also removes the reason for
the `__dict__` assignments in `__init__` — ordinary attributes are fine once the
class no longer intercepts them.

## Type keys on Component

```python
class Component[T]:
	provides: type[T] | None
	requires: tuple[type, ...] = ()

	def boot(self):
		pass

	def provide(self, req: Request, ctx: Context) -> T | None:
		return None

	def finish(self, res: Response, ctx: Context):
		pass

	def __call__(self, req: Request, ctx: Context, next: Next) -> Response:
		provided = self.provide(req, ctx)
		if self.provides is not None:
			ctx.put(self.provides, cast(T, provided))
		res = next(req, ctx)
		self.finish(res, ctx)
		return res
```

`provides = None` admits a component that only wraps the pipeline. `Component`
already does response-path work through `finish` on every component, so a
provider-less one is consistent rather than a new concept, and it is the only
place application-level middleware can live now that `middleware=` has been
removed from `Application.__init__`. The declaration stays mandatory — a
middleware-only component writes `provides = None` explicitly, and `verify`
still rejects a component that declares nothing.

`provide` no longer raises `NotImplementedError`, since a `provides = None`
component need not define it.

`verify` keeps its shape; only the key type and the messages change:

```python
def verify(components: list[Component[Any]]):
	provided: set[type] = set()
	for component in components:
		if not hasattr(component, "provides"):
			raise ComponentError(
				f"{type(component).__qualname__} does not declare what it provides"
			)

		for requirement in component.requires:
			if requirement not in provided:
				raise ComponentError(
					f"{type(component).__qualname__} requires "
					f"{requirement.__qualname__}, which no earlier component provides"
				)

		if component.provides is None:
			continue
		if component.provides in provided:
			raise ComponentError(
				f"more than one component provides {component.provides.__qualname__}"
			)
		provided.add(component.provides)
```

`requires` remains a declaration checked at boot, not an enforcement mechanism.
Nothing prevents a handler or guard from calling `ctx.get(Store)` without any
component declaring it; that still fails per-request, as it does today.

## Module ordering

`provides = Store` is a runtime assignment in the class body, so the provided
class must already exist. It does not in four modules, all of which define
`Component` above the type it provides:

| Module | Provides | Currently defined at |
| --- | --- | --- |
| `helios/data/store.py` | `Store` | below `Component` |
| `helios/session.py` | `Session` | below `Component` |
| `helios/flash.py` | `Flashes` | below `Component` |
| `helios/views/__init__.py` | `Views` | below `Component` |

`from __future__ import annotations` does not help here — it defers annotations,
not assignments. Move `Component` to the bottom of each module. This is the
one mechanical change the string keys were hiding.

`helios/persist.py` needs the `Persistence` protocol declared above its
`Component`, which the section above already places at the top of the module.

## Views engine typing

`views.Component` sets `self.engine = None` in `__init__` and builds it in
`boot`, and `provide` currently has no return annotation. Under
`Component[Views]` the checker will reject returning `Views | None`. Type the
attribute as `Views | None` and fail explicitly in `provide` when the component
was never booted, rather than widening the provided type.

## Session dirty check

`session.Component.finish` saves unconditionally, so every request rewrites the
sessions file including requests that never touched a session. `data.Component`
already guards on `ctx.store.pending`; give sessions the equivalent.

Track the flag on mutation — `Session.__setitem__`, `__delitem__` and `clear`,
and `Sessions.put` — so that a newly created session is dirty by construction.
Component nesting already orders this correctly: `flash.Component` sits inside
`session.Component`, so its `finish` writes `_flash` into the session before the
session's own `finish` runs and observes the flag.

## Call site migration

Within Helios:

- `data/store.py`: `ctx.persistence` and `ctx.store`;
- `session.py`: `ctx.persistence` and `ctx.session`;
- `flash.py`: `ctx.session` and `ctx.flash`;
- `auth.py`: `ctx.session` and `ctx.store`.

`finish` does not receive the value it provided, so it reads it back with
`ctx.get`. Threading the provided value into `finish` is a reasonable follow-up
but is deliberately out of scope here.

## Cork migration

This is the ergonomic cost of the change and it lands entirely in Cork's
handlers, which read `ctx.store`, `ctx.session`, `ctx.views`, `ctx.flash` and
`ctx.auth` throughout. Every one becomes `ctx.get(Store)` and so on, with the
imports that implies.

Handlers that use a capability more than once should bind it once at the top
rather than repeating the call:

```python
def show(req, ctx):
	store = ctx.get(Store)
	board = store.find_one(Board, UUID(req.params["id"]))
	pins = store.find_by(Pin, board_id=board.id)
	return Response.html(ctx.get(Views).render("boards.show", {...}))
```

The component list itself changes only in that `requires` and `provides` now
name classes. Its order does not change, which is the point of verifying the
written order rather than deriving one.

## Suggested implementation stages

Each stage should leave the suite green.

### Stage 1: Recoverable handles

Make `Scope.open` idempotent and `Handle.load` cache. Move `data` and `session`
off `ctx.own`. Delete `Context.own` and `_owned`.

### Stage 2: Persistence protocol

Add the `Persistence` and `Handle` protocols and rename the concrete handle
to `FileHandle`. Point `persist.Component` at the
protocol and move `data` and `session` onto it.

### Stage 3: Type keys

Add `Context.get` and `put` and remove the attribute sugar. Make `Component`
generic, switch `provides` and `requires` to types, update `verify`, reorder the
four modules, and fix the views engine typing.

### Stage 4: Provider-less components

Allow `provides = None` and confirm `verify` still rejects an undeclared
component.

### Stage 5: Session dirty check

Add mutation tracking to `Session` and `Sessions` and guard the save.

### Stage 6: Cork

Migrate handlers and the component list; confirm the app boots and behaves.

## Tests

- `test/app_test.py`: `verify` rejects an undeclared component, a duplicate
  provider, and a requirement no earlier component provides — all with types,
  and asserting the class name appears in the message. A `provides = None`
  component runs its `finish` and puts nothing. `ctx.get` raises for an
  unprovided key.
- `test/persist_test.py`: `Scope.open` returns the same handle for the same
  file and a distinct one per file; `Handle.load` returns the same object
  across calls; `save` is visible to a later `load`; handles close at scope
  exit. Keep the existing lock-serialization coverage unchanged.
- `test/data/component_test.py` and the session component coverage: exercise
  the components against an in-memory `Persistence` rather than a temporary
  directory, now that they depend only on the protocol.
- Session: a request that never touches the session does not rewrite the file;
  a flash written during the request does.
- `test/auth_test.py`: update the seven context reads across the suite.

## Non-goals

Do not include:

- lazy or demand-driven resolution of components;
- reflection-based autowiring of constructor dependencies;
- qualifier keys for two instances of one provided type;
- splitting `Component` into separate provider and middleware concepts;
- reopening `middleware=` on `Application`;
- flushing staged writes at scope exit, or multi-file atomic commit;
- upgrading the shared lock to exclusive on first write;
- passing the provided value into `finish`.

## Final verification

1. Run the complete Helios test suite.
2. Run Ruff formatting and lint checks.
3. Confirm a mis-ordered component list fails at `Application.__init__` rather
   than on the first request.
4. Confirm no `Any` remains on the path from `provides` through `provide` to
   `ctx.get`.
5. Confirm read-only Cork requests rewrite neither the store nor the sessions
   file.
6. Confirm `.agents/notes/component-dependencies.md` is rewritten or removed,
   since its change three describes the string design this plan replaces.
