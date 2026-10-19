from dataclasses import dataclass
from pathlib import Path
import re
from typing import Self

from helios.database.error import DatabaseError
from helios.database.script import Script
from helios.database.sqlite import Connection
from helios.database.statement import Raw

from .error import ForeignKeyError, MigrationError

FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
TRANSACTION_KEYWORDS = {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}


@dataclass
class Migration:
	number: int
	name: str
	path: Path
	script: Script

	@classmethod
	def read(cls, path: Path) -> Self:
		"""Read a migration file and split it into its SQL statements."""

		match = FILENAME.match(path.name)
		if match is None:
			raise MigrationError(
				f"migration files must be named NNNN_description.sql: {path.name}"
			)

		script = Script.read(path)
		for statement in script.statements:
			if statement.keyword in TRANSACTION_KEYWORDS:
				raise MigrationError(
					f"{path.name}: {statement.keyword} is not allowed, "
					f"the runner owns the transaction: {statement.summary}"
				)

		return cls(
			number=int(match.group(1)),
			name=path.stem,
			path=path,
			script=script,
		)

	def run(self, connection: Connection):
		"""Run the statements and record the version in the open transaction.

		The caller owns the transaction and commits it afterwards.
		"""

		for statement in self.script.statements:
			self.execute(connection, statement)

		self.check_foreign_keys(connection)
		connection.write_version(self.number)

	def execute(self, connection: Connection, statement: Raw):
		try:
			connection.execute(statement.sql, statement.parameters).close()
		except DatabaseError as error:
			raise MigrationError(
				f"{self.path.name}: {error}: {statement.summary}"
			) from error

		if not connection.in_transaction:
			raise MigrationError(
				f"{self.path.name}: statement ended the transaction early: "
				f"{statement.summary}"
			)

	def check_foreign_keys(self, connection: Connection):
		violations = connection.foreign_key_violations()
		if violations:
			details = "; ".join(
				f"{table} row {rowid} references missing {parent} (foreign key {index})"
				for table, rowid, parent, index in violations
			)
			raise ForeignKeyError(
				f"{self.path.name}: foreign key violations: {details}",
				violations,
			)
