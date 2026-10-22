from collections.abc import Generator
from contextlib import contextmanager

from .config import Config
from .registry import Registry
from .sqlite import connect
from .store import Store


class Database:
	def __init__(self, config: Config, registry: Registry):
		self.config = config
		self.registry = registry

	@contextmanager
	def transaction(self) -> Generator[Transaction]:
		# Closing the connection rolls back a transaction the block left open.
		with connect(self.config) as connection:
			connection.begin()
			yield Store(connection, self.registry)
			connection.commit()


type Transaction = Store
