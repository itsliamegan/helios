from helios.app import Component, Context

from .files import FilePersistence, Files, Persistence


class Component(Component[Persistence]):
	provides = Persistence

	def __init__(self, files: Files):
		self.files = files

	def provide(self, ctx: Context) -> FilePersistence:
		return ctx.enter(self.files.lock())
