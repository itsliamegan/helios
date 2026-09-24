from collections.abc import Callable
from typing import Any, TYPE_CHECKING

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound

from helios.app import Context

from .helpers import Helpers
from .source import Driver

if TYPE_CHECKING:
	from .views import View


class Engine:
	def __init__(
		self,
		driver: Driver,
		helpers: Helpers | None = None,
		reload: bool = False,
	):
		self.jinja = Environment(
			loader=Loader(driver),
			autoescape=True,
			undefined=StrictUndefined,
			auto_reload=reload,
			cache_size=-1,
		)

		self.helpers = Helpers.defaults()
		self.helpers.update(helpers or Helpers())
		self.jinja.filters.update(self.helpers.filters)
		self.jinja.globals.update(self.helpers.globals)
		self.composers: list[Composer] = []

		for name in self.jinja.list_templates():
			self.jinja.get_template(name)

	def composer(self, composer: Composer):
		self.composers.append(composer)

	def render(self, name: str, assigns: dict[str, Any] | None = None) -> str:
		if assigns is None:
			assigns = {}
		template = self.jinja.get_template(name)
		return template.render(**assigns)


class Loader(BaseLoader):
	def __init__(self, driver: Driver):
		self.driver = driver

	def get_source(
		self,
		environment: Environment,
		template: str,
	) -> tuple[str, str | None, Callable[[], bool]]:
		source = self.driver.source(template)
		if source is None:
			raise TemplateNotFound(template)
		else:
			return (
				source.text,
				source.path,
				lambda: self.driver.is_current(template, source),
			)

	def list_templates(self) -> list[str]:
		return self.driver.names()


type Composer = Callable[[View, Context], None]
