from helios.app import Component, Context, Lifetime

from .config import Config
from .engine import Views, load


class Component(Component[Views]):
	lifetime = Lifetime.APPLICATION
	provides = Views

	def __init__(self, config: Config):
		self.dir = config.dir
		self.engine: Views | None = None

	def boot(self):
		self.engine = load(self.dir)

	def provide(self, ctx: Context) -> Views:
		if self.engine is None:
			raise RuntimeError("views component is not booted")
		return self.engine
