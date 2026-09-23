from typing import TYPE_CHECKING

from helios.app import Application, Container, Provider

from .config import Config
from .helpers import Helpers

if TYPE_CHECKING:
	from .engine import Views


class Provider(Provider):
	def __init__(self, config: Config, helpers: Helpers | None = None):
		self.dir = config.dir
		self.helpers = helpers

	def register(self, container: Container):
		from .engine import Views

		container.singleton(Views, self.views)

	def boot(self, application: Application):
		from .engine import Views

		application.container.get(Views)

	def views(self, container: Container) -> Views:
		from .engine import load

		return load(self.dir, self.helpers)
