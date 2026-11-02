from pathlib import Path
from typing import Self

from .error import MigrationError
from .migration import FILENAME, Migration


class Migrations:
	"""A complete sequence of migrations, numbered from 1 without gaps."""

	def __init__(self, migrations: list[Migration]):
		self.migrations = sorted(
			migrations,
			key=lambda migration: (migration.number, migration.path.name),
		)
		self.check_numbering()

	@classmethod
	def load(cls, directory: Path) -> Self:
		"""Read and validate every migration in a directory, ignoring hidden files."""

		if not directory.is_dir():
			raise MigrationError(f"migrations directory {directory} does not exist")

		paths = [
			path
			for path in sorted(directory.iterdir(), key=lambda path: path.name)
			if not path.name.startswith(".")
		]

		malformed = [
			path.name
			for path in paths
			if FILENAME.match(path.name) is None or not path.is_file()
		]
		if malformed:
			raise MigrationError(
				"migration files must be named NNNN_description.sql: "
				+ ", ".join(malformed)
			)

		return cls([Migration.read(path) for path in paths])

	@property
	def latest(self) -> int:
		return len(self.migrations)

	def after(self, version: int) -> list[Migration]:
		"""Select the migrations after a version.

		A version beyond the latest migration means the database was migrated by
		newer code, which this code cannot safely run against.
		"""

		if version > self.latest:
			raise MigrationError(
				f"database is at version {version}, "
				f"newer than the latest migration {self.latest:04d}"
			)
		return self.migrations[version:]

	def check_numbering(self):
		"""Refuse duplicate numbers and numbering that does not run from 1 to N."""

		by_number: dict[int, list[Migration]] = {}
		for migration in self.migrations:
			by_number.setdefault(migration.number, []).append(migration)

		duplicates = [
			migration.path.name
			for group in by_number.values()
			if len(group) > 1
			for migration in group
		]
		if duplicates:
			raise MigrationError(
				"duplicate migration numbers: " + ", ".join(duplicates)
			)

		out_of_sequence = [
			migration.path.name
			for position, migration in enumerate(self.migrations, start=1)
			if migration.number != position
		]
		if out_of_sequence:
			raise MigrationError(
				"migration numbers must run from 0001 without gaps: "
				+ ", ".join(out_of_sequence)
			)
