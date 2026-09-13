# Password-backed authentication

## Goal

Add the framework primitives needed for Cork to authenticate a selected user with
a password while preserving Helios's existing division of responsibility:

- Cork identifies an account by its existing model UUID and owns the sign-in,
  user-administration, and password-policy flows.
- Helios securely represents and verifies passwords, remembers an arbitrary
  model in a server-side session, and manages that session safely.

Helios will not provide a base user model, username field, routes, handlers, or
templates. Cork's current `User.name` remains a display label rather than a
unique authentication identifier.

The intended Cork model API is:

```python
class User(Model):
	name = attr(str)
	password = attr(Password, nullable=True)
	open_in_new_tab = attr(bool, default=False)
```

The nullable declaration supports migrating existing Cork users without
inventing passwords. New users created through the administration path should
receive a password; users without one cannot sign in.

## Custom attribute types

### Structural `Type` protocol

Replace the concrete `helios.data.types.Type` base class with a runtime-checkable
generic protocol describing the operations the store actually uses:

```python
class Type[T](Protocol):
	def encode(self, value: T) -> Any: ...
	def decode(self, value: Any) -> T: ...
```

The built-in `Str`, `Bool`, `Int`, `UUID`, and `Date` codecs should satisfy the
protocol structurally rather than through inheritance. Preserve their existing
persistence behavior in this work; comprehensive strict decoding remains a
separate concern.

Keep `attr()` as the public extension point. It should:

1. resolve supported built-in Python types to the existing codec objects;
2. accept an object that already satisfies `Type[T]`; and
3. accept a value class such as `Password` when the class object satisfies the
   protocol through class-level `encode` and `decode` methods.

This permits:

```python
password = attr(Password)
```

`Password` is both the canonical Python value type and, as a class object, the
codec retained by `Attribute`. In other words, the class returned by
`type(password)` implements `Type[Password]`; individual `Password` values do
not need to be codec instances.

Move built-in resolution out of `Type.resolve()`. `Type` should state a
contract, not also own a registry of concrete implementations. Resolution can
remain an implementation detail of `attr()` or a helper called only by it.
Reject unsupported classes at model declaration time with the existing useful
`TypeError` behavior.

Preserve all `attr()` overload behavior for defaults and nullability. Confirm
with Ty that `attr(Password)` exposes `Password` and
`attr(Password, nullable=True)` exposes `Password | None` through the descriptor.

## Password representation

Add `Digest` and `Password` to `helios.auth`.

### `Digest`

`Digest` encapsulates the password-hashing library and the encoded digest. It
should provide behavior resembling:

```python
digest = Digest.generate(plaintext)
digest.check(candidate)
digest.encode()
Digest.decode(encoded)
```

Requirements:

- delegate hashing and verification to `werkzeug.security`, which is already a
  Helios dependency;
- use Werkzeug's current secure password-hashing default rather than defining a
  Helios cryptographic format;
- retain the complete self-describing encoded value, including its salt and
  parameters;
- never retain plaintext after generation or checking;
- reject non-string persisted representations;
- redact the encoded value from `repr`;
- do not compare plaintext or digests directly as authentication logic.

Keep all direct calls to Werkzeug's generation and checking functions inside
`Digest`. This gives hashing behavior an object boundary without exposing bare
cryptographic functions as the Helios API.

### `Password`

`Password` is the model-facing domain value. It owns a `Digest` internally but
does not expose the digest or encoded string as part of its ordinary domain API.
It should provide behavior resembling:

```python
password = Password.from_plaintext(plaintext)
password.matches(candidate)
```

It also implements the class-object `Type[Password]` contract:

```python
Password.encode(password)
Password.decode(encoded)
```

Both operations should be class methods so the `Password` class object can be
stored directly as an attribute codec. Encoding and decoding delegate to
`Digest`; decoding must treat its input as an existing encoded digest and must
never hash it again.

Construction from plaintext must remain explicit. Do not make the ordinary
constructor guess whether a string is plaintext or encoded. Redact both the
plaintext and digest from `repr` and error messages.

Password acceptance policy, such as minimum length, remains an application
validation concern. `Password` is responsible only for secure transformation
and verification.

## Session hardening

Password authentication must not build on the current client-selectable session
identifier behavior.

### Server-generated identifiers

When a request has no session cookie, an invalid UUID cookie, or a valid UUID
that is not present in the session store, create a session with a fresh
server-generated UUID. Never adopt an unknown identifier supplied by the
client.

Malformed cookies should be treated as absent rather than escaping as an
unexpected error.

### Session regeneration

Add an explicit operation resembling `Session.rotate()` that:

- assigns a fresh UUID;
- preserves existing non-authentication session values;
- marks the session collection dirty;
- rekeys the owning `Sessions` collection; and
- ensures the previous UUID is omitted from the next persisted document.

Keep the owning collection and session object consistent immediately after
regeneration rather than relying on a later encode pass to repair stale keys.
The response must set the cookie to the rotated identifier.

Call regeneration from `Authenticator.sign_in()` before storing the user ID.
Call it from `Authenticator.sign_out()` after removing the authentication key.
Sign-out should continue preserving unrelated values such as flashes while
making the prior session identifier unusable.

When the authentication component encounters a malformed stored user ID or a
user that no longer exists, remove the stale authentication key and provide a
signed-out authenticator.

### Cookie policy

Extend cookies and session configuration sufficiently for the session cookie
to have:

- `HttpOnly`, enabled unconditionally;
- `SameSite=Lax` by default;
- configurable `Secure`, enabled by Cork in HTTPS deployments;
- the existing path and expiry behavior unless deliberately reconfigured.

Preserve local HTTP development by making the `Secure` setting explicit in
Cork's environment-backed configuration. Validate supported SameSite values
rather than serializing arbitrary text.

CSRF protection is related but remains separate work; SameSite is not a
replacement for CSRF tokens.

## Authenticator boundary

Keep the existing credential-independent authenticator API:

```python
auth.user
auth.is_signed_in()
auth.sign_in(user)
auth.sign_out()
```

The authenticator should not receive a password, find users by name, or know
where a password is stored. Cork loads the selected UUID, asks that user's
`Password` to verify the candidate, and calls `sign_in()` only after success.

Continue storing only the user UUID in the session. Do not store a password,
digest, or serialized user object in session data.

## Cork integration

Adapt Cork without changing the user-selection model:

1. Add a nullable `Password` attribute to `User` so the current store remains
   readable.
2. Update the user administration path to require a plaintext password when
   creating a login-capable user and store `Password.from_plaintext(value)`.
3. Add a password input to the existing user chooser form.
4. Have the sign-in handler parse the UUID and password, load that exact user,
   check `user.password.matches(candidate)`, and then call `auth.sign_in(user)`.
5. Treat a missing password, unknown user, and incorrect password as the same
   authentication failure; do not reveal digest details.
6. Keep `User.name` non-unique and use it only to label chooser options.
7. Update Cork's test support so authenticated requests use actual passwords
   rather than bypassing the public sign-in flow.

Existing Cork data currently has users without a password field. Do not assign a
shared or predictable migration password. Those users remain unable to sign in
until the administrator explicitly assigns one. After every intended account
has a password, making the field non-nullable can be considered as a separate
schema cleanup.

Do not write plaintext passwords, generated digests, or live Cork data into test
fixtures or logs. Tests should generate passwords at setup time.

## Suggested implementation stages

### Stage 1: Extensible model types

1. Convert `Type` to a runtime-checkable protocol.
2. Make built-in codecs structural implementations.
3. Move type resolution behind `attr()` and accept conforming class objects.
4. Add a small test-only custom value class with class-level encode/decode and
   prove it round-trips through `Store`.
5. Run Ruff, Ty, and the complete Helios suite before adding authentication
   behavior.

### Stage 2: Password values

1. Implement and test `Digest` around Werkzeug.
2. Implement `Password` creation, checking, redacted representation, and
   persistence hooks.
3. Round-trip a model containing both required and nullable Password attrs.
4. Confirm decode never rehashes persisted values and independently generated
   passwords use distinct salted encodings.

### Stage 3: Session regeneration

1. Reject malformed and unknown client-selected session IDs.
2. Add collection-aware session regeneration.
3. Rotate on sign-in and sign-out while preserving unrelated session values.
4. Remove stale authentication session entries.
5. Add cookie Secure and SameSite support and session configuration.
6. Exercise the complete component/persistence lifecycle to prove old IDs are
   removed and new cookies resolve to the same retained session state.

### Stage 4: Cork adoption

1. Add the nullable password field and confirm a copy of the existing Cork store
   loads unchanged.
2. Update the administration and sign-in flows.
3. Migrate Cork's authentication and request tests.
4. Assign real passwords through the administration path rather than editing
   stored digests manually.
5. Run both projects' full test and lint commands before deployment.

## Testing priorities

Add focused coverage for:

- a custom value class used directly through `attr(CustomValue)`;
- custom type defaults and nullability;
- static descriptor types under Ty;
- correct and incorrect password checks;
- salted generation producing different encoded values for the same plaintext;
- password and digest representations not leaking stored material;
- password persistence round trips;
- malformed persisted password values;
- missing, malformed, stale, and unknown session cookie IDs;
- regeneration changing the ID and removing the old persisted key;
- sign-in and sign-out both rotating IDs;
- unrelated session and flash values surviving rotation;
- SameSite, Secure, HttpOnly, expiry, and cookie serialization;
- Cork users without passwords being rejected safely;
- successful and unsuccessful Cork sign-ins through the real request lifecycle.

Do not assert Werkzeug's exact encoded format or current default parameters;
those are library implementation details. Assert observable generation,
checking, persistence, and redaction behavior instead.

## Non-goals

Do not include:

- a Helios base `User` class;
- usernames, emails, or uniqueness constraints;
- Helios-provided registration, sign-in, or password-reset handlers and views;
- automatic password-policy validation;
- digest exposure from `Password`;
- password recovery or reversible encryption;
- authorization roles or permissions;
- login throttling, lockout, or audit history;
- persistent-session invalidation across every browser after a password change;
- CSRF protection in the same change;
- broad strictness changes to all existing model codecs.

## Final verification

1. Run `mise run test` and `mise run lint` in Helios.
2. Run Ty against Helios and the `attr(Password)` Cork declaration.
3. Run Cork's complete test and lint commands.
4. Confirm copied pre-password Cork data still loads.
5. Confirm no unknown client-provided UUID becomes a server-side session ID.
6. Confirm sign-in and sign-out invalidate the previous session ID.
7. Confirm no plaintext password or encoded digest appears in responses, logs,
   object representations, or session files.
8. Confirm Helios contains no user model, username policy, routes, or templates.
