# AGENTS

## Commands

- `mise run test`: Run the test suite.
- `mise run lint`: Run Ruff for formatting & linting.
- `mise run check`: Run Ty for type checking.

## Workflow

Always ensure the test suite passes, the formatter is clean, and the type
checker reports no errors before considering any work complete.

CI runs these steps on every pull request.
