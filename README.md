# Helios

Helios is a small Python web framework. It includes:

- [HTTP request and response handling](src/helios/http/)
- [Routing with optionally typed parameters](src/helios/routing/)
- [Application container and components](src/helios/app/)
- [WSGI adapter](src/helios/wsgi/)
- [Data storage and model definitions](src/helios/data/)
- [View rendering](src/helios/views/)
- [Form validation](src/helios/form/)
- [Cookie-backed sessions](src/helios/session/)
- [Authentication](src/helios/auth/)

It is small enough to read & understand in an afternoon.

## Tests

Tests for each module sit in `test/` and are the fastest way to see intended
usage. Run them with:

```
mise run test
```
