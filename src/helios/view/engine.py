from collections.abc import Callable, Sequence
from typing import Any, overload

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound

from helios.app import Context

from .component import Component, Rendering, rendering
from .extension import RenderExtension
from .helpers import Helpers
from .source import Driver
from .view import View


class Engine:
	def __init__(
		self,
		driver: Driver,
		helpers: Helpers | None = None,
		reload: bool = False,
		components: Sequence[type[Component]] | None = None,
	):
		self.jinja = Environment(
			loader=Loader(driver),
			extensions=[RenderExtension],
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

		templates = self.jinja.list_templates()
		for name in templates:
			self.jinja.get_template(name)

		registered: dict[str, Any] = {}
		for component in components or []:
			check_registration(component, registered, self.helpers, templates)
			registered[component.__name__] = component
		self.jinja.globals.update(registered)

	def composer(self, composer: Composer):
		self.composers.append(composer)

	@overload
	def render(
		self, renderable: View, assigns: dict[str, Any] | None = None
	) -> str: ...

	@overload
	def render(self, renderable: Component) -> str: ...

	def render(
		self,
		renderable: View | Component,
		assigns: dict[str, Any] | None = None,
	) -> str:
		if isinstance(renderable, Component):
			component = renderable
			token = rendering.set(Rendering(self, {}))
			try:
				return str(component)
			finally:
				rendering.reset(token)
		else:
			view = renderable
			token = rendering.set(Rendering(self, view.shared))
			try:
				assigns = assigns or {}
				template = self.jinja.get_template(view.name)
				return template.render({**view.shared, **assigns})
			finally:
				rendering.reset(token)


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


def check_registration(
	component: type[Component],
	registered: dict[str, Any],
	helpers: Helpers,
	templates: list[str],
):
	name = component.__name__
	if name in registered:
		raise ValueError(f"Two components are named {name}")
	if name in helpers.globals:
		raise ValueError(f"Component {name} has the same name as a helper global")
	if component.template not in templates:
		raise ValueError(
			f'Component {name} uses the template "{component.template}", '
			"which does not exist"
		)


type Composer = Callable[[View, Context], None]
