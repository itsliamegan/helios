from contextvars import ContextVar
from dataclasses import Field, fields
from typing import Any, ClassVar, TYPE_CHECKING

from markupsafe import Markup

from .attributes import Attributes, html_name

if TYPE_CHECKING:
	from .engine import Engine

rendering: ContextVar[Engine] = ContextVar("rendering")

global_attributes = {"class", "id", "hidden"}


class Component:
	__dataclass_fields__: ClassVar[dict[str, Field[Any]]]

	template: ClassVar[str]
	accepts: ClassVar[set[str]] = set()

	def __post_init__(self):
		if "attributes" not in field_names(type(self)):
			return
		attributes: Attributes = vars(self)["attributes"]
		for name in sorted(attributes.names()):
			if not allowed(type(self), name):
				raise TypeError(
					f'{type(self).__name__} does not accept the attribute "{name}"'
				)

	def __html__(self) -> Markup:
		engine = rendering.get(None)
		if engine is None:
			raise RuntimeError(
				f"{type(self).__name__} was rendered outside a view; "
				"use engine.render(component)"
			)
		template = engine.jinja.get_template(self.template)
		values = {name: getattr(self, name) for name in field_names(type(self))}
		values["component"] = self
		return Markup(template.render(values))

	def __str__(self) -> str:
		return str(self.__html__())


class Constructor:
	def __init__(self, component: type[Component]):
		self.component = component
		self.fields = field_names(component)

	def __call__(self, *arguments: Any, **keywords: Any) -> Component:
		if "attributes" not in self.fields:
			return self.component(*arguments, **keywords)
		inputs = {}
		loose = {}
		for name, value in keywords.items():
			if name in self.fields:
				inputs[name] = value
			else:
				loose[html_name(name)] = value
		if loose and "attributes" in inputs:
			raise TypeError(
				f"{self.component.__name__} takes either attributes= "
				"or attribute keywords, not both"
			)
		if loose:
			inputs["attributes"] = Attributes.from_html_names(loose)
		return self.component(*arguments, **inputs)


def allowed(component: type[Component], name: str) -> bool:
	return (
		name in global_attributes
		or name.startswith("data-")
		or name in component.accepts
	)


def field_names(component: type[Component]) -> list[str]:
	return [field.name for field in fields(component)]
