from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, ClassVar, TYPE_CHECKING, dataclass_transform

from markupsafe import Markup

from helios.declarative import (
	MISSING,
	check_init_keywords,
	check_reserved_names,
	check_single_base,
	declarations,
)

from .attributes import Attributes, html_name
from .error import ComponentError
from .prop import Prop
from .view import View

if TYPE_CHECKING:
	from .engine import Engine


@dataclass
class Rendering:
	engine: Engine
	shared: dict[str, Any]


rendering: ContextVar[Rendering] = ContextVar("rendering")


@dataclass_transform(kw_only_default=True, eq_default=False)
class Component:
	template: ClassVar[str]
	accepts: ClassVar[set[str]] = set()
	props: ClassVar[dict[str, Prop]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Component, ComponentError)
		check_reserved_names(cls, Component, METADATA, ComponentError)
		cls.props = {}
		for declaration in declarations(cls, ComponentError):
			cls.props[declaration.name] = Prop(declaration)
		check_declaration(cls)
		for name, prop in cls.props.items():
			setattr(cls, name, prop)

	@classmethod
	def accepts_attribute(cls, name: str) -> bool:
		return Attributes.is_global(name) or name in cls.accepts

	def __init__(self, **keywords: Any):
		component = type(self)
		for prop in component.props.values():
			prop.resolve()
		props = {}
		attributes = {}
		for name, value in keywords.items():
			if name in component.props:
				props[name] = value
			else:
				attributes[name] = value

		if attributes:
			if "attributes" not in component.props:
				raise TypeError(
					f"{component.__name__} got unexpected keywords: "
					f"{", ".join(attributes)}"
				)
			if "attributes" in props:
				raise TypeError(
					f"{component.__name__} takes either attributes= "
					"or attribute keywords, not both"
				)
			props["attributes"] = Attributes.from_html_names(
				{html_name(name): value for name, value in attributes.items()}
			)

		check_init_keywords(
			component,
			"props",
			props,
			component.props,
			[name for name, prop in component.props.items() if prop.required],
		)

		self._values: dict[str, Any] = {}
		for name, prop in component.props.items():
			self._values[name] = props.get(name, prop.default)

		if "attributes" in component.props:
			for name in sorted(self._values["attributes"].names()):
				if not component.accepts_attribute(name):
					raise TypeError(
						f'{component.__name__} does not accept the attribute "{name}"'
					)

	def __html__(self) -> Markup:
		current = rendering.get(None)
		if current is None:
			raise RuntimeError(f"{type(self).__name__} was rendered outside a view")
		assigns = {}
		for name in type(self).props:
			assigns[name] = getattr(self, name)
		assigns["component"] = self
		return Markup(
			current.engine.render(View(self.template, current.shared), assigns)
		)

	def __str__(self) -> str:
		return str(self.__html__())

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={getattr(self, name)!r}" for name in type(self).props
		)
		return f"{type(self).__name__}({values})"


def check_declaration(component: type[Component]):
	name = component.__name__
	for prop_name, prop in component.props.items():
		if prop_name == "component":
			raise ComponentError(f"{name}.component is reserved by Component")
		default = prop.default
		if default is not MISSING and default.__hash__ is None:
			raise ComponentError(
				f'Component {name} has a mutable default for "{prop_name}"'
			)
		if html_name(prop_name) in component.accepts:
			raise ComponentError(
				f'Component {name} accepts "{html_name(prop_name)}", '
				"which is also a prop"
			)
	if component.accepts and "attributes" not in component.props:
		raise ComponentError(
			f"Component {name} declares accepts but has no attributes prop"
		)


METADATA = {"props"}
