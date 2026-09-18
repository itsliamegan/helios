from collections.abc import Iterable

from helios.app import Application, Container, Context, Next
from helios.app import Provider as ApplicationProvider
from helios.http import Request, Response

from .config import Config
from .model import Model
from .sqlite import connect
from .store import Registry, Store


class Provider(ApplicationProvider):
	def __init__(self, config: Config, model_types: Iterable[type[Model]]):
		self.config = config
		self.registry = Registry(model_types)

	def register(self, container: Container):
		container.scoped(Store, self.store)

	def boot(self, application: Application):
		application.use(self.middleware)

	def store(self, context: Context) -> Store:
		connection = context.enter(connect(self.config))
		connection.begin()
		return Store(connection, self.registry)

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		try:
			response = next(request, context)
			store = context.resolved(Store)
			if store is not None:
				store.connection.commit()
			return response
		except BaseException:
			store = context.resolved(Store)
			if store is not None:
				store.connection.rollback()
			raise
