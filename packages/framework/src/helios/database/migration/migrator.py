from dataclasses import dataclass

from helios.database.config import Config
from helios.database.sqlite import Connection, connect

from .error import MigrationError
from .migration import Migration
from .migrations import Migrations


class Migrator:
	"""Brings one database up to date with a sequence of migrations."""

	def __init__(self, config: Config, migrations: Migrations):
		self.config = config
		self.migrations = migrations

	def version(self) -> int:
		"""Read the database's version without opening a transaction."""

		# Connecting would create an empty file, leaving a stray database behind
		# when the path is mistyped.
		if not self.config.path.is_file():
			raise MigrationError(f"database {self.config.path} does not exist")

		with connect(self.config) as connection:
			return connection.read_version()

	def status(self) -> Status:
		"""Report the database's version and the migrations it has not applied."""

		current = self.version()
		latest = self.migrations.latest
		return Status(
			current=current,
			latest=latest,
			pending=[] if current > latest else self.migrations.after(current),
		)

	def pending(self) -> list[Migration]:
		"""List the migrations apply would run, without changing the database."""

		return self.migrations.after(self.version())

	def apply(self) -> list[Migration]:
		"""Apply every pending migration, each in its own transaction.

		When a migration fails, it is rolled back and the ones before it stay
		committed, leaving the database at the last fully applied version.
		"""

		if not self.config.path.parent.is_dir():
			raise MigrationError(
				f"database directory {self.config.path.parent} does not exist"
			)

		applied = []
		# Foreign keys are off so migrations can rebuild tables that others
		# reference, and each migration checks them before committing instead.
		# Closing the connection rolls back a migration that failed partway.
		with connect(self.config, foreign_keys=False) as connection:
			while migration := self.begin_next(connection):
				migration.run(connection)
				connection.commit()
				applied.append(migration)
		return applied

	def begin_next(self, connection: Connection) -> Migration | None:
		"""Begin a transaction for the next pending migration, if there is one.

		The version is read inside the write transaction, so a concurrent runner
		cannot apply the same migration twice.
		"""

		connection.begin()
		remaining = self.migrations.after(connection.read_version())
		return remaining[0] if remaining else None


@dataclass
class Status:
	current: int
	latest: int
	pending: list[Migration]
