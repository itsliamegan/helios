from contextvars import ContextVar
from dataclasses import Field, fields
from typing import Any, ClassVar, TYPE_CHECKING

from markupsafe import Markup

from .attributes import Attributes, html_name

if TYPE_CHECKING:
	from .engine import Engine

rendering: ContextVar[Engine] = ContextVar("rendering")


class Component:
	__dataclass_fields__: ClassVar[dict[str, Field[Any]]]

	template: ClassVar[str]
	accepts: ClassVar[set[str]] = set()

	@classmethod
	def field_names(cls) -> list[str]:
		return [field.name for field in fields(cls)]

	@classmethod
	def accepts_attribute(cls, name: str) -> bool:
		return Attributes.is_global(name) or name in cls.accepts

	def __post_init__(self):
		if "attributes" not in self.field_names():
			return

		attributes: Attributes = vars(self)["attributes"]
		for name in sorted(attributes.names()):
			if not self.accepts_attribute(name):
				raise TypeError(
					f'{type(self).__name__} does not accept the attribute "{name}"'
				)

	def __html__(self) -> Markup:
		engine = rendering.get(None)
		if engine is None:
			raise RuntimeError(f"{type(self).__name__} was rendered outside a view")
		values = {}
		for name in self.field_names():
			values[name] = getattr(self, name)
		values["component"] = self
		return Markup(engine.render(self.template, values))

	def __str__(self) -> str:
		return str(self.__html__())


class Constructor:
	def __init__(self, component: type[Component]):
		self.component = component
		self.fields = component.field_names()

	def __call__(self, *arguments: Any, **keywords: Any) -> Component:
		if "attributes" not in self.fields:
			return self.component(*arguments, **keywords)

		field_keywords = {}
		attribute_keywords = {}
		for name, value in keywords.items():
			if name in self.fields:
				field_keywords[name] = value
			else:
				attribute_keywords[html_name(name)] = value
		if attribute_keywords and "attributes" in field_keywords:
			raise TypeError(
				f"{self.component.__name__} takes either attributes= "
				"or attribute keywords, not both"
			)
		if attribute_keywords:
			field_keywords["attributes"] = Attributes.from_html_names(
				attribute_keywords
			)
		return self.component(*arguments, **field_keywords)
