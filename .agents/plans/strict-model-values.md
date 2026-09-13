# Strict model values and data types

## Goal

Ensure model attributes contain canonical Python values without implementing the
broader strict-document work described in `strict_json_formats.md`.

Keep the three relevant operations distinct:

```python
class Type[T]:
	def check(self, value: object): ...
	def decode(self, value: JSONValue) -> T: ...
	def encode(self, value: T) -> JSONValue: ...
```

- `check` asserts that application code supplied an already-canonical Python
  value. It does not convert or return that value.
- `decode` independently validates and converts a persisted JSON value.
- `encode` checks a canonical Python value and converts it to JSON.

Preserve the existing model API and persisted JSON representation.

## Scope

Implement:

- `Type.check` for every existing data type;
- strict leaf decoding and encoding;
- canonical checks during model construction, default application, assignment,
  and persisted hydration;
- correct distinctions among missing values, explicit `None`, and defaults.

Do not implement:

- path-aware format errors;
- complete document-shape validation;
- recursive JSON validation;
- duplicate record or schema detection;
- session format changes;
- audit or migration tooling;
- a new persistence envelope or format marker.

## Type behavior

Update `src/helios/data/types.py` to use `persist.JSONValue` instead of `Any` at
codec boundaries.

`check` should raise a focused `TypeError` when a value is not canonical. It
should complete without returning a value when the check succeeds.

Implement these canonical checks:

- `Str`: require `str`;
- `Bool`: require `bool`;
- `Int`: require `int` while explicitly rejecting `bool`;
- `UUID`: require `uuid.UUID`;
- `Date`: require `datetime` with a non-null `tzinfo` and `utcoffset()`.

Do not allow `check` to coerce values.

### Decode

Each `decode` implementation validates its persisted representation directly;
it should not delegate its input to `check`.

- `Str.decode` accepts only a JSON string.
- `Bool.decode` accepts only a JSON boolean.
- `Int.decode` accepts only a JSON integer and rejects booleans.
- `UUID.decode` requires a string and parses it as a UUID. Reject canonical
  `UUID` objects and malformed strings.
- `Date.decode` requires an ISO datetime string, parses it, and rejects malformed
  or naive results. Reject canonical `datetime` objects.

Decode failures may use ordinary focused `TypeError` or `ValueError` exceptions.
Do not add a format-error hierarchy as part of this work.

The primitive checks for strings, booleans, and integers may look similar in
`check` and `decode`. Prefer that small duplication over coupling the model and
persistence boundaries.

### Encode

Every `encode` implementation calls its own `check` before serialization. This
is coherent because both operations consume canonical Python values and keeps
direct codec use defensive.

- strings, booleans, and integers retain their JSON scalar representation;
- UUIDs encode as strings;
- datetimes encode through the existing `isoformat()` representation.

Encoding a value of the wrong canonical type, including a naive datetime, must
fail before returning a JSON value.

## Attribute nullability

Keep nullability outside leaf types. Add an attribute-level check that:

1. accepts `None` only when the attribute is nullable;
2. otherwise calls the attribute type's `check` method;
3. translates leaf failures to `ModelError` with model and attribute context;
4. performs no conversion and does not replace the supplied value.

Useful errors should identify at least the model and field, for example:

```text
Post.points: expected an integer, got bool
Post.title: cannot be null
```

Exact path-aware persistence errors remain out of scope.

## Construction and defaults

Revise `Model._initialize` so it treats supplied, missing, and null values as
separate cases.

For each initializable attribute:

1. If the caller supplied the field, check and retain that exact value. An
   explicit `None` remains `None` when nullable, even if a non-null default is
   declared.
2. If the field is missing and has a declared default, check and apply the
   default.
3. If the field is missing, has no declared default, and is nullable, use
   `None`.
4. Otherwise report the required field as missing.

For example:

```python
class Post(Model):
	title = attr(str, default="Untitled", nullable=True)


Post().title  # "Untitled"
Post(title=None).title  # None
```

An invalid default should fail with model and attribute context when the default
is applied. A supplied value should not be replaced merely because it is falsey.

The existing `_MISSING`, `required`, and stored `default` fields already retain
enough information to implement these rules; do not redesign the declaration
API solely for this change.

## Assignment

Check a proposed value at the start of `Attribute.__set__`, before recording an
old value or modifying `_values`.

If the check fails:

- the current attribute value remains unchanged;
- `_old_values` remains unchanged;
- the caller receives a contextual `ModelError`.

Successful assignment retains the existing snapshot behavior used by explicit
`Store.save`.

## Persisted hydration and nulls

Keep persisted conversion in `data.store.decode`, but correct its null policy:

- a present JSON `null` becomes `None` only for a nullable attribute;
- a present JSON `null` never selects the attribute default;
- a missing field with a declared default receives that checked default;
- a missing nullable field without a default receives `None`;
- a missing required field remains an error.

Present non-null fields continue through the leaf type's `decode` method.
Hydration must apply attribute checks to the resulting canonical values so
models cannot bypass the same invariant used by ordinary construction and
assignment. It should also check defaults applied for missing persisted fields.

Do not expand this work into root, record, unknown-field, unknown-model, or
duplicate-ID validation.

## Generated values

`created_at` is persisted as a required, aware datetime but is publicly `None`
before a new model is first saved. Once non-nullable descriptor assignment is
checked, ordinary assignment cannot initialize it to `None`.

Preserve the current behavior with a narrow internal initialization exception:
place the initial `created_at = None` directly into the new model's private
value mapping rather than passing it through normal descriptor assignment.
`Store.save` should continue assigning an aware UTC datetime through the checked
descriptor exactly once.

Hydrated `created_at` values must decode and check as aware datetimes. Do not add
the broader unset-sentinel design in this work.

## Tests

Add focused tests under `test/data/` covering:

### Types

- each `check` accepts its canonical Python type;
- `Str`, `Bool`, and `Int` reject values they previously coerced;
- `Int` rejects booleans in both `check` and `decode`;
- UUID checking accepts only `UUID`, while decoding accepts only valid strings;
- date checking accepts only aware datetimes;
- date decoding rejects non-strings, malformed strings, and naive datetimes;
- every encoder rejects a non-canonical value;
- valid values retain their existing encoded representation.

### Models

- construction rejects a wrong canonical type;
- nullable construction accepts and preserves explicit `None`;
- explicit `None` does not select a declared default;
- a missing field applies and checks its default;
- a missing nullable field without a default becomes `None`;
- a non-nullable explicit `None` is rejected;
- invalid defaults fail when applied with model and field context;
- assignment rejects an invalid value without changing model or snapshot state;
- valid assignment and explicit save behavior remain unchanged;
- a new model still exposes `created_at is None` before first save;
- first save assigns an aware creation timestamp exactly once.

### Persistence

- strict leaf values still round-trip through data encoding and decoding;
- persisted nullable `null` remains `None` even when the attribute has a
  non-null default;
- a missing persisted field applies a checked default;
- malformed leaf representations are rejected;
- naive persisted datetimes are rejected;
- hydrated values receive canonical checks;
- the existing JSON record shape and scalar encodings remain unchanged.

Test observable model and round-trip behavior rather than private helper calls,
except for direct unit coverage of the public `Type` operations.

## Implementation order

1. Add strict `check`, `decode`, and `encode` behavior to data types.
2. Add nullable-aware attribute checks and enforce them on assignment.
3. Correct construction and default handling.
4. Apply the same checks and null policy to persisted hydration.
5. Preserve the internal unsaved `created_at` exception.
6. Run the complete test suite and Ruff checks.

## Final verification

1. No existing data type coerces unrelated values.
2. `check` validates without converting or returning the value.
3. `decode` validates persisted representations independently of `check`.
4. `encode` checks canonical input before serialization.
5. Construction, defaults, assignment, and hydration enforce the same model
   invariant.
6. Explicit nullable `None` remains distinct from a missing field.
7. Persisted JSON shapes and valid scalar representations are unchanged.
8. The complete Helios suite and Ruff checks pass.
