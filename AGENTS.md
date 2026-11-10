# AGENTS

Helios is small, so read it directly rather than guessing at its API. Read the
module first, then write against it.

## Commands

- `just test`: Run the test suite.
- `just lint`: Run Ruff for formatting & linting.
- `just check`: Run Ty for type checking.

## Workflow

CI runs the tests, linter, and type checker on every pull request.

## Conventions

- Helios is inspired by Laravel, Hono, and Rails. When naming a concept or
  shaping an API, start from what they call it and how they structure it.
- Views always use a separate template language. Do not build HTML in Python.
- Generic helpers that are not specific to Helios, such as inflection and
  case handling, belong in Luna.
- Only a provider reads its `Config`. Services take the values they use.
- `Model`, `Form`, and `Component` declare their contents with bare class
  annotations (`title: str`) through one shared mechanism. Do not add wrapper
  types such as `Attribute[str]`, and do not give one of them a different
  declaration style.
- A `Model`, `Form`, or `Component` subclass lists exactly one base, the
  framework base. Share behavior by composition.
- Keyed classes such as `Session`, `Headers`, `Input`, and `Query` are not
  `Mapping`s. Write `__contains__(self, name: object)` by hand rather than
  inheriting the mapping API.
- Collection parameters take `Mapping` or `Sequence`. Use `dict` or `list` only
  where appropriate.
- Tests share one blog domain. Its core models are `Post`, `Author`,
  `Comment`, and `Tag`. A test adds a blog model, such as `Tagging` or
  `Draft`, when a case needs a shape the core models lack. Its services, for
  tests that bind them, are `Moderator` and `Newsletter` for the application
  and `Reader` and `Visit` for a request.
