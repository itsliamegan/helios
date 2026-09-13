# Persistence defects

Current-state observations for Helios persistence. Remove entries as they are
fixed.

## Corruption reported as a bare `KeyError`

`data.decode` resolves persisted data through two unguarded dictionary lookups:

```python
model_type = schema.get_model_type(raw_model_data["_type"])
...
attr = model_type.attrs[name]
```

An unknown `_type` fails inside `Schema.get_model_type`, and a field with no
matching attribute fails while resolving `model_type.attrs`. Both surface as a
`KeyError` naming only the missing key, with no indication of which record was
being read. A missing `_type` key fails the same way. Because the data store
loads on every request, the result is a 500 on every page with no way to locate
the offending record.

Decoding should report the record position and field, for example:

```text
records[14]._type: unknown model type 'Bored'
records[22].colour: unknown attribute on Pin
```

The same loop assigns decoded models by ID without checking for collisions, so
a duplicate ID silently discards the earlier record. Low priority while the
framework is the only writer, but it is free to detect once the loop is already
tracking an index.
