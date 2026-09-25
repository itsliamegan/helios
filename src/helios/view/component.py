from annotationlib import get_annotations
from contextvars import ContextVar
from typing import Any, ClassVar, TYPE_CHECKING, dataclass_transform

from markupsafe import Markup

from helios.declarative import (
	Declaration,
	MISSING,
	check_init_keywords,
	check_single_base,
	declarations,
)

from .attributes import Attributes, html_name
from .error import ComponentError

if TYPE_CHECKING:
	from .engine import Engine

rendering: ContextVar[Engine] = ContextVar("rendering")


@dataclass_transform(kw_only_default=True, eq_default=False)
class Component:
	template: ClassVar[str]
	accepts: ClassVar[set[str]] = set()
	props: ClassVar[dict[str, Declaration[object]]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Component, ComponentError)
		cls.props = {
			declaration.name: declaration
			for declaration in declarations(cls, prop_type, ComponentError)
		}
		check_declaration(cls)

	@classmethod
	def accepts_attribute(cls, name: str) -> bool:
		return Attributes.is_global(name) or name in cls.accepts

	def __init__(self, **keywords: Any):
		component = type(self)
		for declaration in component.props.values():
			declaration.resolve()
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
			[
				name
				for name, declaration in component.props.items()
				if declaration.default is MISSING
			],
		)

		for name, declaration in component.props.items():
			setattr(self, name, props.get(name, declaration.default))

		if "attributes" in component.props:
			for name in sorted(vars(self)["attributes"].names()):
				if not component.accepts_attribute(name):
					raise TypeError(
						f'{component.__name__} does not accept the attribute "{name}"'
					)

	def __html__(self) -> Markup:
		engine = rendering.get(None)
		if engine is None:
			raise RuntimeError(f"{type(self).__name__} was rendered outside a view")
		values = {}
		for name in type(self).props:
			values[name] = getattr(self, name)
		values["component"] = self
		return Markup(engine.render(self.template, values))

	def __str__(self) -> str:
		return str(self.__html__())

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={getattr(self, name)!r}" for name in type(self).props
		)
		return f"{type(self).__name__}({values})"


def prop_type(declaration: Declaration[object]) -> object:
	return declaration.annotation


def check_declaration(component: type[Component]):
	name = component.__name__
	for prop_name, declaration in component.props.items():
		if prop_name == "component":
			raise ComponentError(f'Component {name} has a prop named "component"')
		if prop_name in vars(Component) or prop_name in get_annotations(Component):
			raise ComponentError(
				f'Component {name} has a prop named "{prop_name}", which Component uses'
			)
		default = declaration.default
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
