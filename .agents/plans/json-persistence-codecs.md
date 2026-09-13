# Shared JSON persistence and strict codecs

## Goal

Introduce a shared JSON document persistence layer for Helios, then move the
model store and sessions onto separate strict codecs built on that layer.

This work follows the descriptor-based model attribute migration in
`.agents/plans/model_attribute_descriptors.md`. It uses the resulting compiled
model metadata and descriptor assignment checks rather than redesigning model
construction in parallel with that migration.

The intended architecture is:

```text
JSONFile[T]
  ├── StoreCodec(schema)     <-> Store
  │     └── attribute Type   <-> canonical model values
  └── SessionsCodec          <-> Sessions
```

`JSONFile` owns JSON and filesystem mechanics. Each document codec owns the
shape and meaning of its persisted data. Store attribute types own conversion
between individual JSON values and canonical Python values.

## Relationship to type conversion

Follow the terminology and boundaries in `.agents/notes/type-conversion.md`:

- document and attribute codecs **decode** and **encode** persisted values;
- model attributes **check** canonical Python values;
- form parsers continue to **parse** browser input;
- malformed persisted data is reported as corruption or schema incompatibility,
  not coerced or converted into a user-facing form error.

Do not introduce a universal `cast` operation. Store attributes and session
items may use small shared primitives where genuine duplication appears, but
they retain separate policies and error context.

### Descriptor typing and lifecycle follow-up

Complete the runtime side of the generic descriptor API as part of strict store
codec work:

- add `Type.check()` for canonical in-memory values without decoding or
  coercion;
- invoke checks during model initialization, default application, descriptor
  assignment, persisted hydration, and encoding;
- preserve contextual `ModelError` or codec errors rather than exposing errors
  incidental to a leaf implementation;
- model nullable attributes so descriptor access is typed as `T | None` while
  non-nullable attributes remain `T`;
- represent an unsaved `created_at` with a private unset sentinel, exposing
  `None` before first persistence without making the persisted attribute
  nullable;
- reject unset non-nullable values during encoding and assign `created_at`
  exactly once when a model is first added to a store;
- annotate heterogeneous compiled metadata such as `Model.attrs` sufficiently
  for the store implementation itself to pass static checking.

Keep `Model.__init__(**attrs: Any)` intentionally dynamic for now. Static
constructor synthesis, `dataclass_transform`, checker plugins, and generated
stubs are outside this work; invalid constructor values must instead fail
through canonical runtime checks.

## Shared JSON foundation

### JSON values

Define an explicit recursive `JSONValue` type covering JSON null, booleans,
numbers, strings, arrays, and objects. Code accepting dynamically loaded JSON
must still validate its runtime shape rather than relying only on annotations.

Session values should no longer be unconstrained `Any` at the persistence
boundary. Either reject non-JSON values when assigned or validate the complete
session document before writing it, with a useful error identifying the
session and item.

### Document codec protocol

Introduce a small generic protocol resembling:

```python
class Codec[T](Protocol):
	def encode(self, value: T) -> JSONValue: ...
	def decode(self, value: JSONValue) -> T: ...
```

A codec is responsible for the logical structure of one document. It does not
open files, lock resources, or interpret request input.

Use a dedicated decode error that codecs can enrich with structural paths such
as `records[4].board_id`. Encoding failures should likewise identify the value
that violated the in-memory contract rather than exposing an incidental
`json.dump` error.

### JSON file abstraction

Add a generic JSON file abstraction configured with a path and document codec.
It should own:

- loading and parsing JSON;
- passing the loaded JSON value to the codec;
- encoding values before any live file is modified;
- atomic same-directory temporary-file writes and replacement;
- flushing and syncing writes where supported;
- coordination between concurrent readers and writers;
- cleanup after failed writes;
- clear separation of filesystem, JSON syntax, and codec errors.

Concurrency protection must cover the complete read-modify-write lifetime, not
only the final `replace`, or two requests can load the same revision and lose
one request's changes. Establish this lifecycle explicitly in the component API.
Do not hide request-specific mutable state on a shared component instance.

Store and session files may use the same mechanism while retaining independent
locks and recovery policies. Cross-file transactions are not required by this
work.

## Store codec

Introduce a `StoreCodec` configured with a `Schema`. It owns the persisted store
document and model-record structure:

- validate the top-level document shape;
- identify the persisted format version;
- validate each record as an object;
- resolve `_type` through the schema;
- reject unknown model types and unexpected fields;
- decode built-in and application attributes through compiled descriptor
  metadata;
- apply nullable and missing/default policy explicitly;
- detect duplicate model IDs rather than silently replacing an earlier record;
- construct decoded models through a trusted internal path that preserves IDs
  and creation timestamps;
- encode all model fields through the same compiled metadata;
- avoid mutating the JSON value supplied to `decode`.

Attribute `Type` objects remain the leaf codecs. Extend them to provide strict
operations resembling:

```python
class Type[T]:
	def check(self, value: object) -> T: ...
	def decode(self, value: JSONValue) -> T: ...
	def encode(self, value: T) -> JSONValue: ...
```

Required behavior includes:

- `Str` accepts only JSON/Python strings;
- `Bool` accepts only actual booleans;
- `List` accepts only lists and reports the failing item index;
- `UUID` decodes only a valid UUID string and checks for `uuid.UUID` in memory;
- the datetime type decodes only its documented string representation and
  checks timezone/canonical-date policy explicitly;
- `null` is handled by attribute nullability rather than by every leaf type;
- encoding checks canonical values rather than coercing them.

Descriptor assignment and model construction should invoke these canonical
checks, ensuring bad values cannot enter through `Store.create`, defaults, or
later assignment and fail only during persistence.

Store codec errors should include enough context to locate corruption, for
example:

```text
records[14].board_id: invalid UUID string
records[22]._type: unknown model type 'Bored'
records[31].open_in_new_tab: expected a boolean, got a string
records[42].id: duplicate model ID
```

## Session codec

Introduce a separate `SessionsCodec` implementing the document codec protocol.
It should:

- require an object at the document root;
- decode every object key as a strict UUID string;
- require every session payload to be an object;
- validate nested session values as JSON values;
- encode session IDs and items without relying on the store's model or
  attribute rules;
- report malformed sessions with the session ID and item path where possible.

Keep session semantics independent from store schema semantics. Sessions are a
dynamic key-value facility and should not use model `Attribute` declarations or
store `Type` objects merely because both are persisted as JSON.

Move request-local loaded session state off `session.Component`. A component is
shared across requests, so storing the active `Sessions` collection on the
component can allow concurrent requests to overwrite one another's state. Put
the active collection or JSON-file transaction handle on `Context` and save the
same request-local value during component teardown.

Malformed or expired cookie IDs should be handled as session-boundary failures
according to an explicit policy, separately from corruption in the persisted
session document.

## Persisted format and compatibility

Preserve the current logical model and session representations during the first
refactor where practical. Add format versioning deliberately rather than as an
incidental consequence of moving code.

If a versioned store envelope is introduced, support the existing top-level
record list as an explicit legacy version so Cork's current data remains
readable. Do not rewrite production data until it has passed a read-only audit.

Decide and test missing-field policy explicitly:

- missing required persisted fields are errors;
- nullable fields may decode as `None` when absent if that remains the declared
  compatibility behavior;
- attributes with defaults may use those defaults for additive schema changes;
- unknown fields are errors unless a forward-compatibility policy is designed.

Provide a read-only audit path that loads and validates existing Cork store and
session files, reports every actionable error possible, and never saves the
result. Back up the original files before the first strict-codec deployment.

## Component and transaction lifecycle

Adapt the store and session components to use the shared JSON file lifecycle.
The design must guarantee that:

1. a request reads a coherent document revision;
2. its mutations apply to that request-local decoded value;
3. a successful request writes atomically;
4. an exception does not replace the prior document;
5. another writer cannot commit from a stale snapshot unnoticed.

Define whether handled 4xx/5xx responses commit mutations. Prefer an explicit
success/commit decision over inferring safety accidentally from middleware
ordering. Preserve ordinary successful redirect behavior.

Avoid introducing a general application transaction manager in this stage.
The JSON layer only needs a clear, testable unit-of-work lifecycle that a future
backend can replace.

## Suggested implementation stages

### Stage 1: Shared contracts

1. Complete the descriptor-based model attribute migration.
2. Add `JSONValue`, document codec protocols, and structured persistence errors.
3. Add focused tests for runtime JSON-shape validation and contextual errors.

### Stage 2: JSON file durability

1. Implement codec-driven loading and pre-encoding.
2. Implement atomic temporary writes, syncing, replacement, and cleanup.
3. Add locking around the complete read-modify-write lifecycle.
4. Test interrupted encoding/writing and concurrent stale writers.

### Stage 3: Strict store codec

1. Move store-level `encode` and `decode` behavior into `StoreCodec`.
2. Add strict `check`, `decode`, and `encode` behavior to attribute types.
3. Apply checks during model construction, defaults, and assignment.
4. Validate document and record structure, unknown fields, and duplicate IDs.
5. Preserve the existing store representation or provide an explicit legacy
   decoder.

### Stage 4: Session codec

1. Move session encoding and decoding into `SessionsCodec`.
2. Validate IDs, payload objects, and nested JSON values strictly.
3. Move request-local session collections off the shared component instance.
4. Use the common atomic and locked JSON lifecycle.

### Stage 5: Cork validation and rollout

1. Audit copies of Cork's existing store and session files without rewriting
   them.
2. Resolve any malformed or non-canonical values explicitly.
3. Verify logical encode/decode round trips for every Cork model and session
   shape.
4. Exercise representative concurrent store and session requests.
5. Back up live files and document recovery before enabling strict writes.

## Testing priorities

Add tests covering:

- primitive type rejection of formerly coerced values;
- checks during create, default application, assignment, and encoding;
- nullable values and additive defaults;
- malformed root documents and records;
- missing, extra, and unknown model fields/types;
- malformed and duplicate IDs;
- list item error paths;
- decode operations leaving their input unchanged;
- invalid nested session values;
- atomic writes preserving the old file after an encoding or write failure;
- concurrent requests not losing committed updates;
- request-local session state isolation;
- legacy Cork JSON compatibility;
- non-commit behavior after failed requests.

Run the complete Helios suite and Ruff checks after each stage. Validate Cork
against copied data before any live-file write.

## Non-goals

Do not include the following in this work:

- a universal casting or conversion API;
- form or route parsing changes unrelated to shared low-level helpers;
- a SQLite implementation or backend-neutral ORM;
- automatic relationship, uniqueness, or cascade declarations;
- cross-file transactions between the store and sessions;
- transparent repair or coercion of malformed persisted data;
- broad changes to Cork's public store query API.

This work should leave a clean boundary for a later SQLite store: Cork-facing
store operations and canonical model checks can remain stable, while SQLite
uses its own row/schema codec and transaction implementation rather than being
forced through the JSON file abstraction.

## Final verification

1. Confirm the descriptor migration is complete before integrating strict model
   checks.
2. Confirm store and session filesystem code uses the shared JSON abstraction.
3. Confirm store and session codecs remain separate and stateless.
4. Confirm all persisted values are validated without coercion.
5. Confirm failed or interrupted writes preserve the previous valid document.
6. Confirm concurrent requests cannot silently overwrite a newer revision.
7. Confirm existing Cork data passes the audit or produces precise remediation
   errors.
8. Confirm no production data is rewritten as an incidental migration step.
