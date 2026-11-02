"""A forward-only SQL migration runner for SQLite databases.

Migrations are `NNNN_description.sql` files numbered from 0001 without gaps.
`PRAGMA user_version` records the number of the last applied migration, and
each migration commits together with its version bump. Only the number is
recorded, so a description can be renamed after the migration has been applied.

Descriptions name the change, using plural table names:

- `create_initial_schema`, for the first migration only
- `create_<table>` and `drop_<table>`
- `add_<column>_to_<table>` and `drop_<column>_from_<table>`
- `change_<column>_in_<table>`, for a column's type, nullability, or default
- `rename_<old>_to_<new>_in_<table>`, for a column
- `rename_<old>_to_<new>`, for a table

A migration that touches several tables is named for its main change.
"""

from .error import ForeignKeyError, MigrationError
from .migration import Migration
from .migrations import Migrations
from .migrator import Migrator

__all__ = [
	"ForeignKeyError",
	"Migration",
	"MigrationError",
	"Migrations",
	"Migrator",
]
