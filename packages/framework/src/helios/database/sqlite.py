from collections.abc import Iterable
import sqlite3
from typing import Any, Self, cast

from .codec import Scalar
from .config import Config
from .error import DatabaseBusyError, DatabaseError


def connect(config: Config, foreign_keys: bool = True) -> Connection:
	return Connection(config, foreign_keys=foreign_keys)


class Connection:
	def __init__(self, config: Config, foreign_keys: bool = True):
		try:
			self.connection = sqlite3.connect(
				config.path,
				autocommit=True,
			)
		except sqlite3.Error as error:
			raise translate(error, "connection") from error
		self.closed = False

		try:
			self.configure(config, foreign_keys=foreign_keys)
		except Exception:
			try:
				self.close()
			except DatabaseError:
				pass
			raise

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exception_type, exception, traceback):
		self.close()

	@property
	def in_transaction(self) -> bool:
		return self.connection.in_transaction

	@property
	def parameter_limit(self) -> int:
		return self.connection.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)

	def configure(self, config: Config, foreign_keys: bool):
		if foreign_keys:
			self.control("PRAGMA foreign_keys = ON", "configuration")
		else:
			self.control("PRAGMA foreign_keys = OFF", "configuration")
		self.control(
			f"PRAGMA busy_timeout = {config.busy_timeout.total_seconds() * 1000}",
			"configuration",
		)

	def begin(self):
		self.control("BEGIN IMMEDIATE", "transaction begin")

	def commit(self):
		if not self.in_transaction:
			return
		try:
			self.control("COMMIT", "transaction commit")
		except DatabaseError:
			if self.in_transaction:
				try:
					self.rollback()
				except DatabaseError:
					pass
			raise

	def rollback(self):
		if self.in_transaction:
			self.control("ROLLBACK", "transaction rollback")

	def read_version(self) -> int:
		cursor = self.execute("PRAGMA user_version")
		try:
			(version,) = cast(tuple[int], cursor.fetch_one())
		finally:
			cursor.close()
		return version

	def write_version(self, version: int):
		self.control(f"PRAGMA user_version = {version}", "version update")

	def foreign_key_violations(self) -> list[tuple[Scalar | None, ...]]:
		cursor = self.execute("PRAGMA foreign_key_check")
		try:
			return cursor.fetch_all()
		finally:
			cursor.close()

	def control(self, sql: str, operation: str):
		try:
			cursor = self.connection.execute(sql)
			cursor.close()
		except sqlite3.Error as error:
			raise translate(error, operation) from error

	def execute(
		self,
		sql: str,
		parameters: Iterable[Any] = (),
	) -> Cursor:
		try:
			return Cursor(self.connection.execute(sql, tuple(parameters)))
		except sqlite3.Error as error:
			raise translate(error, "statement") from error

	def close(self):
		if self.closed:
			return
		rollback_error: DatabaseError | None = None
		if self.in_transaction:
			try:
				self.rollback()
			except DatabaseError as error:
				rollback_error = error
		try:
			self.connection.close()
		except sqlite3.Error as error:
			raise translate(error, "connection close") from error
		self.closed = True
		if rollback_error is not None:
			raise rollback_error


class Cursor:
	def __init__(self, cursor: sqlite3.Cursor):
		self.cursor = cursor

	@property
	def columns(self) -> tuple[str, ...]:
		description = self.cursor.description
		if description is None:
			return ()
		return tuple(column[0] for column in description)

	@property
	def changed_rows(self) -> int:
		return self.cursor.rowcount

	def fetch_one(self) -> tuple[Scalar | None, ...] | None:
		try:
			return self.cursor.fetchone()
		except sqlite3.Error as error:
			raise translate(error, "fetch") from error

	def fetch_all(self) -> list[tuple[Scalar | None, ...]]:
		try:
			return self.cursor.fetchall()
		except sqlite3.Error as error:
			raise translate(error, "fetch") from error

	def close(self):
		try:
			self.cursor.close()
		except sqlite3.Error as error:
			raise translate(error, "cursor close") from error


def translate(error: sqlite3.Error, operation: str) -> DatabaseError:
	code = getattr(error, "sqlite_errorcode", None)
	if isinstance(code, int) and code & 0xFF in (
		sqlite3.SQLITE_BUSY,
		sqlite3.SQLITE_LOCKED,
	):
		return DatabaseBusyError(f"database {operation} could not acquire a lock")
	return DatabaseError(f"database {operation} failed: {error}")


def quote_identifier(identifier: str) -> str:
	escaped = identifier.replace('"', '""')
	return f'"{escaped}"'
