from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from .registry import Registry
from .sqlite import Connection
from .store import Store


class Database:
	"""A handle to a potential SQLite database accessed through transactions.

	Each transaction opens its own connection and holds the database's write
	lock. It commits when its block ends and rolls back when the block raises.
	"""

	def __init__(
		self,
		path: Path,
		registry: Registry,
		busy_timeout: timedelta = timedelta(seconds=30),
	):
		self.path = path
		self.registry = registry
		self.busy_timeout = busy_timeout

	@contextmanager
	def transaction(self) -> Generator[Transaction]:
		# Closing the connection rolls back a transaction the block left open.
		with Connection.open(self.path, self.busy_timeout) as connection:
			connection.begin()
			yield Store(connection, self.registry)
			connection.commit()


type Transaction = Store
