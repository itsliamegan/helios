from collections.abc import Generator

from helios.app import Application, Container, Context, Provider
from helios.http import Status

from .config import Config
from .database import Database
from .error import NotFoundError
from .migration import Migrations, Migrator
from .registry import Registry
from .store import Store


class Provider(Provider):
	"""Provides the database and a `Store` for each request.

	A request's store is one transaction, which takes the database's write lock
	on its first statement, commits when the request succeeds, and rolls back
	when it fails.
	"""

	def __init__(self, config: Config, registry: Registry):
		self.config = config
		self.registry = registry
		self.database = Database(
			config.path,
			registry,
			busy_timeout=config.busy_timeout,
		)

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.instance(Registry, self.registry)
		container.instance(Database, self.database)
		container.singleton(Migrator, self.migrator)
		container.scoped(Store, self.store)

	def boot(self, application: Application):
		application.rescue(NotFoundError, Status.NOT_FOUND)

	def migrator(self, container: Container) -> Migrator:
		return Migrator(
			self.config.path,
			Migrations.load(self.config.migrations),
			busy_timeout=self.config.busy_timeout,
		)

	def store(self, context: Context) -> Generator[Store]:
		with context.get(Database).store() as store:
			yield store
