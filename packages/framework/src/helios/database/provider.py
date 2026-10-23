from collections.abc import Generator, Iterable

from helios.app import Container, Context, Provider

from .config import Config
from .database import Database
from .migration import Migrations, Migrator
from .model import Model
from .registry import Registry
from .store import Store


class Provider(Provider):
	"""Provides the database and a `Store` for each request.

	A request's store is one transaction, which commits when the request
	succeeds and rolls back when it fails.
	"""

	def __init__(self, config: Config, model_types: Iterable[type[Model]]):
		self.config = config
		self.database = Database(
			config.path,
			Registry(model_types),
			busy_timeout=config.busy_timeout,
		)

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.instance(Database, self.database)
		container.singleton(Migrator, self.migrator)
		container.scoped(Store, self.store)

	def migrator(self, container: Container) -> Migrator:
		return Migrator(
			self.config.path,
			Migrations.load(self.config.migrations),
			busy_timeout=self.config.busy_timeout,
		)

	def store(self, context: Context) -> Generator[Store]:
		with context.get(Database).transaction() as transaction:
			yield transaction
