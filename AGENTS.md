# AGENTS

Helios is small, so read it directly rather than guessing at its API. Read the
module first, then write against it.

## Commands

- `just test`: Run the test suite.
- `just lint`: Run Ruff for formatting & linting.
- `just check`: Run Ty for type checking.

## Workflow

Always ensure the test suite passes, the formatter is clean, and the type
checker reports no errors before considering any work complete.

CI runs these steps on every pull request.

## Conventions

- Helios follows Rails and Laravel. When naming a concept or shaping an API,
  start from what they call it and how they structure it.
- Views always use a separate template language. Do not build HTML in Python.
- Generic helpers that are not specific to Helios, such as inflection and
  case handling, belong in Luna.
- Tests share one blog domain. Its models are `Post`, `Author`, `Comment`, and
  `Tag`. Its services, for tests that bind them, are `Moderator` and
  `Newsletter` for the application and `Reader` and `Visit` for a request.
