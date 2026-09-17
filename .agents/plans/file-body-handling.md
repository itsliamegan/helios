# Helios: framework changes for file handling

## Problem

Helios cannot currently accept file uploads or serve binary file downloads.
Both limitations trace to concrete design choices in the HTTP layer that
assume all request and response content is text.

## 1. Request: add `File`, `Files`, and `request.files`

### Current state

`Request.input` holds an `Input`, which wraps `dict[str, str | list[str]]`.
This models URL-encoded form fields. When a browser submits a
`multipart/form-data` form (the encoding required for file inputs), each file
part carries binary content, a filename, and a content type — none of which
fit into `str | list[str]`.

In the WSGI adapter, `adapt_input` checks the content type: if it's
`application/x-www-form-urlencoded`, it reads and parses the input stream
into an `Input`. For every other content type — including
`multipart/form-data` — it returns an empty `Input()`. Multipart requests
arrive at handlers with no data at all.

### Changes

**New module: `http/file.py`.** Add a `File` class representing a single
uploaded file — at minimum, it holds the file's `bytes`, original `filename`,
and `content_type`. Add a `Files` class that wraps
`dict[str, File | list[File]]`, keyed by form field name, mirroring how
`Input` wraps `dict[str, str | list[str]]`. `Files` should support
`__getitem__` and `__contains__` like `Input` does.

**`Request` gets a `files` parameter.** `Request.__init__` takes a new
`files: Files` argument alongside `input: Input`. Handlers access uploaded
files through `request.files`. `Input` stays unchanged — it continues to
hold only text field values.

**`adapt_input` in `wsgi.py` gains a multipart branch.** When the content
type is `multipart/form-data`, the adapter parses the request body using
werkzeug's `FormDataParser` (already an available dependency). The parser
returns both text fields and file parts. Text fields go into `Input` as
they do for URL-encoded bodies. File parts are wrapped in `File` objects
and collected into a `Files` instance. The adapter function's return type
changes from `Input` to `(Input, Files)`, or alternatively `adapt_input`
is split into two functions — either way, `adapt_env` needs to construct
both and pass them to `Request`.

For non-multipart requests, `files` is an empty `Files()`.

**Cleanup opportunity.** The URL-encoded parsing path in `adapt_input`
currently does its own `parse_qs` on the raw stream. Werkzeug's
`FormDataParser` handles both URL-encoded and multipart bodies, so the
two branches could be consolidated into a single werkzeug-based parse
that always produces `(Input, Files)`. This would remove the manual
`parse_qs` / `latin_1` decode path.

### Testing

The `TestClient` wraps werkzeug's `Client` and passes `data=form` through
to it. Werkzeug's `Client` already supports file uploads in its `data`
parameter (using tuples or `FileStorage` objects), so once the server side
parses multipart requests, testing uploads should work without changes to
`TestClient`.

## 2. Response: support binary bodies

### Current state

`Body` wraps `str | None`. `adapt_res` in `wsgi.py` does
`str(res.body).encode("utf8")` to produce the WSGI response body, forcing
everything through string conversion. Binary content cannot survive this
path.

### Changes

**`Body` supports `bytes`.** `Body.__init__` accepts `str | bytes | None`.
`Body` needs a method or property that returns `bytes` for the WSGI
adapter — either encoding `str` content to UTF-8 or passing `bytes`
through directly. `Body.__str__` stays as-is for text bodies.

**`adapt_res` branches on content type.** Instead of
`str(res.body).encode("utf8")`, it calls the new bytes method on `Body`.

**New `Response` factory: `Response.file()`.** Takes `content: bytes`,
`filename: str`, and `content_type: str` as separate parameters. Sets
`Content-Type`, `Content-Disposition: attachment; filename="..."`, and
`Content-Length` headers. This sits alongside `Response.text()` and
`Response.html()`. It takes plain values rather than an `http.file.File`
so it stays independent of the upload representation and works for any
binary response.

## 3. Static file serving (optional, lower priority)

The file transfer app's download route will use `Response.file()`
directly in the handler. But if Helios eventually wants to serve CSS, JS,
or images for its view layer, it will need a static file middleware or a
built-in static route. This is not required for the file transfer app but
is adjacent work.

## Summary

Two additions to `http/`: a `file` module (`File`, `Files`) and binary
support in `Body`. One change to `Request` (the `files` parameter). One
change to `wsgi.py` (multipart parsing via werkzeug and binary-aware
response writing). One new `Response` factory method.
