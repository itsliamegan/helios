from dataclasses import dataclass

from helios.database.config import Config
from helios.database.error import DatabaseError
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

		with self.connect() as connection:
			return read_version(connection)

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
		# Closing the connection rolls back a migration that failed partway.
		with self.connect() as connection:
			while migration := self.begin_next(connection):
				migration.run(connection)
				try:
					connection.commit()
				except DatabaseError as error:
					raise MigrationError(
						f"{migration.path.name}: could not commit"
					) from error
				applied.append(migration)
		return applied

	def begin_next(self, connection: Connection) -> Migration | None:
		"""Begin a transaction for the next pending migration, if there is one.

		The version is read inside the write transaction, so a concurrent runner
		cannot apply the same migration twice.
		"""

		try:
			connection.begin()
		except DatabaseError as error:
			raise MigrationError("could not begin a transaction") from error

		remaining = self.migrations.after(read_version(connection))
		return remaining[0] if remaining else None

	def connect(self) -> Connection:
		"""Open the database with foreign keys off.

		Turning them off lets migrations rebuild tables that others reference;
		each migration checks foreign keys before committing instead. SQLite
		ignores the pragma inside a transaction, so it runs before any begins.
		"""

		try:
			connection = connect(self.config)
		except DatabaseError as error:
			raise MigrationError(
				f"could not open database {self.config.path}"
			) from error

		try:
			connection.control("PRAGMA foreign_keys = OFF", "configuration")
		except DatabaseError as error:
			connection.close()
			raise MigrationError("could not disable foreign keys") from error
		return connection


@dataclass
class Status:
	current: int
	latest: int
	pending: list[Migration]


def read_version(connection: Connection) -> int:
	try:
		cursor = connection.execute("PRAGMA user_version")
		try:
			row = cursor.fetch_one()
		finally:
			cursor.close()
	except DatabaseError as error:
		raise MigrationError("could not read the database version") from error
	if row is None or not isinstance(row[0], int):
		raise MigrationError("could not read the database version")
	return row[0]
