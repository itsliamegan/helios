# Helios HTTP errors

## Goal

Move HTTP control errors into `helios.http`, let framework facilities raise
HTTP-specific errors without creating imports from `helios.app` to those
facilities, and preserve one centralized implementation of HTTP error
responses.

Limit the routing change to the source of its not-found base class so that route
guards, router ownership, `Kernel`, and route dispatch can still be redesigned
separately.

## Dependency direction

1. Define the HTTP error abstraction in `helios.http`, which already owns
   `Status`, `Request`, and `Response`.
2. Allow `helios.app`, `helios.routing`, and the Helios store integration to
   depend on `helios.http`.
3. Do not import `helios.store` from `helios.app`; the application catches the
   shared HTTP abstraction rather than concrete store errors.
4. Keep components implemented as middleware. This migration does not change
   `Context`, `Component`, `Thread`, `Kernel`, or the router API.

The resulting dependency path for not-found handling is:

```text
helios.app ───────→ helios.http
helios.store ─────→ helios.http
helios.routing ───→ helios.http
```

There is no path from `helios.app` back to `helios.store`, so this remains
acyclic.

## HTTP error hierarchy

1. Add `HTTPError` to `helios.http` with a `Status` carried by the error type or
   instance.
2. Add `NotFoundError` as the HTTP 404 specialization.
3. Keep response rendering out of the exception classes. They communicate HTTP
   control flow; one application middleware remains responsible for rendering
   them.
4. Preserve concrete exceptions such as `helios.store.NotFoundError` so callers
   can still catch the more specific error and inspect its model and ID.

## Store migration

1. Change `helios.store.NotFoundError` to inherit directly from
   `helios.http.NotFoundError` instead of the generic error module.
2. Preserve its existing constructor, message, `model_type`, and `id`.
3. Do not add an exception map or make individual handlers translate store
   errors.
4. Keep `Store.find_one` behavior otherwise unchanged.

This intentionally treats the bundled Helios store as a web-framework facility:
an uncaught missing model has HTTP 404 semantics. Code that wants different
behavior can still catch `helios.store.NotFoundError` before it reaches the
application boundary.

## Central HTTP error handling

1. Replace the application middleware's dependency on
   `helios.errors.NotFoundError` with the HTTP-owned abstraction.
2. Generalize `handle_not_found` to a single HTTP-error handler if useful for
   the implementation, but preserve the current plain-text 404 response and
   status.
3. Place HTTP-error handling inside the component middleware chain and directly
   outside the router. A handler error must become a response before control
   unwinds through component `after` hooks.
4. Keep the generic unexpected-error capture outside the components so failures
   not represented by `HTTPError` still become 500 responses.
5. Preserve content-length handling and artificial-method adaptation.

The effective request pipeline should be:

```text
ensure content length
capture unexpected errors
adapt artificial method
components, in configured order
handle HTTP errors
router
```

A missing model or route therefore becomes a 404 response first, after which
component `after` hooks run normally in reverse order.

## Routing migration boundary

1. Change `helios.routing` to import its not-found base directly from
   `helios.http` rather than `helios.errors`.
2. Preserve `helios.routing.NotFoundError` as its own concrete exception,
   subclassing `helios.http.NotFoundError`. Routing therefore continues to own
   the specific error raised when no route matches, while the application can
   catch it through the HTTP abstraction.
3. Delete `helios.errors` once its imports have been removed.
4. Make no other changes to `Route`, `Router`, `Thread`, `Kernel`, matching
   behavior, handler invocation, or routing tests except where a new integration
   assertion is strictly necessary.

This touches one routing import but does not redesign routing. The guard work can
therefore proceed afterwards against otherwise unchanged routing behavior.

## Tests

1. Add HTTP tests proving `NotFoundError` is an `HTTPError` with
   `Status.NOT_FOUND`.
2. Preserve the existing application tests for unmatched routes, missing
   models, and unexpected exceptions.
3. Add an application regression test with a component whose `after` hook
   records or modifies the response, then verify that the hook runs for:
   - an unmatched route;
   - an uncaught `helios.store.NotFoundError` raised by a handler.
4. Preserve store tests proving callers can catch `helios.store.NotFoundError`
   and inspect its details.
5. Run the complete Helios test suite from `../helios` with `uv run test`.
6. Confirm `helios.app` has no import of `helios.store`, no imports of
   `helios.errors` remain, and the obsolete module has been deleted.

## Deferred routing work

Handle the following in a separate plan after this migration:

1. Make `Router` an explicitly configured terminal dispatcher accepted by
   `Application`.
2. Decide whether generic middleware composition and `Kernel` remain in
   `helios.routing` or move to `helios.app`.
3. Add route-specific guards and pass converted route parameters to them.
4. Reconsider whether unmatched routes should remain exception-based as part of
   the broader dispatcher design; do not couple that decision to this migration.

Keeping these decisions out of this migration ensures the existing routing
behavior provides a stable baseline for the subsequent redesign.
