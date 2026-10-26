from collections.abc import Sequence

from helios.app import Application, Container, Context, Provider
from helios.assets import Assets
from helios.routing import URLs

from .component import Component
from .composer import Composers
from .config import Config
from .engine import Engine
from .file import Driver
from .helpers import Helpers
from .views import Views


class Provider(Provider):
	"""Provides the template engine and each request's `Views`.

	The engine is built while booting, so a template error stops the
	application from starting. `urls` and `assets` become template globals
	when they are bound.
	"""

	def __init__(
		self,
		config: Config,
		helpers: Helpers | None = None,
		components: Sequence[type[Component]] | None = None,
	):
		self.config = config
		self.helpers = helpers
		self.components = components

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.instance(Composers, Composers())
		container.singleton(Engine, self.engine)
		container.scoped(Views, self.views)

	def boot(self, application: Application):
		application.container.get(Engine)

	def engine(self, container: Container) -> Engine:
		helpers = Helpers()
		if container.bound(URLs):
			helpers.globals["urls"] = container.get(URLs)
		if container.bound(Assets):
			helpers.globals["assets"] = container.get(Assets)
		helpers.update(self.helpers or Helpers())
		return Engine(
			Driver(self.config.directory),
			helpers,
			components=self.components,
		)

	def views(self, context: Context) -> Views:
		return Views(
			context.get(Engine),
			context.get(Composers),
			context,
		)
