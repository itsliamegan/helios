from collections.abc import Callable
from typing import Any, TYPE_CHECKING, overload

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound

from helios.app import Context

from .attributes import html_name
from .component import Component, Constructor, rendering
from .extension import RenderExtension
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
		components: list[type[Component]] | None = None,
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

		constructors: dict[str, Any] = {}
		for component in components or []:
			check_registration(component, constructors, self.helpers, templates)
			constructors[component.__name__] = Constructor(component)
		self.jinja.globals.update(constructors)

	def composer(self, composer: Composer):
		self.composers.append(composer)

	@overload
	def render(
		self,
		renderable: str,
		assigns: dict[str, Any] | None = None,
	) -> str: ...

	@overload
	def render(self, renderable: Component) -> str: ...

	def render(
		self,
		renderable: str | Component,
		assigns: dict[str, Any] | None = None,
	) -> str:
		token = rendering.set(self)
		try:
			if isinstance(renderable, Component):
				return str(renderable)
			else:
				assigns = assigns or {}
				template = self.jinja.get_template(renderable)
				return template.render(**assigns)
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
	field_names = component.field_names()
	if name in registered:
		raise ValueError(f"Two components are named {name}")
	if name in helpers.globals:
		raise ValueError(f"Component {name} has the same name as a helper global")
	if component.template not in templates:
		raise ValueError(
			f'Component {name} uses the template "{component.template}", '
			"which does not exist"
		)
	if component.accepts and "attributes" not in field_names:
		raise ValueError(
			f"Component {name} declares accepts but has no attributes field"
		)
	for field_name in field_names:
		if html_name(field_name) in component.accepts:
			raise ValueError(
				f'Component {name} accepts "{html_name(field_name)}", '
				"which is also a field"
			)
	if "component" in field_names:
		raise ValueError(f'Component {name} has a field named "component"')


type Composer = Callable[[View, Context], None]
