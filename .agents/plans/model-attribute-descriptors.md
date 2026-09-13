# Descriptor-based model attributes

## Goal

Replace list-based model attribute declarations with descriptors so model fields
participate directly in Python class construction:

```python
class Pin(Model):
	url = Attribute(types.Str())
	title = Attribute(types.Str())
	board_id = Attribute(types.UUID(), nullable=True)
```

Make `id` and `created_at` genuine model attributes, remove the current reuse of
`attrs` for declarations, compiled class metadata, and instance values, and
eliminate RUF012 from application model declarations without suppressions.

Preserve the existing model access API (`pin.title`), store operations, error
semantics, and persisted JSON representation.

## Architectural boundary

Model attributes are class metadata and therefore use Python's descriptor and
class-construction protocols. Forms remain runtime values assembled from
`Field` objects; this change does not make forms class-based or attempt to give
models and forms identical declaration syntax.

The resulting responsibilities should be:

- `Attribute` describes one model field and mediates class-level metadata and
  instance-level value access.
- `Model` compiles inherited and locally declared attributes into a class-level
  schema.
- A model instance keeps its actual values in a private mapping with a distinct
  name.
- `Store` owns generated values and persistence, while relying on compiled model
  metadata for validation and encoding.
- `Schema` continues to map persisted model type names to model classes.

## Public model interface

1. Remove the attribute name from normal `Attribute` construction. The name is
   supplied by assignment in the model class body and captured through
   `__set_name__`.
2. Make class-level descriptor access return the `Attribute` itself, allowing
   model metadata to be inspected through expressions such as `Pin.title`.
3. Make instance-level descriptor access return the corresponding stored value.
4. Preserve model attribute assignment if it is currently considered supported.
   Assignment should update the private value mapping rather than shadowing the
   descriptor in the instance dictionary.
5. Preserve `default` and `nullable` declaration options and their current model
   creation behavior.
6. Retain a class-level `attrs` mapping as the complete compiled schema if useful
   for framework and user introspection. It should map names to `Attribute`
   objects, be distinct from instance values, and be exposed as immutable.
7. Treat the old `attrs = [Attribute(...)]` declaration syntax as an intentional
   breaking API change. Update Helios and Cork together rather than carrying a
   compatibility path through the class-construction machinery.

## Built-in attributes

1. Declare `id` and `created_at` on `Model` using the same descriptor mechanism
   as application-defined attributes.
2. Mark them as generated or non-initializable so callers of `Store.create` do
   not supply them as ordinary keyword attributes.
3. Include them in the compiled `attrs` mapping and expose their metadata through
   the class.
4. Continue assigning their values when a model is created or decoded.
5. Continue persisting them under the existing `id` and `created_at` JSON keys.
6. Prevent application models from accidentally replacing or disabling these
   built-ins unless an explicit supported override use case is identified.

Whether the generated-field marker is a public `Attribute` option such as
`init=False` or private metadata used only by `Model` should be decided while
implementing. Prefer the smallest API that still gives creation and decoding a
clear, non-name-based way to distinguish generated fields.

## Descriptor and value semantics

1. Have `Attribute.__set_name__` capture and retain the declared Python name.
2. Have descriptor reads from a model instance use a private value mapping such
   as `_values`; do not retain `self.attrs` for instance data.
3. Have descriptor reads from a model class return metadata rather than trying
   to read a value.
4. Decide model assignment behavior explicitly and test it. If assignment is
   supported, route it through the descriptor and preserve the current effective
   mutability of models.
5. Preserve the current distinction among missing, nullable, and defaulted
   values during construction.
6. Raise normal, useful model or attribute errors for uninitialized descriptor
   access instead of exposing internal mapping failures.
7. Keep runtime type checking and stricter codec behavior outside this migration.
   The separate type-conversion work can later add checks to descriptor
   assignment without coupling that policy change to the declaration refactor.

## Compiled model metadata

1. Replace conversion of a temporary declaration list with collection of
   `Attribute` descriptors from the class namespace.
2. Compile an ordered name-to-attribute mapping for each model class. Preserve
   declaration order so encoding remains stable and introspection is
   predictable.
3. Include inherited attributes when compiling a subclass. This should make
   concrete model inheritance well-defined rather than inheriting and then
   accidentally iterating a previously compiled dictionary as declarations.
4. Define overriding rules explicitly:
   - locally declared attributes may replace inherited application attributes
     if model inheritance is intended to support schema overrides;
   - built-in generated attributes remain reserved;
   - replacing an inherited attribute with a non-`Attribute` value should fail
     during class construction rather than leaving descriptor metadata and
     Python lookup behavior inconsistent.
5. Detect duplicate or conflicting attribute names at class construction and
   report them with the model and attribute name.
6. Expose the completed schema through an immutable mapping. The mapping is
   intentionally shared class metadata, so any remaining `ClassVar` annotation
   exists only inside the framework and accurately describes the value.
7. Keep schema compilation internal to `Model`; `Schema` should continue to deal
   with model types rather than individual fields.

## Model construction and store creation

1. Separate generated constructor values from caller-provided model attributes
   without relying on whether a name happens to be `id` or `created_at`.
2. Validate supplied keyword names against the compiled set of initializable
   attributes.
3. Reject extra, missing, and non-nullable `None` values with the current
   `ModelError` behavior.
4. Apply defaults and nullable absence exactly once during model construction.
5. Populate the private value mapping with both generated and ordinary
   attributes before normal descriptor reads are possible.
6. Keep `Store.create(model_type, **attrs)` unchanged for callers.
7. Avoid broad constructor API redesign unless needed to cleanly distinguish the
   internal decoding path from public store creation.

## Persistence

1. Drive encoding from the compiled attribute metadata rather than maintaining
   separate loops for built-in and declared attributes where practical.
2. Preserve the `_type`, `id`, `created_at`, and application attribute keys and
   encoded values exactly, so existing store files remain readable and newly
   saved files remain compatible.
3. Decode values with each attribute's store type and nullable behavior.
4. Ensure generated decoded values enter model construction through a trusted
   internal path rather than appearing as user-supplied create attributes.
5. Preserve model type lookup through `Schema` and model identity lookup through
   `Store`.
6. Do not combine this migration with stricter decoding, type coercion changes,
   transaction changes, or a new persistence format.

## Helios test migration

1. Convert test model declarations from `attrs` lists to named `Attribute`
   descriptors.
2. Preserve all existing tests for creation, defaults, nullability, missing and
   extra values, lookup, deletion, and encode/decode round trips.
3. Add focused tests proving:
   - descriptor names are inferred from class assignments;
   - class-level access returns attribute metadata;
   - instance-level access returns model values;
   - supported assignment updates the value used by later encoding;
   - `id` and `created_at` appear in compiled model metadata and work through
     descriptor access;
   - generated fields cannot be supplied through ordinary `Store.create`
     attributes;
   - compiled attribute metadata is immutable;
   - inherited fields are retained in subclasses;
   - overriding and reserved-name rules behave as designed;
   - models with no application-defined fields still work;
   - existing-format JSON data decodes and re-encodes without a schema change.
4. Add tests for useful failures during invalid class declarations rather than
   allowing errors to emerge only when instances are created or saved.

## Cork migration

1. Convert the four Cork model classes to descriptor declarations.
2. Remove repeated string names from every Cork `Attribute` construction.
3. Keep the Cork `Schema` declaration unchanged.
4. Preserve all handler, authorization, and template access through ordinary
   instance attributes; those call sites should not require migration.
5. Confirm the existing `data/store.json` loads without transformation and can
   be saved with the same structure.
6. Exercise creation and rendering for users, pins, boards, and shares against
   the already running Cork development server.
7. Record newly encountered framework friction in Cork's dogfooding notes only
   if the migration exposes an unresolved issue.

## Suggested implementation stages

### Stage 1: Descriptor foundation

1. Add name inference and class/instance descriptor behavior to `Attribute`.
2. Give model instances a private value mapping.
3. Compile descriptor declarations into immutable class metadata.
4. Establish inheritance, override, and reserved-name behavior.
5. Migrate enough store tests to exercise the new declaration syntax and run the
   complete Helios suite before changing persistence internals further.

### Stage 2: Built-in attributes and persistence

1. Represent `id` and `created_at` as generated descriptors.
2. Include them in compiled metadata while excluding them from ordinary create
   input.
3. Adapt encoding and decoding to the unified metadata without changing JSON.
4. Add compatibility and generated-field tests.

### Stage 3: Consumer migration

1. Convert all remaining Helios test declarations.
2. Convert Cork's model declarations.
3. Run Helios tests and Ruff checks.
4. Verify Cork can load its existing data and perform representative create,
   read, and save operations.

## Compatibility and non-goals

This migration intentionally changes model declaration syntax and
`Attribute` construction. It should not change:

- `Store.create`, `find_all`, `find_one`, `find_by`, or `delete` call shapes;
- ordinary instance access such as `pin.title`;
- form declarations or form parsing;
- route parameter conversion;
- persisted JSON structure;
- model type names;
- default and nullable semantics;
- store type conversion policy.

Do not add dataclass integration, annotation-derived store types, automatic form
generation, relationship descriptors, query expressions, migrations, or a new
schema DSL as part of this work.

## Final verification

1. Run the complete Helios test suite.
2. Run Ruff formatting and lint checks and confirm model declarations no longer
   trigger RUF012.
3. Confirm no model declaration still uses the old `attrs` list syntax.
4. Confirm instance values no longer share a name or dictionary with compiled
   class metadata.
5. Load and save a copy of Cork's existing store and compare its logical JSON
   structure.
6. Smoke-test Cork model creation and pages that read every model type using the
   existing development server.
