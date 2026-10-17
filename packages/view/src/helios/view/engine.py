from collections.abc import Mapping, Sequence
from typing import Any, overload

from jinja2 import (
	BaseLoader,
	Environment,
	StrictUndefined,
	TemplateNotFound,
	TemplateRuntimeError,
)
from markupsafe import Markup

from .component import Component
from .extension import LayoutExtension, RenderExtension
from .helpers import Helpers
from .rendering import Rendering, Sections, rendering
from .source import Driver
from .view import View


class Engine:
	def __init__(
		self,
		driver: Driver,
		helpers: Helpers | None = None,
		components: Sequence[type[Component]] | None = None,
		fallbacks: Sequence[Driver] | None = None,
	):
		fallbacks = fallbacks or []

		self.jinja = Environment(
			loader=Loader(driver, fallbacks),
			extensions=[RenderExtension, LayoutExtension],
			autoescape=True,
			undefined=StrictUndefined,
			finalize=finalize,
			auto_reload=False,
			cache_size=-1,
		)

		self.helpers = Helpers.defaults()
		self.helpers.update(helpers or Helpers())
		self.jinja.filters.update(self.helpers.filters)
		self.jinja.globals.update(self.helpers.globals)

		templates = self.jinja.list_templates()
		for name in templates:
			self.jinja.get_template(name)

		registered: dict[str, Any] = {}
		for component in components or []:
			check_registration(component, registered, self.helpers, templates)
			registered[component.__name__] = component
		self.jinja.globals.update(registered)

	@overload
	def render(
		self, renderable: View, assigns: Mapping[str, Any] | None = None
	) -> str: ...

	@overload
	def render(self, renderable: Component) -> str: ...

	def render(
		self,
		renderable: View | Component,
		assigns: Mapping[str, Any] | None = None,
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
			current = Rendering(self, view.shared)
			token = rendering.set(current)
			try:
				assigns = assigns or {}
				context = {**view.shared, **assigns}
				html = self.jinja.get_template(view.name).render(context)

				chain = [view.name]
				while current.layout is not None:
					layout = current.layout
					if layout in chain:
						raise TemplateRuntimeError(
							f'The layouts of "{view.name}" form a loop'
						)
					chain.append(layout)

					current.layout = None
					html = self.jinja.get_template(layout).render(
						{
							**context,
							"content": Markup(html),
							"sections": Sections(current.sections),
						}
					)
				return html
			finally:
				rendering.reset(token)


class Loader(BaseLoader):
	def __init__(self, driver: Driver, fallbacks: Sequence[Driver]):
		self.drivers = [driver, *fallbacks]

	def get_source(
		self,
		environment: Environment,
		template: str,
	) -> tuple[str, str | None, None]:
		for driver in self.drivers:
			source = driver.source(template)
			if source is not None:
				return source.text, source.path, None
		raise TemplateNotFound(template)

	def list_templates(self) -> list[str]:
		names: list[str] = []
		for driver in self.drivers:
			for name in driver.names():
				if name not in names:
					names.append(name)
		return names


def finalize(value: Any) -> Any:
	if value is None:
		return ""
	else:
		return value


def check_registration(
	component: type[Component],
	registered: Mapping[str, Any],
	helpers: Helpers,
	templates: Sequence[str],
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
