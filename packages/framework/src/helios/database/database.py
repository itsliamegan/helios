from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from .config import Config
from .registry import Registry
from .sqlite import connect
from .store import Store


@dataclass
class Database:
	config: Config
	registry: Registry

	@contextmanager
	def transaction(self) -> Generator[Store]:
		# Closing the connection rolls back a transaction the block left open.
		with connect(self.config) as connection:
			connection.begin()
			yield Store(connection, self.registry)
			connection.commit()
