from collections.abc import Generator, Iterable

from helios.app import Container, Context, Provider

from .config import Config
from .database import Database
from .migration import Migrations, Migrator
from .model import Model
from .registry import Registry
from .store import Store


class Provider(Provider):
	def __init__(self, config: Config, model_types: Iterable[type[Model]]):
		self.config = config
		self.database = Database(config, Registry(model_types))

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.instance(Database, self.database)
		container.singleton(Migrator, self.migrator)
		container.scoped(Store, self.store)

	def migrator(self, container: Container) -> Migrator:
		return Migrator(self.config, Migrations.load(self.config.migrations))

	def store(self, context: Context) -> Generator[Store]:
		with context.get(Database).transaction() as store:
			yield store
