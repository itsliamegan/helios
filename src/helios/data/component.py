from helios.app import Component, Context
from helios.http import Request, Response
from helios.persist.files import Files, Persistence

from .config import Config
from .store import Format, Schema, Store


class Component(Component[Store]):
	provides = Store
	requires = (Persistence,)

	def __init__(self, config: Config, files: Files, schema: Schema):
		self.file = files.json(config.store_file, Format(schema))

	def provide(self, req: Request, ctx: Context) -> Store:
		persistence = ctx.get(Persistence)
		return persistence.open(self.file).load()

	def finish(self, res: Response, ctx: Context):
		store = ctx.get(Store)
		persistence = ctx.get(Persistence)

		if store.pending:
			persistence.open(self.file).save(store)
			store.pending.clear()
