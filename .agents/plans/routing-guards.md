# Helios router ownership, guards, and groups

## Goal

Make the router an explicitly configured terminal dispatcher, represent
route-specific authorization natively, and add declarative route grouping for
shared guards and URL prefixes.

The intended Cork configuration is:

```python
router = Router(routes)
app = Application(router, components)
```

with public routes outside an authenticated group and protected routes inside
it:

```python
routes = [
	Route(Method.GET, Pattern("/sign-in"), auths.new),
	Route(Method.POST, Pattern("/sign-in"), auths.create),
	Group(
		guards=[ensure_signed_in],
		routes=[
			Route(Method.POST, Pattern("/sign-out"), auths.delete),
			Route(Method.GET, Pattern("/"), home.show),
			Group(prefix="/boards", routes=[...]),
			Group(prefix="/pins", routes=[...]),
		],
	),
]
```

Implement this in independently reviewable stages. Every stage should leave
Helios and Cork operational.

## Architectural boundary

`helios.app.Application` owns the request pipeline and component lifecycle. It
accepts a terminal dispatcher with the callable shape `(req, ctx) -> Response`
but does not construct or otherwise understand a router.

`helios.routing.Router` owns route configuration and dispatch. It matches a
route, converts its parameters, runs that route's effective guards, and invokes
the handler. It is a terminal dispatcher, not middleware, and therefore does
not accept an unused `next` argument.

`Route` owns its handler and effective route metadata, including guards.
`Group` is only a declarative configuration facility. Groups do not participate
in the runtime middleware chain or perform dispatch themselves.

The request pipeline remains:

```text
ensure content length
capture unexpected errors
adapt artificial method
components, in configured order
handle HTTP errors
terminal dispatcher (normally Router)
```

This ordering ensures authentication components populate `ctx` before route
guards run. Responses returned by guards, and HTTP errors raised by guards,
also unwind through component `after` hooks normally.

## Stage 1: Explicit terminal router

1. Change `Router.__call__` from middleware shape `(req, ctx, next)` to terminal
   dispatcher shape `(req, ctx)`.
2. Change `Application` to accept a terminal dispatcher instead of a list of
   routes.
3. Keep the terminal type generic so `helios.app` does not need to import
   `Route` or `Router`. A callable type alias or protocol is sufficient.
4. Compose the built-in middleware and components around the supplied
   dispatcher inside `helios.app`.
5. Remove `Kernel` and `Thread` from `helios.routing`. They currently combine
   generic middleware composition with router construction even though that is
   application pipeline behavior. Use a small private composition facility in
   `helios.app`; do not introduce a new public abstraction unless the
   implementation demonstrates a need for one.
6. Preserve the exact current middleware ordering and HTTP error behavior.
7. Update Helios callers and tests to construct `Router` explicitly.
8. Update Cork to pass `Router(routes)` to `Application`, while temporarily
   retaining Cork's existing global `Guards` component. This stage must not
   change which Cork requests require authentication.

### Stage 1 tests

1. Preserve all existing application, routing, and WSGI behavior.
2. Test direct terminal dispatch through `Router(req, ctx)`.
3. Test that `Application` can operate with a non-router terminal callable,
   proving the boundary is generic.
4. Preserve the HTTP-error regression tests showing component `after` hooks run
   for routing and store not-found responses.
5. Confirm `helios.app` no longer imports anything from `helios.routing`.

## Stage 2: Route-specific guards

1. Add an optional ordered guard collection to `Route`. Routes without guards
   retain their current behavior.
2. Define a guard as a callable receiving `req`, `ctx`, and the same converted
   route parameters available to the handler. It returns either a `Response` to
   stop dispatch or `None` to continue.
3. Change routing matches to retain the matched `Route`, rather than reducing a
   match immediately to `(handler, params)`. `Router.match` may return
   `(route, params)`; avoid adding a separate match abstraction unless it
   provides concrete value.
4. Dispatch in this order:

   ```text
   match route
   convert parameters
   run guards in declaration order
   invoke handler
   ```

5. Pass converted parameters by name to guards, as is already done for
   handlers.
6. Stop at the first guard result that is not `None` and return that response.
   Do not use general truthiness as the control condition.
7. Let exceptions from guards propagate normally. `HTTPError` instances will be
   rendered by the existing application middleware and unexpected exceptions
   will retain the existing 500 behavior.
8. Keep guards independent of `helios.auth`; the router knows only their
   callable contract.
9. Do not migrate Cork away from its global guard component in this stage.

### Stage 2 tests

1. A route without guards invokes its handler unchanged.
2. Guards run in declaration order.
3. A guard returning `None` allows dispatch to continue.
4. A guard returning a response prevents later guards and the handler from
   running.
5. Guards receive converted parameters, including UUID values.
6. A normal guard response passes through component `after` hooks.
7. An `HTTPError` raised by a guard is handled inside the component chain.
8. An unexpected guard exception retains the existing 500 behavior.
9. An unmatched request runs no route guards.

## Stage 3: Declarative `Group`

1. Add `Group` to `helios.routing` with:
   - an ordered list of `Route | Group` children;
   - an optional URL prefix, defaulting to no prefix;
   - an optional ordered guard collection, defaulting to no guards.
2. Allow `Router` to accept an ordered list containing both routes and groups.
3. Recursively flatten groups when constructing the router. Runtime dispatch
   should operate over ordinary effective routes and should not recursively
   inspect groups for every request.
4. Build new effective route configuration while flattening. Do not mutate the
   source `Route`, `Pattern`, guard lists, or `Group` objects supplied by the
   application.
5. Join nested prefixes with exactly one path separator at each boundary while
   preserving meaningful root and trailing-slash patterns. Construct the final
   `Pattern` from the joined raw pattern so parameter conversion continues to
   work normally.
6. Inherit guards in this order:

   ```text
   outer group guards
   inner group guards
   route guards
   handler
   ```

7. Preserve declaration order exactly when flattening so existing first-match
   routing semantics do not change.
8. Keep `Group` declarative. It must not become middleware, a nested router, or
   an authentication-specific facility.
9. Export it as `Group`, not `RouteGroup`.

The conceptual API is:

```python
Group(
	routes: list[Route | Group],
	prefix: str = "",
	guards: list[Guard] | None = None,
)
```

The precise constructor argument order may follow the project's existing style,
but keyword use for `prefix`, `guards`, and `routes` should remain clear.

### Stage 3 tests

1. A group with neither prefix nor guards preserves its routes unchanged.
2. A prefix is applied to every direct child route.
3. Nested prefixes compose correctly.
4. Root child patterns compose correctly with a prefix.
5. Route parameters in grouped patterns are still converted.
6. Group guards are inherited by every descendant route.
7. Nested and route-specific guards run outermost-first.
8. A response from an inherited guard short-circuits remaining guards and the
   handler.
9. Flattening preserves route declaration and matching order.
10. Reusing a route or group in configuration does not mutate its original
    pattern or guards.

## Stage 4: Migrate Cork

1. Remove Cork's application-level `Guards` component.
2. Keep the sign-in GET and POST routes public at the top level.
3. Put all routes requiring authentication, including sign-out, inside a
   `Group(guards=[ensure_signed_in], ...)`.
4. Simplify `ensure_signed_in` so it only checks authentication state. Remove
   its inspection of `req.url.path` and its knowledge of `/sign-in`.
5. Use nested `/boards` and `/pins` prefix groups to remove repeated path
   prefixes while preserving all existing route patterns and route order.
6. Keep `helios.auth.Component` before dispatch in the component list so
   `ctx.auth` exists when the group guard runs.
7. Remove the exported global `guards` list if it is no longer useful.
8. Preserve redirects and all current signed-in/signed-out behavior.
9. Record any newly encountered framework friction in Cork's
   `.agents/notes/dogfooding.md`; do not add a historical note merely to record
   that this migration occurred.

### Stage 4 verification

Cork currently has no test harness, so verify the migration against the already
running development server without starting another server:

1. A signed-out request to `/sign-in` reaches the sign-in page.
2. A signed-out request to `/` redirects to `/sign-in`.
3. A signed-out request to a grouped board or pin route redirects to
   `/sign-in`.
4. A signed-in request reaches home, settings, board, and pin routes.
5. Signing out remains available while signed in and leaves protected routes
   inaccessible afterwards.
6. Grouped UUID routes still match and receive converted UUID parameters.

## Compatibility and non-goals

This is an intentional constructor-level API change for `Application` and a
call-shape change for `Router`. Update Helios and Cork together rather than
maintaining compatibility shims for the current small API.

Do not include the following in this work:

1. Decorator-based route registration or a routing builder DSL.
2. Authentication-specific guards in Helios.
3. Global router guards; a root `Group` provides the declarative equivalent.
4. Named routes or URL generation.
5. Dynamic route registration after router construction.
6. Changes to method-not-allowed behavior.
7. Changes to exception-based unmatched-route handling.
8. Changes to the HTTP error hierarchy or response rendering introduced by the
   preceding HTTP-error migration.

## Final verification

1. Run the complete Helios suite with `uv run test` from the Helios repository.
2. Run the configured lint or formatting checks.
3. Confirm Cork imports and starts with the new `Application(Router(...), ...)`
   construction.
4. Perform the Cork authentication smoke checks above against the existing
   development server.
5. Confirm there is no remaining Cork guard that infers route security from URL
   string inspection.
