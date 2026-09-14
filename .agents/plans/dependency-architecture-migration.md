# Dependency architecture migration

## Goal

Replace the current `Component`/`Lifetime` architecture with the four-object
architecture in `.agents/notes/dependency-architecture-design.md`:

- `Application` owns construction, lifecycle, and the HTTP pipeline.
- `Provider` installs a feature's bindings and middleware.
- `Container` owns application bindings, singleton instances, and
  application-lifetime resources.
- `Context` owns one request's scoped instances, outcome, and resources.

This is a hard cutover. Delete the old `Component`, `Lifetime`, `verify`, public
`Thread`, mutable `Context.put()`, parent-context behavior, optional
`Application.boot()`. Do not add adapters, deprecation aliases, or dual
component/provider paths.

Preserve the useful existing behavior:

- services are keyed by Python types;
- factories are explicit and do not inspect constructors;
- file persistence is acquired lazily and shared by data and sessions in one
  request;
- handled `HTTPError`s run response-side persistence;
- unexpected exceptions skip response-side persistence but still release
  request resources;
- returned responses, including explicitly returned 500 responses, are not
  treated as errors.

## Public API after the cutover

Expose the dependency API from `helios.app`. Keep application, container,
context, and kernel implementations in focused modules within that package:

```python
type Next = Callable[[Request, Context], Response]
type Middleware = Callable[[Request, Context, Next], Response]


class Provider:
	def register(self, container: Container): ...
	def boot(self, application: Application): ...


class Container:
	def instance[T](self, key: type[T], value: T): ...
	def singleton[T](self, key: type[T], factory: Callable[[Container], T]): ...
	def scoped[T](self, key: type[T], factory: Callable[[Context], T]): ...
	def get[T](self, key: type[T]) -> T: ...
	def enter[T](self, resource: AbstractContextManager[T]) -> T: ...
	def close(self): ...


class Context:
	error: Exception | None

	def get[T](self, key: type[T]) -> T: ...
	def resolved[T](self, key: type[T]) -> T | None: ...
	def enter[T](self, resource: AbstractContextManager[T]) -> T: ...
	def close(self): ...


class Application:
	container: Container

	def __init__(
		self,
		config: Config,
		router: Router,
		providers: list[Provider],
		middlewares: list[Middleware] | None = None,
	): ...
	def use(self, middleware: Middleware): ...
	def handle(self, request: Request) -> Response: ...
	def close(self): ...
```

Retain `helios.app.Config` and its optional `base_url`; it is the application
configuration named by the design. It is separate from the environment reader
in `helios.config` and from each feature's typed configuration.

Replace `ComponentError` with `DependencyError` for missing bindings, invalid
scope resolution, and factories or instances producing `None`. Messages for
resolution failures must name the requested type. Resource entry/exit
exceptions remain their original exceptions. Dependency graphs are expected to
be acyclic; cycles are unsupported and recurse until Python reports them.

Do not track or validate application lifecycle phases. Providers and hosts are
expected to follow the documented construction, request, and shutdown sequence.
Mutation after registration, resolution during registration, calls to
`Application.use()` outside provider boot, handling after shutdown, and use of
closed contexts or containers are unsupported rather than detected errors.

## Container internals and contracts

Represent each binding as exactly one of instance, singleton, or scoped. A
single binding dictionary is preferable to parallel dictionaries because
replacement must also replace the lifetime. Registration under an existing key
silently replaces the old definition.

The application seeds ordinary instance bindings for:

- `Application` with the application under construction;
- `Container` with the container itself;
- `Config` with the supplied `helios.app.Config`;
- `Router` with the supplied router;
- `URLs` when `config.base_url` is configured.

`Request` is seeded directly into each request context rather than resolved by
`Container.get()`. Providers are expected to register only their feature-owned
bindings during `register()` and to defer resolution until `boot()` or request
handling. The container does not freeze definitions or reserve framework keys.
`get` resolves instances and singletons only; a scoped key reports that a
request context is required. `enter` is used by boot logic and singleton
factories. `close` idempotently closes the application `ExitStack`.

Reject `None` both when registering an instance and after invoking a factory.
Do not cache a failed or `None` singleton result.

Use lazy singleton construction. Protect singleton cache inspection and factory
publication with a reentrant lock so concurrent request threads cannot publish
multiple instances and same-thread nested singleton resolution remains
possible.

`Container.enter()` owns only resources explicitly entered through it. Do not
infer cleanup from a singleton's `close`, `__exit__`, or other methods.
Application resources close in reverse acquisition order.

## Request context

Construct one `Context` in `Kernel.handle()` and seed its exact `Request`
instance internally. A context contains:

- its application container;
- a scoped-instance cache;
- the request binding;
- a request `ExitStack`;
- the first/current error from which the active response was rendered.

`Context.get()` returns the request, a cached or newly created scoped value, or
delegates application-lifetime resolution to the container. Scoped factories
receive this same context, so nested scoped dependencies share its cache.

`Context.resolved()` must not invoke a factory. It returns:

- the request binding;
- a cached scoped service;
- a container instance;
- an already-initialized singleton;
- `None` for an uninitialized singleton, unresolved scoped binding, or missing
  binding.

Because `None` is not a valid service value, this result is unambiguous. Access
to initialized singleton state must use the same synchronization as singleton
resolution.

`Context.enter()` enters a request resource immediately. `close()` is
idempotent and unwinds request resources in reverse order. Context closure
belongs exclusively to `Application`; remove public mutation and parent-scope
construction. Use after closure is unsupported and is not explicitly detected.

## Application construction and lifecycle

Construction performs the complete build synchronously:

1. Create the container and install framework-owned bindings.
2. Call every `Provider.register(container)` in provider-list order.
3. Call every `Provider.boot(application)` in the same order.
4. Build the provider pipeline.

Keep the provider list on the application so provider objects remain alive even
when a provider happens not to contribute a retained bound method. Providers
call `use()` during boot. All registrations are visible by then, so boot-time
singleton resolution is independent of provider order.

If any registration or boot step fails, close the container before propagating
the failure. Do not return a partially built application. `close()` closes the
container and is idempotent. The host is responsible for handling requests only
after construction and stopping dispatch before shutdown; misuse is not
explicitly detected. The application is not a context manager and does not
manage or drain its WSGI host.

## HTTP pipeline and outcomes

Remove the public `Thread` abstraction. Introduce an internal `Kernel` that
builds an immutable callable chain when application construction completes and
executes each request through it. The effective order is:

```text
request Context lifetime
└─ content-length normalization
   └─ unexpected-error rendering
      └─ artificial-method adaptation
         └─ provider middleware in provider-list order
            └─ standalone middleware in constructor order
               └─ router dispatch
```

Provider middleware precedes standalone constructor middleware. Request-side
work runs in installation order and response-side work in reverse order.

Wrap every middleware link and the terminal router link with the same
`HTTPError` boundary. If a link raises `HTTPError`, that link records the error
on the context and renders the plain-text error response. This placement is
important: an error from a middleware's request side becomes a response for
outer middleware, while an error from the router becomes a response for every
provider middleware.

Do not catch unexpected exceptions at individual middleware links. Let them
unwind middleware, then have the application's outer unexpected-error
handler:

1. record the exception on the context;
2. print it to stderr as today;
3. render the existing plain-text 500 response.

Content-length normalization surrounds that handler, so ordinary, handled HTTP,
and rendered 500 responses are normalized identically. A directly returned
response never sets `Context.error`, regardless of status.

Have `Kernel.handle()` close the context in a `finally` outside the complete
response pipeline. A
request-resource cleanup failure therefore propagates to the host and is not
converted into another HTTP response. This also guarantees cleanup for normal
responses, handled HTTP errors, and unexpected exceptions.

Keep the current artificial method behavior and its position before provider
middleware. Do not move WSGI concerns into the application.

## Built-in feature migration

Rename each feature installation class from `Component` to `Provider`, rename
`component.py` modules to `provider.py`, and update package exports. Remove the
old modules rather than leaving import shims.

### Persistence

`helios.persist.Provider` retains `Files` and registers:

```python
container.scoped(Persistence, self.persistence)
```

Its `persistence(context)` factory enters `self.files.lock()` through
`context.enter()` and returns the active `FilePersistence`. It installs no
middleware. This preserves one lazily acquired lock per request, shared by all
persistence consumers, and avoids locking requests that never resolve
`Persistence`.

### Data

`helios.data.Provider` retains data config, `Files`, and `Schema`. During
registration it creates the `JSONFile[Store]` declaration and registers `Store`
as scoped. Its `store(context)` factory resolves `Persistence`, opens the file,
and loads the store.

During boot it installs one response-side middleware. The middleware calls the
next link first, then uses `context.resolved(Store)`. If no store was used, it
does nothing. If the resolved store has pending changes, it reuses the request's
persistence handle, saves, and clears pending changes.

This intentionally keeps current outcome policy: redirects, handled HTTP errors,
and directly returned error responses save; unexpected exceptions skip the
response side and do not save.

### Sessions

`helios.session.Provider` retains session config and its sessions file and
registers `Session` as scoped. The `session(context)` factory resolves `Request`
and `Persistence`, loads/purges `Sessions`, and returns the existing valid
session or a new detached session using the current rules.

Install response middleware during boot. After the inner response returns, use
`context.resolved(Session)` and do nothing if sessions were never requested. If
a session exists, preserve the current attach/remove/invalidate, cookie, expiry,
rotation, dirty-check, and save behavior. Reopening the same persistence file
returns its request-cached handle and `Sessions` value, so no second request
state binding is required.

### Flash

`helios.flash.Provider` registers scoped `Flashes`. Its factory lazily consumes
and removes `_flash` from `Session`. Its response middleware uses
`context.resolved(Flashes)` and, only when resolved and dirty, writes the next
flash payload to the already-resolved session.

The flash provider must appear after the session provider so flash response work
runs before session persistence.

### Authentication

`helios.auth.Provider` retains the configured user model type and registers a
scoped `Authenticator`. Move the existing session-user lookup and stale-ID
cleanup unchanged into its `authenticator(context)` factory. It installs no
middleware.

### Views

`helios.views.Provider` registers `Views` as a singleton whose factory calls
`load(config.dir)`. During boot it resolves `Views` eagerly. This retains startup
validation/loading while expressing the value as an ordinary singleton. It
installs no middleware.

### Rate limiting

Expose `helios.limit.Middleware` for direct installation through the application
constructor. The middleware retains its configuration and constructs one
`RateLimiter`, so its mutable limiter is shared across requests without an
otherwise-unused container binding or provider. Remove its declarative
`requires` attribute; its dependency is the runtime
`context.get(Authenticator)` call.

Thread-safety of `RateLimiter.entries` is a separate behavioral concern, not
part of this architecture cutover.

## Composition and ordering

A complete application composition becomes:

```python
Application(
	config,
	router,
	[
		persist.Provider(files),
		data.Provider(data_config, files, schema),
		views.Provider(views_config),
		session.Provider(session_config, files),
		flash.Provider(),
		auth.Provider(User),
	],
	[limit.Middleware(limit_config)],
)
```

Data, session, and flash install provider middleware. The configured rate-limit
middleware follows them, producing:

```text
data save boundary
└─ session save boundary
   └─ flash transfer boundary
      └─ rate limit
         └─ router
```

On the response path flash updates the session before session persistence, and
session persistence completes before data persistence. Service construction is
lazy and does not depend on this order; only middleware semantics do.

Update any downstream application (notably Cork) in the same cutover:

- instantiate `Provider` classes instead of `Component` classes;
- pass providers as the third `Application` argument;
- pass standalone middleware as the fourth `Application` argument;
- delete all `app.boot()` calls;
- call `app.close()` from host shutdown and test fixture teardown.

## Routing and WSGI typing

Replace `Any` in `Next`, `Middleware`, route `Handler`, route `Guard`, and
`Router.__call__` context positions with `Context`. Use typing-only imports in
`helios.routing` to avoid a runtime cycle with `helios.app`, which imports
`Router`.

Keep `helios.wsgi.Application` as the WSGI subclass of the core application.
Its constructor now fully boots. Remove `boot()` from WSGI tests and helpers.
Do not make the WSGI adapter close the application automatically; server/host
shutdown owns that call.

Update the README's architecture description and examples from components to
providers and container/context scopes.

## Implementation stages

Each stage should keep focused tests passing, but compatibility with the old
public API is not required between stages.

### Stage 1: Container and context

1. Add binding records, lazy singleton resolution, scoped resolution,
   synchronization, `resolved()`, and both resource stacks in
   `src/helios/app/`.
2. Add direct container/context tests before integrating the application.
3. Exercise resource order, idempotent close, failed factories, `None`, binding
   replacement, scope errors, and concurrent singleton resolution.

### Stage 2: Application lifecycle and pipeline

1. Replace component verification/boot with provider registration and boot.
2. Make construction finish provider registration and booting, then create the
   kernel to assemble the pipeline.
3. Build kernel request handling with per-link HTTP errors, outer
   unexpected-error rendering, outcome recording, and unconditional context
   close.
4. Add close and partial-construction cleanup behavior.
5. Remove `Component`, `Lifetime`, `Thread`, and old verification functions and
   rewrite `test/app_test.py` around public behavior.

### Stage 3: Stateless service providers

Migrate views and authentication first. They exercise eager singleton boot and
scoped dependency graphs without response persistence. Rename files, classes,
exports, and tests in the same change.

### Stage 4: Persistence and response providers

Migrate persistence, data, sessions, and flash together so request locking and
response order never pass through a half-component/half-provider state. Keep the
existing file and domain objects unchanged. Rewrite component tests as provider
integration tests through `Application` and observable persistence/cookie
behavior rather than invoking factory or finalizer methods directly.

### Stage 5: Rate limiting, typing, and consumers

1. Pass rate-limit middleware directly to the application.
2. Type routing and middleware context boundaries.
3. Update all Helios and downstream application construction call sites.
4. Remove obsolete component modules/imports and update README and stale design
   notes.

## Tests

### Container and context contract

Add coverage that:

- instance, singleton, and scoped bindings resolve by type;
- later registration replaces earlier registration across lifetime kinds;
- missing bindings and cross-scope resolution fail with useful errors;
- singleton factories run once under concurrent resolution;
- a failed singleton factory is retried and never cached;
- `None` is rejected for every binding kind;
- scoped factories run once per context and independently across contexts;
- `resolved()` never triggers a factory;
- request and application resources close in reverse order and at only their
  owning lifetime;
- context, container, and application close operations are idempotent.

### Application lifecycle and pipeline

Add coverage that:

- all providers register before any provider boots and both phases preserve
  list order;
- boot can resolve a service registered by a later provider;
- middleware installed during boot executes in provider order;
- construction failures close already-entered application resources;
- `handle()` works immediately after construction;
- each request receives its exact `Request` and independent scoped services;
- normal, handled HTTP-error, and unexpected-error responses receive content
  length;
- HTTP errors raised by routing or middleware become responses for outer
  response middleware and set `Context.error`;
- directly returned responses leave `Context.error` unset;
- unexpected exceptions set `Context.error`, skip provider response-side work,
  and render 500;
- request resources always close, while cleanup failures escape to the host.

### Built-in providers

Preserve existing domain behavior and specifically assert:

- persistence is not locked on a request that resolves no persistence-backed
  service;
- data and sessions share one active `Persistence` and lock in a request;
- data/session/flash scoped services are lazy and constructed at most once;
- read-only or unused stores are not rewritten;
- data saves after normal responses, redirects, handled HTTP errors, and
  directly returned 500 responses, but not unexpected exceptions;
- unused sessions do not load or save, while used sessions preserve all current
  cookie and mutation semantics;
- flash response changes are present when session middleware saves;
- views load during application construction and are shared across requests;
- authenticators are request scoped;
- rate limiting uses one application limiter and remains middleware.

Use application requests for provider integration tests. Mock only external
boundaries such as in-memory persistence or filesystem/process coordination;
do not test private binding records, cache fields, or pipeline helper call
order.

## Non-goals

Do not add:

- compatibility adapters for `Component`, `Lifetime`, `boot()`, `Context.put()`,
  or `Thread`;
- reflection-based constructor injection;
- transient bindings, string keys, qualifiers, aliases, decorators, tagged
  collections, or global container access;
- provider shutdown hooks or automatic singleton cleanup;
- route registration APIs on providers;
- named middleware stages or priority sorting;
- application server draining;
- changes to persistence formats, durability, session policy, or data commit
  policy;
- transaction abstractions beyond the context/resource ownership needed for
  future transactions.

## Documentation cleanup and final verification

1. Update `README.md` to name providers rather than components.
2. Remove or rewrite `.agents/notes/dependency-architecture.md` and
   `.agents/notes/request-scoped-resources.md` once the implementation makes
   their current-state descriptions obsolete. Keep
   `.agents/notes/dependency-architecture-design.md` as the architecture source
   of truth.
3. Mark the component-specific portions of older plans as superseded; do not
   silently leave examples presenting `Component` as current API.
4. Run `mise run test`.
5. Run `mise run lint`.
6. Run `uv run ty check` and confirm no `Any` remains on the middleware/router
   context boundary.
7. Search `src`, tests, README, and downstream consumers for `Component`,
   `Lifetime`, `.boot()`, `Context.put`, and `Thread`.
8. Exercise downstream application startup, one persistence-free request, one
   data/session request, a handled 404, an unexpected exception, and explicit
   shutdown.
