from collections.abc import Callable
from typing import Any

from jinja2 import BaseLoader, Environment, TemplateNotFound

from .helpers import Helpers
from .source import Driver


class Views:
	def __init__(
		self,
		driver: Driver,
		helpers: Helpers | None = None,
		reload: bool = False,
	):
		self.jinja = Environment(
			loader=Loader(driver),
			autoescape=True,
			auto_reload=reload,
			cache_size=-1,
		)
		self.helpers = Helpers.defaults()
		self.helpers.update(helpers or Helpers())
		self.jinja.filters.update(self.helpers.filters)
		self.jinja.globals.update(self.helpers.globals)
		for name in self.jinja.list_templates():
			self.jinja.get_template(name)

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
