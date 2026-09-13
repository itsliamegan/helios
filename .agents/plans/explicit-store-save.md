# Explicit model saves

## Goal

Replace automatic whole-store persistence after every normally completed request
with an explicit model-level save API:

```python
ctx.store.save(board)
ctx.store.save(board, pin)
```

Calling `Store.save` stages only the models passed to that call. A normally
completed request persists the staged model snapshots during component teardown.
Mutations to other models remain request-local and are discarded.

Deletion remains an explicit store operation and stages itself automatically:

```python
ctx.store.delete(Board, board.id)
```

This work precedes the `helios.store` to `helios.data` namespace migration and
the shared `helios.persist` layer. Implement it against the current store
module without introducing the later filesystem abstraction in parallel.

## Current behavior

`store.Component.before` loads the complete JSON document into a request-local
`Store`. `store.Component.after` writes the complete in-memory Store after every
normally returned response, even when the request only read data.

Consequently:

- every model mutation is persisted implicitly;
- callers cannot save one model without also saving unrelated mutations;
- every normally completed request rewrites the store file;
- handled HTTP errors commit mutations because `handle_http_errors` converts
  them to responses inside the component chain;
- unexpected exceptions skip `Component.after` and therefore do not save, but
  this is incidental rather than an explicit store policy.

The current write path remains vulnerable to the durability defects in
`.agents/notes/persistence-defects.md`. Those filesystem and concurrency defects
are addressed by the later shared persistence plan rather than expanded here.

## Public API

```python
class Store:
	def save(self, model: Model): ...
```

The call stages the specified models; it does not write the JSON file
immediately. Requiring at least one positional model avoids giving `save()` the
old meaning of committing every mutation in the Store.

A model passed to `save` must be the live model currently held by that Store.
Reject models from another Store and replacement objects that merely reuse an
existing ID. Report the failure as a useful `ModelError` or store-specific
programming error.

## Staging semantics

`Store` needs to distinguish three states:

1. the baseline state loaded at the start of the request;
2. live models used by handlers and templates;
3. model snapshots and deletions explicitly staged for persistence.

`save(model)` captures each specified model at call time. This gives
`save` local, predictable meaning:

- changes made before the call are staged;
- later changes to that model require another `save` call;
- saving the model again replaces its earlier staged snapshot;
- changes to models never passed to `save` are not persisted;
- a newly created model is persisted only if it is saved;
- saving multiple models stages one coherent set of snapshots.

Do not retain the mutable live model object as the staged representation. A
later assignment through that object must not silently alter an earlier save.
Use a trusted model snapshot or equivalent internal representation that
preserves model type, ID, creation time, and attribute values.

The Store should be able to produce a committed projection consisting of:

- baseline models that were not changed explicitly;
- staged model snapshots replacing baseline records with the same IDs;
- staged new models;
- no records for staged deletions.

The JSON file is still physically rewritten as a complete document. “Only save
that model” describes which logical record changes are included, not an
in-place file update.

## Creation and generated values

Keep `Store.create` and `Store.add` as request-local operations. They should not
stage persistence automatically.

Continue assigning `created_at` when a model is first added to a Store, exactly
once. An unsaved model may therefore have a creation timestamp even if the
request ends without saving it; no timestamp reaches persistence until the
model itself is saved.

## Deletion

Keep the current public operation:

```python
store.delete(ModelType, id)
```

Deletion stages persistence automatically because the deletion call is already
an explicit mutation command and the removed model is no longer available to
pass to `save`.

Define ordering behavior explicitly:

- saving and then deleting a model stages deletion;
- deleting a model removes any earlier staged save for that ID;
- deleting a missing or wrong-type model retains the current public error
  behavior unless a focused API correction is required;
- unrelated unsaved model mutations remain excluded from the committed
  projection.

## Component and response lifecycle

Change `store.Component.after` to write only when the request-local Store has
staged model saves or deletions. It writes the Store's committed projection,
not all live objects.

Adopt this explicit outcome policy:

- any normally returned `Response` permits staged changes to be written;
- this includes redirects, handled 4xx responses, and explicitly returned 5xx
  responses;
- an exception escaping the inner component chain prevents the store teardown
  write;
- repeated `save` calls remain staged until that one teardown write.

The current middleware order already distinguishes returned responses from
escaping exceptions. Add tests so this is intentional behavior rather than an
accident of ordering.

The later `helios.persist` plan will place teardown inside the request-level
filesystem lock. Until that lands, this stage improves commit semantics but
does not fix multi-process lost updates.

## Encoding boundary

Keep the existing persisted JSON representation and current encode/decode
policy in this stage. Do not introduce strict attribute checks, document
formats, format errors, or a new file abstraction here.

Encoding the committed projection must not mutate the baseline, live models, or
staged snapshots. A successful teardown can clear or promote staged state for
consistency in direct component tests, although ordinary request Stores are
then discarded.

## Cork migration

Update every Cork mutation path:

- save newly created models explicitly;
- save edited models after their final intended assignment;
- pass all related created or edited models when an operation logically saves
  several records;
- leave delete calls explicit without a following save solely for the deleted
  model;
- do not add saves to read-only handlers.

Pay particular attention to handlers that create a board and shares, rebuild
ordering records, or update a board and its access records. Their intended
record set should be visible at each save call.

## Tests

Add focused tests covering:

- a saved existing model is persisted;
- an unsaved existing-model mutation is discarded;
- saving one model excludes mutations to another model;
- multiple models can be staged in one call;
- a save captures call-time state;
- saving a model again replaces its staged snapshot;
- a newly created unsaved model is omitted;
- a newly created saved model is included;
- a model from another Store is rejected;
- deletion stages itself;
- deletion supersedes an earlier save;
- read-only requests do not rewrite the store;
- redirects write staged changes;
- handled 4xx and returned 5xx responses write staged changes;
- escaping exceptions do not write staged changes;
- the existing logical JSON record representation is unchanged.

Test observable persisted results rather than private staging containers.

## Relationship to known defects

This plan makes the exception/save policy identified in
`.agents/notes/persistence-defects.md` deliberate. It does not yet fix:

- truncation before encoding;
- interrupted or partial writes;
- coordination between Gunicorn workers;
- locking and cleanup.

Keep those defect entries until the shared persistence plan lands. Remove or
revise only the entry about incidental failed-request save behavior when these
outcome semantics are implemented and tested.

## Non-goals

Do not include:

- `helios.persist`;
- process or thread locking;
- atomic temporary-file replacement;
- strict JSON decoding;
- strict model attribute checks;
- the `helios.store` to `helios.data` rename;
- SQL or a backend-neutral Store protocol.

## Final verification

1. Run the complete Helios test suite.
2. Run Ruff formatting and lint checks.
3. Confirm Cork mutation handlers explicitly save every intended created or
   edited model.
4. Confirm read-only Cork requests no longer rewrite the store.
5. Confirm the persisted JSON structure is unchanged.
6. Confirm the remaining durability and concurrency defects are still tracked
   in `.agents/notes/persistence-defects.md`.
