# Shared durable JSON persistence

## Goal

Introduce `helios.persist` as the shared JSON-file persistence foundation for
Helios data and sessions:

```python
persistence = persist.Files(lock_file)
store_file = persistence.json(store_path, data.Format(schema))
sessions_file = persistence.json(sessions_path, session.Format())
```

The application enters one persistence request scope around its complete
component thread. That scope holds one process-safe lock while the data and
session documents are loaded, used, and conditionally saved.

This plan owns filesystem durability and concurrency. It does not introduce
strict model or session document validation; that belongs to the subsequent
strict JSON formats plan.

## Prerequisites

The explicit model-level `Store.save(model)` API and its Cork migration are
already established. That work determines when the data document is dirty; this
plan determines how that requested state reaches disk safely.

Complete the remaining mechanical `helios.store` to `helios.data` namespace
migration first, while retaining `ctx.store` as the request API. Keep that rename
separate from persistence behavior changes, update both Helios and Cork imports,
and run both test suites before continuing.

## Current defects

This plan directly addresses the following entries in
`.agents/notes/persistence-defects.md`:

- encoding after truncating the live file;
- no coordination between worker processes;
- request state stored on shared `session.Component`;
- lock and cleanup behavior after exceptions.

The note records concrete production constraints: Cork runs two Gunicorn sync
workers, whole-document writes can discard another worker's committed changes,
and locking the replaceable JSON file itself is incorrect.

## Module boundary

Add `helios.persist` with the shared contracts and mechanics:

```python
# helios.persist

type JSONValue = (
	None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)


class Format[T](Protocol):
	def encode(self, value: T) -> JSONValue: ...
	def decode(self, value: JSONValue) -> T: ...


class Files: ...


class JSONFile[T]: ...
```

`persist` may also define focused errors for:

- opening, reading, writing, syncing, or replacing files;
- malformed JSON syntax;
- format encoding and decoding failures.

Keep those categories distinguishable. The path-rich strict format errors are
added by the later plan.

`helios.persist` must not import `helios.data` or `helios.session`.

## Formats during this refactor

Add concrete formats beside the domains they understand:

```python
# helios.data
data.Format(schema)

# helios.session
session.Format()
```

Initially move the existing logical `encode` and `decode` behavior behind these
objects without tightening all validation at once. Both formats continue to
use the current unversioned representations:

```text
data:     a top-level array of model record objects
sessions: a top-level object keyed by session UUID strings
```

The shared layer calls only the `persist.Format` protocol. Formats operate on
already-parsed JSON values and never open files or acquire locks.

## Coordinated file set

`persist.Files` represents the JSON documents sharing one request-level
consistency boundary. It owns:

- the stable lock-file path;
- creation of associated `JSONFile` objects;
- acquisition and release of a per-request persistence scope.

Prefer creating files through the coordinator:

```python
store_file = files.json(store_path, data.Format(schema))
sessions_file = files.json(sessions_path, session.Format())
```

rather than constructing unrelated lock-owning files. Store and session files
must not independently open the same lock path within one request.

A request scope should expose an explicit handle or token used by associated
files. `JSONFile.load` and `JSONFile.save` should fail clearly if invoked as a
request mutation outside the correct active scope. Provide a deliberate
read-only scope for audits and command-line validation.

Do not store active request handles, loaded documents, or mutable request state
on the shared `Files` or component instances. Pass the request scope through
`Context` or directly to file operations. If implementation bookkeeping is
needed, it must remain request-local and safe for concurrent threads as well as
processes.

## Application lifecycle

The persistence request scope is application infrastructure, not a `Component`.
A lock required for correctness must not depend on application authors placing
an optional component first.

Configure it directly on `helios.app.Application`:

```python
Application(
	router,
	components,
	persistence=files,
)
```

Install the persistence scope as application-owned infrastructure inside the
application's error-capture boundary and outside the complete component thread.
Conceptually, the middleware order is:

```text
ensure_content_length
capture_errors
application persistence scope
adapt_artificial_method
components
handle_http_errors
router
```

The persistence wrapper is configured by `Application`; it is not exposed as an
optional `Component`. This placement lets lock acquisition, component loading,
persistence teardown, and lock-release failures follow the application's normal
unexpected-error policy rather than escaping `Application.handle` accidentally.

The scope must wrap all component `before` hooks, the router and guards, all
component `after` hooks, and exceptional unwinding. It does not need to enclose
response decoration performed outside the component thread.

Applications without coordinated JSON documents may omit persistence. Data and
session components configured with coordinated `JSONFile` objects must fail
configuration or usage clearly if the matching application scope is absent.

## Locking

Use one stable lock file and an OS-level `flock` appropriate for Cork's
multi-process deployment.

The lock must:

1. be acquired before either JSON document is loaded;
2. remain held throughout handler and guard execution;
3. remain held while session teardown and staged data saves run;
4. be released only after all persistence teardown completes;
5. be released on normal responses and every exceptional path.

Never lock a data file that is replaced atomically; replacement changes its
inode and invalidates that coordination strategy. Never use only a
`threading.Lock`, because Gunicorn workers are separate processes.

One lock intentionally serializes Cork requests that use these JSON documents.
This is the consistency cost of a whole-document file store and is acceptable
for this stage. Cross-file atomic transactions are still not provided.

## Durable JSON writes

`JSONFile.save` must leave the current live document untouched until the entire
replacement is ready.

Required sequence:

1. call `Format.encode`;
2. serialize the complete JSON value into memory;
3. create a uniquely named temporary file in the destination directory;
4. write the complete serialized document;
5. flush and `fsync` the temporary file where supported;
6. close it;
7. use `os.replace` to atomically replace the destination;
8. sync the containing directory where supported;
9. remove any remaining temporary file on failure.

Catching for temporary-file cleanup must cover `BaseException`, including
interrupts. Preserve useful exception chaining and distinguish format,
serialization, and filesystem failures.

Writing in the same directory is mandatory because atomic replacement is only
guaranteed within one filesystem. Preserve the permission bits of an existing
destination on its replacement and test that behavior. A newly created
destination may retain the temporary file's secure mode; do not broaden its
permissions implicitly.

JSON parsing should reject malformed syntax cleanly. Keep runtime document-shape
policy in the concrete formats rather than `JSONFile`.

## Component integration

### Data

`data.Component.before` loads its request-local `Store` through the coordinated
`JSONFile` and places it on `ctx.store`.

`data.Component.after` writes only the committed projection produced by staged
`Store.save` calls and automatic staged deletions. Read-only and wholly unsaved
requests do not rewrite the data file.

The write occurs before the application leaves the persistence scope.

### Sessions

Move the loaded `Sessions` collection off `session.Component` and onto
`Context`. The component should save exactly the collection loaded for that
request.

Session teardown may retain its existing automatic-save behavior in this plan.
Its commit policy is separate from explicit model saves.

Component objects retain only immutable configuration such as their coordinated
file handles.

## Failure and commit behavior

Preserve the explicit Store policy established by the preceding plan:

- staged model saves and deletions write after any normally returned response;
- an exception escaping the inner component chain skips the data write;
- handled HTTP errors are responses and therefore permit staged writes.

The persistence scope always releases its lock, regardless of whether a
component load, handler, format encode, file write, or component teardown
raises.

A failed data or session write must preserve that document's previous valid
contents. A session write may complete before a later data write fails; atomic
cross-file commit is explicitly outside this work.

## Implementation sequence

Implement this work in reviewable stages. Run the relevant focused tests after
each stage rather than combining the whole migration into one patch.

1. **Mechanical namespace migration**
   - rename `helios.store` to `helios.data` without changing behavior;
   - update Helios and Cork imports while retaining `ctx.store`;
   - run both suites before adding persistence behavior.
2. **Shared persistence contracts and scopes**
   - add `JSONValue`, `Format`, focused persistence errors, `Files`, and
     `JSONFile`;
   - establish request and read-only scopes and their ownership checks;
   - test the generic layer with a small fake format, independently of data and
     sessions.
3. **Durable JSON files**
   - implement loading, complete pre-encoding and serialization, same-directory
     temporary writes, syncing, replacement, permission preservation, and
     cleanup;
   - add fault-injection tests at each boundary before integration.
4. **Concurrency coordination**
   - add the stable lock file and request-wide `flock` lifecycle;
   - verify that two associated files share one acquisition;
   - add deterministic thread and process concurrency tests.
5. **Application integration**
   - install the application-owned scope inside error capture and outside the
     component thread;
   - put its request-local handle on `Context`;
   - verify lock lifetime across normal responses, handled errors, unexpected
     exceptions, and teardown failures.
6. **Data and session integration**
   - add the intentionally non-strict initial `data.Format` and
     `session.Format` implementations;
   - move all domain filesystem access to coordinated `JSONFile` objects;
   - move the loaded `Sessions` collection onto `Context`;
   - finish with combined data/session lifecycle and multi-process tests.

Do not begin integration by moving the data format. The coordinator, scope, and
durable file behavior must first be testable without either domain.

## Tests

Add tests covering:

- format encoding completes before a destination is touched;
- JSON serialization failures preserve the old file;
- write, flush, sync, close, and replace failures preserve the old file where
  replacement has not completed;
- temporary files are removed after `Exception` and `BaseException` paths;
- readers observe either the complete old or complete new document;
- lock acquisition uses a separate stable lock file;
- the lock spans load, request processing, and all saves;
- lock release occurs after normal responses and exceptions;
- two worker processes cannot commit stale snapshots;
- concurrent threads are coordinated as well as separate worker processes;
- data and sessions share one lock without reentrant `flock` acquisition;
- request-local session collections cannot cross between concurrent requests;
- associated files reject mutation outside their application persistence scope;
- read-only audit scopes never save;
- read-only requests do not rewrite the data document;
- escaping exceptions do not write staged data changes;
- handled responses retain their established commit policy.

Use process-based concurrency tests for the Gunicorn defect; thread-only tests
are insufficient.

## Relationship to strict formats

This refactor establishes the names and boundaries used by the next plan:

```text
persist.JSONFile[data.Store]
	uses data.Format(schema)

persist.JSONFile[session.Sessions]
	uses session.Format()
```

Do not add model schema migrations, strict coercion changes, or comprehensive
corruption auditing here. Preserve the current logical JSON shape so durability
and concurrency behavior can be reviewed independently.

## Non-goals

Do not include:

- SQL or a backend-neutral transaction manager;
- independent locks for data and sessions;
- cross-file atomic transactions;
- strict attribute runtime checks;
- a new persisted JSON envelope;
- format migration dispatch;
- broad Cork data repair.

## Rollout and defect tracking

Before deploying:

1. back up both live JSON files;
2. exercise two-process concurrent requests against copied data;
3. verify interrupted writes leave a valid old or new document;
4. verify the lock path is writable and shared by all Gunicorn workers.

As fixes land, remove the resolved entries from
`.agents/notes/persistence-defects.md`. The note represents current defects, not
a historical changelog. Leave the bare corruption-error entry for the strict
formats plan if it has not yet been fixed.

## Final verification

1. Run the complete Helios test suite.
2. Run Ruff formatting and lint checks.
3. Confirm all data and session filesystem code uses `helios.persist`.
4. Confirm the application, rather than a component, owns the request lock.
5. Confirm the lock encloses both loads, the handler, and both teardown paths.
6. Confirm failed writes preserve the previous document.
7. Confirm concurrent Gunicorn-style workers cannot silently lose an update.
8. Confirm no production JSON data was rewritten during migration or audit.
