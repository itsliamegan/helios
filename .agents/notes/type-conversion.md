# Type conversion design notes

Helios has several boundaries where values need to be converted into canonical
Python values. These operations are related, but they do not have the same
responsibilities or failure semantics. The framework should share small
conversion primitives where useful without introducing one universal `cast`
operation.

## Terminology

Use specific terms instead of "casting":

- **Parse**: convert untrusted textual input into a Python value.
- **Decode / encode**: convert between a persisted representation and a Python
  value.
- **Validate**: decide whether an input or value is acceptable.
- **Check**: ensure that application code supplied the expected canonical Python
  type.
- **Coerce**: permissively convert an arbitrary value. Helios should generally
  avoid coercion because it can hide malformed input or stored data.

## Conversion boundaries

| Boundary        | Raw representation             | Meaning of failure                |
|-----------------|--------------------------------|-----------------------------------|
| Form input      | `str`, `list[str]`, or missing | A user-facing field error         |
| Route parameter | A path segment string          | The route does not match          |
| Stored data     | A JSON value                   | Corrupt data or a schema mismatch |
| Model API       | A Python value                 | A programmer or domain error      |

Each boundary may use a similarly shaped decoder, but the boundary must retain
control over how errors are interpreted.

## Form parsers and validation are separate responsibilities

A form parser only converts an extracted form representation into a canonical
Python value. It does not decide whether the value is required or valid for the
application.

For example, a UUID parser is responsible for:

```text
"102ddad7-06d1-484f-a3f8-3cf4711e91ba" -> UUID(...)
"not-a-uuid"                            -> ParseError
```

Validation rules are separately responsible for constraints such as:

- whether a field is required;
- string length or numeric range;
- whether two fields agree;
- whether a referenced record exists;
- whether the current user may reference that record.

Keeping parsers and rules separate allows a parser to be reused under different
validation policies. A UUID field may be required in one form and optional in
another without changing what it means to parse a UUID.

A field validation pipeline should be conceptually:

1. Extract the raw value while preserving missing versus present.
2. Apply raw-input rules such as `required`.
3. Parse the raw value into its canonical Python type.
4. Apply typed validation rules.
5. Add the typed value to the form data, or attach errors to the field.

The exact API still needs to account for rules that run before parsing and rules
that run after parsing. These stages should be explicit rather than inferred
from callable signatures.

An illustrative API is:

```python
form = Form(
	[
		Field("title", parser=parsers.Str(), raw_rules=[rules.required]),
		Field("user_id", parser=parsers.UUID(), raw_rules=[rules.required]),
		Field("board_id", parser=parsers.Optional(parsers.UUID())),
	]
)
```

After successful validation, handlers receive typed data:

```python
data, errors = form.validate(req.input.items)
if not errors:
	user = ctx.store.find_one(User, data["user_id"])
```

They should not need to repeat `UUID(data["user_id"])` themselves.

## Form parsers understand browser input

Form parsers consume the representation produced by `helios.http.Input`:
`str | list[str]`, plus a distinct missing state. They may understand browser
conventions such as:

- a blank optional select value mapping to `None`;
- repeated fields mapping to a list;
- a checkbox being absent when unchecked;
- textual date, number, or UUID syntax.

These conventions must not leak into model attributes or persistence codecs.
For example, `""` may represent no selection in a form, but it is not a valid
stored UUID.

Missing, blank, and null are distinct concepts. A private `MISSING` sentinel is
preferable to collapsing all three to `None` before parsing and validation.

## Concrete form requirements from Cork

The board edit form supplies a repeated `user_id` checkbox field. It needs a
parser that declares the field to be a collection and has these semantics:

| Raw input | Parsed input |
|-----------|--------------|
| missing | `[]` |
| `"<uuid>"` | `[UUID("<uuid>")]` |
| `["<uuid-1>", "<uuid-2>"]` | `[UUID("<uuid-1>"), UUID("<uuid-2>")]` |
| a malformed item | a field parse error |

The collection parser should own both cardinality normalization and per-item
parsing. An API could resemble:

```python
Field("user_id", parser=parsers.Repeated(parsers.UUID()))
```

This parser only establishes a canonical `list[UUID]`. Whether those UUIDs
identify existing users who may receive access remains application/domain
logic; it should not be built into the form parser.

A boolean form parser should understand the representation produced by a
single checkbox, where absence means unchecked rather than an empty
collection:

| Raw input | Parsed input |
|-----------|--------------|
| missing | `False` |
| `"on"` | `True` |
| any unexpected scalar or a list | a field parse error |

The public interface should describe the resulting type rather than the HTML
widget:

```python
Field("archived", parser=parsers.Bool())
```

`Bool` can support standard explicit true/false strings in addition to the
browser's default `"on"` value if concrete forms require them, but it should
reject unrecognized values rather than silently treating them as false. A raw
`required` rule can still distinguish “must be checked” from ordinary boolean
parsing. Checkbox groups that represent selected values use
`Repeated(item_parser)` instead.

Forms also need a result that preserves submitted values and field errors so an
application can re-render a bound form after syntactic or rule failures. This
is presentation support for validation results, not a reason to move domain
operations into `Form`.

## Store types describe persistence

The store's `Type[T]` abstraction converts between JSON and a canonical Python
value. It does not parse HTML form conventions and does not produce user-facing
validation errors.

A store type should provide operations resembling:

```python
class Type[T]:
	def check(self, value: object) -> T: ...

	def decode(self, value: JSONValue) -> T: ...

	def encode(self, value: T) -> JSONValue: ...
```

- `check` rejects non-canonical values supplied through the model API.
- `decode` strictly reads a JSON representation.
- `encode` writes a checked canonical value as JSON.

Store decoding should be strict. In particular:

- a JSON string should not silently become a boolean;
- a JSON number should not silently become a string;
- `null` should only be accepted for nullable attributes;
- malformed UUIDs and dates should identify corrupt or incompatible data.

The current permissive behavior of operations such as `Bool.decode("false")`
and `Str.decode(42)` can hide data errors and should be replaced with strict
checks.

Model construction and attribute assignment should use the same canonical type
checks. Otherwise invalid values can enter a model through `Store.create` or a
later assignment and fail only when the store is saved.

## How parsers and store types are related

A form parser and a store type may produce the same Python type:

```text
Form UUID parser ----\
                      > uuid.UUID
Store UUID decoder --/
```

They remain separate classes because they describe different source
representations and have different error contracts. They can share low-level
implementation helpers, such as strict UUID-string parsing, without one calling
through a context-dependent universal caster.

This distinction becomes especially important for booleans and optional values:

```text
Form checkbox: missing or "on" -> browser-specific interpretation
Stored boolean: true or false  -> Python bool
Model value: Python bool only
```

A method such as `cast(value, source="form")` should be avoided. It centralizes
unrelated policy in conditionals and makes behavior difficult to infer at a
call site.

## Shared abstractions

If repeated code justifies it, parsers, route converters, and store decoders can
share a minimal protocol and conversion exception:

```python
class DecodeError(ValueError):
	pass


class Decoder[Raw, T](Protocol):
	def decode(self, value: Raw) -> T: ...
```

Each consumer translates `DecodeError` according to its boundary:

- a form records a field error;
- a route treats the conversion as a non-match;
- the store raises a contextual store/model decoding error.

This protocol is an implementation convenience, not a reason to merge form
parsers and store types.

## Suggested implementation order

1. Introduce a distinct missing-value sentinel for form extraction.
2. Add parser classes and parse errors to `helios.forms`.
3. Make `Field` explicitly sequence raw validation, parsing, and typed
   validation.
4. Add parsers for strings, UUIDs, optional values, booleans, and repeated
   values as real use cases require them.
5. Make store types decode JSON strictly and check canonical Python values.
6. Apply store type checks during both model construction and assignment.
7. Extract shared decoder protocols or primitive helpers only after concrete
   duplication appears.

The desired convergence is therefore not a single casting API. It is a
consistent flow into canonical Python values, with parsing, persistence, and
validation kept as separate responsibilities.
