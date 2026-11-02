from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Self

from .error import ScriptError
from .statement import Raw


@dataclass
class Script:
	"""SQL text split into its complete statements."""

	statements: list[Raw]

	@classmethod
	def read(cls, path: Path) -> Self:
		"""Read a SQL file, skipping statements that hold only comments."""

		statements = []
		sql = ""
		for line in path.read_text().splitlines(keepends=True):
			sql += line
			if sqlite3.complete_statement(sql):
				statement = Raw(sql, ())
				if statement.body.strip(" \t\r\n;"):
					statements.append(statement)
				sql = ""

		if Raw(sql, ()).body:
			raise ScriptError(f"{path.name}: incomplete final statement")

		return cls(statements)
