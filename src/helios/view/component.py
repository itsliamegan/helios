from annotationlib import Format, get_annotations
from contextvars import ContextVar
from typing import Any, ClassVar, TYPE_CHECKING, dataclass_transform, get_origin

from markupsafe import Markup

from .attributes import Attributes, html_name

if TYPE_CHECKING:
	from .engine import Engine

rendering: ContextVar[Engine] = ContextVar("rendering")

MISSING: Any = object()


@dataclass_transform(kw_only_default=True, eq_default=False)
class Component:
	template: ClassVar[str]
	accepts: ClassVar[set[str]] = set()
	props: ClassVar[dict[str, Any]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		props = dict(cls.props)
		for name, annotation in get_annotations(cls, format=Format.FORWARDREF).items():
			if not is_class_variable(annotation):
				props[name] = vars(cls).get(name, MISSING)
		cls.props = props
		check_component(cls)

	@classmethod
	def accepts_attribute(cls, name: str) -> bool:
		return Attributes.is_global(name) or name in cls.accepts

	def __init__(self, **keywords: Any):
		component = type(self)
		passed_props = {}
		passed_attributes = {}
		for name, value in keywords.items():
			if name in component.props:
				passed_props[name] = value
			else:
				passed_attributes[name] = value

		if passed_attributes:
			if "attributes" not in component.props:
				raise TypeError(
					f"{component.__name__} got unexpected keywords: "
					f"{", ".join(passed_attributes)}"
				)
			if "attributes" in passed_props:
				raise TypeError(
					f"{component.__name__} takes either attributes= "
					"or attribute keywords, not both"
				)
			passed_props["attributes"] = Attributes.from_html_names(
				{html_name(name): value for name, value in passed_attributes.items()}
			)

		missing = [
			name
			for name, default in component.props.items()
			if name not in passed_props and default is MISSING
		]
		if missing:
			raise TypeError(
				f"{component.__name__} is missing props: {", ".join(missing)}"
			)

		for name, default in component.props.items():
			setattr(self, name, passed_props.get(name, default))

		if "attributes" in component.props:
			attributes: Attributes = vars(self)["attributes"]
			for name in sorted(attributes.names()):
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


def is_class_variable(annotation: Any) -> bool:
	return annotation is ClassVar or get_origin(annotation) is ClassVar


def check_component(component: type[Component]):
	name = component.__name__
	for prop_name, default in component.props.items():
		if prop_name == "component":
			raise ValueError(f'Component {name} has a prop named "component"')
		if prop_name in vars(Component) or prop_name in get_annotations(Component):
			raise ValueError(
				f'Component {name} has a prop named "{prop_name}", which Component uses'
			)
		if default is not MISSING and default.__hash__ is None:
			raise ValueError(
				f'Component {name} has a mutable default for "{prop_name}"'
			)
		if html_name(prop_name) in component.accepts:
			raise ValueError(
				f'Component {name} accepts "{html_name(prop_name)}", '
				"which is also a prop"
			)
	if component.accepts and "attributes" not in component.props:
		raise ValueError(
			f"Component {name} declares accepts but has no attributes prop"
		)
