from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Self

from helios.database.error import DatabaseError
from helios.database.sqlite import Connection

from .error import ForeignKeyError, MigrationError

FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
TRANSACTION_KEYWORDS = {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}


@dataclass
class Migration:
	number: int
	name: str
	path: Path
	statements: list[str]

	@classmethod
	def read(cls, path: Path) -> Self:
		"""Read a migration file and split it into its SQL statements."""

		match = FILENAME.match(path.name)
		if match is None:
			raise MigrationError(
				f"migration files must be named NNNN_description.sql: {path.name}"
			)

		return cls(
			number=int(match.group(1)),
			name=path.stem,
			path=path,
			statements=split(path),
		)

	def run(self, connection: Connection):
		"""Run the statements and record the version in the open transaction.

		The caller owns the transaction and commits it afterwards.
		"""

		for statement in self.statements:
			self.execute(connection, statement)

		self.check_foreign_keys(connection)
		connection.write_version(self.number)

	def execute(self, connection: Connection, statement: str):
		try:
			connection.execute(statement).close()
		except DatabaseError as error:
			raise MigrationError(
				f"{self.path.name}: {error}: {summarize(statement)}"
			) from error

		if not connection.in_transaction:
			raise MigrationError(
				f"{self.path.name}: statement ended the transaction early: "
				f"{summarize(statement)}"
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


def split(path: Path) -> list[str]:
	"""Split a migration file into its complete SQL statements."""

	statements = []
	statement = ""
	for line in path.read_text().splitlines(keepends=True):
		statement += line
		if sqlite3.complete_statement(statement):
			if strip_leading_comments(statement).strip(" \t\r\n;"):
				statements.append(statement)
			statement = ""

	if strip_leading_comments(statement):
		raise MigrationError(f"{path.name}: incomplete final statement")

	for statement in statements:
		match = re.match(r"[A-Za-z]+", strip_leading_comments(statement))
		keyword = "" if match is None else match.group(0).upper()
		if keyword in TRANSACTION_KEYWORDS:
			raise MigrationError(
				f"{path.name}: {keyword} is not allowed, "
				f"the runner owns the transaction: {summarize(statement)}"
			)

	return statements


def strip_leading_comments(statement: str) -> str:
	"""Remove whitespace and comments from the start of a statement."""

	remainder = statement.lstrip()
	while True:
		if remainder.startswith("--"):
			end = remainder.find("\n")
			remainder = "" if end == -1 else remainder[end + 1 :]
		elif remainder.startswith("/*"):
			end = remainder.find("*/")
			remainder = "" if end == -1 else remainder[end + 2 :]
		else:
			return remainder
		remainder = remainder.lstrip()


def summarize(statement: str) -> str:
	"""Collapse a statement onto one line, shortened for error messages."""

	text = " ".join(strip_leading_comments(statement).split())
	return text if len(text) <= 80 else text[:77] + "..."
