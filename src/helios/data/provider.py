from helios.app import Application, Container, Context, Next, Provider
from helios.http import Request, Response
from helios.persist.files import Files, Persistence

from .config import Config
from .store import Format, Schema, Store


class Provider(Provider):
	def __init__(self, config: Config, files: Files, schema: Schema):
		self.file = files.json(config.store_file, Format(schema))

	def register(self, container: Container):
		container.scoped(Store, self.store)

	def boot(self, application: Application):
		application.use(self.middleware)

	def store(self, context: Context) -> Store:
		persistence = context.get(Persistence)
		return persistence.open(self.file).load()

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		store = context.resolved(Store)
		if store is not None and store.pending:
			persistence = context.get(Persistence)
			persistence.open(self.file).save(store)
			store.pending.clear()
		return response
