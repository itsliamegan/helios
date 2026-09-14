from helios.app import Container, Context, Provider

from .files import FilePersistence, Files, Persistence


class Provider(Provider):
	def __init__(self, files: Files):
		self.files = files

	def register(self, container: Container):
		container.scoped(Persistence, self.persistence)

	def persistence(self, context: Context) -> FilePersistence:
		return context.enter(self.files.lock())
