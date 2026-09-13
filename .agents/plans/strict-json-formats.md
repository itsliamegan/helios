# Strict JSON data and session formats

## Goal

Make the existing Helios data and session JSON representations strict and
well-defined using the format boundary established by `helios.persist`:

```text
persist.JSONFile[T]
  ├── data.Format(schema)  <-> data.Store
  │     └── data.types.Type <-> canonical model values
  └── session.Format()     <-> session.Sessions
```

Document formats own the shape and meaning of complete JSON documents. Data
attribute types own conversion between individual JSON values and canonical
Python values. Model descriptors check canonical values supplied by application
code.

Preserve the existing document shapes exactly. Do not add an envelope, format
marker, compatibility dispatch, or migration machinery.

## Prerequisites

Complete these changes first:

1. explicit model-level `Store.save(model, *models)` and staged deletions;
2. the `helios.store` to `helios.data` namespace migration;
3. `helios.persist.Format`, coordinated `JSONFile`, durable writes, and the
   application-level request lock.

This plan tightens logical validation after file durability and concurrency are
already reliable.

## Terminology and boundaries

Follow `.agents/notes/type-conversion.md`:

- formats and attribute types **decode** and **encode** persisted values;
- model attributes **check** canonical Python values;
- forms **parse** browser input;
- malformed persisted data is corruption or schema incompatibility, not a form
  validation error;
- no boundary silently coerces an unrelated value.

Do not introduce a universal cast or conversion operation. Keep the method
names `check`, `encode`, and `decode` on `data.types.Type`.

## Existing JSON representations

The data document remains a top-level array:

```json
[
  {
    "_type": "Board",
    "id": "...",
    "created_at": "...",
    "title": "Example",
    "user_id": "..."
  }
]
```

The sessions document remains a top-level object:

```json
{
  "<session UUID>": {
    "_user_id": "<user UUID>"
  }
}
```

These are the only formats supported by this work. Strict validation must not
rewrite, wrap, tag, or otherwise migrate a valid existing document.

## JSON values

Use the recursive `persist.JSONValue` type for JSON null, booleans, finite
numbers, strings, arrays, and string-keyed objects.

Values loaded dynamically still require runtime validation. In particular:

- reject non-finite numbers accepted as extensions by Python's JSON parser;
- reject non-string object keys at the encoding boundary;
- reject unsupported Python objects;
- report cyclic arrays or objects as encoding errors rather than exposing a
  recursion or `json.dumps` implementation error.

Runtime validation should preserve a structural path to the invalid value.

## Format errors and paths

Provide dedicated decode and encode errors that distinguish malformed persisted
data from invalid in-memory state. Errors should carry structured path segments
and render useful locations such as:

```text
records[14].board_id: invalid UUID string
records[22]._type: unknown model type 'Bored'
records[31].open_in_new_tab: expected a boolean, got a string
records[42].id: duplicate model ID
sessions.<uuid>._flash.notice: expected a JSON value
```

Leaf implementations may raise focused local errors, but `data.Format`,
`session.Format`, descriptors, and model construction must preserve their own
context rather than exposing incidental `KeyError`, `TypeError`, or
`ValueError` exceptions.

Normal decode may fail at the first error. The separate read-only audit path
should aggregate independent actionable errors where continuing is safe.

## Data format

`data.Format` is configured with a `data.Schema` and implements
`persist.Format[data.Store]`.

### Document and record validation

It must:

- require an array at the document root;
- require every array item to be an object;
- require `_type` to be a string;
- resolve `_type` through the configured schema;
- reject unknown model types with record context;
- reject fields not declared in compiled model metadata;
- reject malformed, missing, or null generated fields;
- decode every field through its compiled `Attribute` metadata;
- detect duplicate model IDs before constructing the final Store;
- avoid mutating the JSON value supplied to `decode`.

Consider rejecting duplicate model names when constructing `Schema`, rather
than allowing later classes to silently replace earlier registrations.

### Missing, default, and null policy

Use these distinct rules:

- a present JSON `null` decodes to `None` only for a nullable attribute;
- explicit `None` remains `None`, even when the attribute also has a non-null
  default;
- a missing field with a declared default receives that default;
- a missing nullable field without another default receives `None`;
- a missing required non-nullable field is corruption or schema incompatibility;
- an unknown field is always an error.

Defaults applied during decode must pass the same canonical checks as defaults
used during ordinary model construction.

### Hydration and staged Stores

Construct decoded models through a trusted internal hydration path that
preserves IDs and creation timestamps without treating them as public
constructor input. Hydration must nevertheless check the resulting canonical
values.

Initialize the Store's baseline state so explicit saves can stage model-level
snapshots without accidentally treating every decoded model as new or dirty.
Encoding the committed projection must include only staged logical changes and
must check every model value that will be written.

## Attribute types

Retain `data.types.Type[T]` as the leaf abstraction:

```python
class Type[T]:
	def check(self, value: object) -> T: ...
	def decode(self, value: JSONValue) -> T: ...
	def encode(self, value: T) -> JSONValue: ...
```

Required behavior for the currently supported types:

- `Str` accepts only actual strings;
- `Bool` accepts only actual booleans;
- `Int` accepts integers but rejects booleans;
- `UUID` decodes only a valid UUID string and checks for `uuid.UUID` in memory;
- `Date` decodes only a valid ISO datetime string and checks for an aware
  `datetime` in memory;
- `Date.encode` preserves the documented ISO representation without coercing a
  naive datetime;
- `null` is handled by `Attribute.nullable`, not by leaf types;
- encoding invokes canonical checking before returning a JSON value.

Do not add a model `List` type in this work. Cork has no list-valued model
attribute, and nested session arrays are validated by `session.Format` rather
than `data.types`.

## Model runtime checks

Complete the runtime side of descriptor typing:

- check caller values during model initialization;
- check defaults when they are applied;
- check descriptor assignment;
- check trusted persisted hydration;
- check staged snapshots and encoding;
- translate leaf failures into contextual `ModelError` or format errors.

Keep `Model.__init__(**attrs: Any)` intentionally dynamic. Static constructor
synthesis, checker plugins, generated stubs, and `dataclass_transform` remain
outside this work.

Model nullable attributes should expose `T | None`, while non-nullable
attributes expose `T`. Preserve sufficiently accurate heterogeneous metadata
annotations for `Model.attrs` and Store implementation code. Make compiled
metadata immutable if that unfinished descriptor-migration requirement remains
outstanding.

### Unsaved creation timestamps

Represent an unsaved `created_at` internally with a private unset sentinel.
Descriptor access exposes `None` before first addition without declaring the
persisted attribute nullable.

`Store.add` assigns an aware UTC creation time exactly once. Encoding rejects an
unset non-nullable generated value. Hydrated models retain their persisted
creation time.

## Session format

`session.Format` implements `persist.Format[session.Sessions]` independently of
models and data attribute types.

It must:

- require an object at the document root;
- decode every object key as a strict UUID string;
- require every session payload to be an object;
- require session item keys to be strings;
- recursively validate all item values as JSON values;
- encode session IDs as UUID strings;
- report the session ID and nested item path where possible;
- avoid mutating the JSON value supplied to `decode`.

Session item annotations should no longer expose unconstrained `Any` at the
persistence boundary. They may use `JSONValue` directly while preserving the
dynamic key-value API.

Malformed cookie IDs are request-boundary input, not persisted-document
corruption. Treat an absent, malformed, or unknown cookie session ID as a fresh
session according to one explicit boundary policy; do not report it as a
session document format failure or allow it to become an incidental 500.

Keep the request-local `Sessions` collection on `Context`, as established by
the shared persistence plan.

## Read-only audit

Provide a read-only audit path for copies of Cork's data and session documents.
It must:

- acquire the coordinated persistence scope in read-only mode;
- parse and validate without staging or saving anything;
- report as many independent actionable errors as safely possible;
- identify document paths and expected canonical forms;
- verify duplicate model IDs and unknown model or field names;
- verify all session IDs and nested values;
- leave file contents and metadata unchanged.

The current preliminary inspection found the existing Cork shapes, UUIDs,
timestamps, and nested session values compatible, but the implemented formats
remain the authoritative audit.

Back up the original files before the first strict write deployment. Do not use
the audit as an automatic repair or migration tool.

## Testing priorities

Add tests covering:

- rejection of values previously coerced by `Str`, `Bool`, `Int`, `UUID`, and
  `Date`;
- canonical checks during construction, default application, assignment,
  hydration, staging, and encoding;
- nullable explicit values versus missing defaults;
- invalid defaults with model context;
- malformed data and session roots;
- non-object records and session payloads;
- missing, extra, and unknown model fields and types;
- malformed and duplicate IDs;
- malformed and naive datetimes;
- non-finite JSON numbers and unsupported nested session values;
- useful nested session paths, including array indexes;
- decode operations leaving their input unchanged;
- malformed and stale session cookies creating fresh sessions;
- encoding only the committed Store projection;
- existing Cork data and session compatibility without rewriting;
- audit aggregation and guaranteed read-only behavior.

Continue running durability and multi-process tests from the shared persistence
plan to ensure stricter encoding failures still preserve the previous file.

## Relationship to known defects

This plan fixes the bare-`KeyError` corruption reporting described in
`.agents/notes/persistence-defects.md` and broadens it into complete structural
validation.

After contextual format errors are implemented and tested, remove that entry
from the note. The atomic-write, concurrency, shared-session-state, and lock
cleanup entries should already have been removed by the shared persistence
work.

## Non-goals

Do not include:

- a persisted format marker or envelope;
- compatibility detection or migration dispatch;
- automatic data repair or coercion;
- a model `List` attribute type;
- form or route parsing changes;
- SQL or a backend-neutral ORM;
- cross-file transactions;
- relationships, uniqueness constraints, or cascades;
- broad changes to Cork's Store query API.

## Rollout

1. Audit copies of Cork's existing files without writing them.
2. Resolve every reported incompatibility explicitly.
3. Verify logical encode/decode round trips for every Cork model and session
   shape.
4. Exercise representative staged saves and session writes under the
   application persistence lock.
5. Back up live files.
6. Enable strict reads before allowing strict writes where deployment permits.
7. Confirm no file is rewritten merely because it was audited.

## Final verification

1. Confirm data and session formats are separate and filesystem-free.
2. Confirm all persisted values are validated without coercion.
3. Confirm model API values are checked before reaching persistence.
4. Confirm the existing JSON shapes remain unchanged.
5. Confirm Cork's copied data passes audit or yields precise remediation errors.
6. Run the complete Helios suite and Ruff checks.
7. Remove resolved entries from `.agents/notes/persistence-defects.md`.
