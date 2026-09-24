from helios.app import Application, Container, Context, Provider
from helios.routing import URLs

from .config import Config
from .engine import Engine
from .file import Driver
from .helpers import Helpers
from .views import Views


class Provider(Provider):
	def __init__(self, config: Config, helpers: Helpers | None = None):
		self.dir = config.dir
		self.reload = config.reload
		self.helpers = helpers

	def register(self, container: Container):
		container.singleton(Engine, self.engine)
		container.scoped(Views, self.views)

	def boot(self, application: Application):
		application.container.get(Engine)

	def engine(self, container: Container) -> Engine:
		helpers = Helpers()
		if container.bound(URLs):
			helpers.globals["urls"] = container.get(URLs)
		helpers.update(self.helpers or Helpers())
		return Engine(Driver(self.dir), helpers, self.reload)

	def views(self, context: Context) -> Views:
		return Views(context.get(Engine), context)
