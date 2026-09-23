from helios.app import Application, Container, Provider

from .config import Config
from .engine import Views
from .file import Driver
from .helpers import Helpers


class Provider(Provider):
	def __init__(self, config: Config, helpers: Helpers | None = None):
		self.dir = config.dir
		self.reload = config.reload
		self.helpers = helpers

	def register(self, container: Container):
		container.singleton(Views, self.views)

	def boot(self, application: Application):
		application.container.get(Views)

	def views(self, container: Container) -> Views:
		return Views(Driver(self.dir), self.helpers, self.reload)
