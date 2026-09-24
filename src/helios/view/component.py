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
	fields: ClassVar[dict[str, Any]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		fields = dict(cls.fields)
		for name, annotation in get_annotations(cls, format=Format.FORWARDREF).items():
			if not is_class_variable(annotation):
				fields[name] = vars(cls).get(name, MISSING)
		cls.fields = fields
		check_component(cls)

	@classmethod
	def accepts_attribute(cls, name: str) -> bool:
		return Attributes.is_global(name) or name in cls.accepts

	def __init__(self, **keywords: Any):
		component = type(self)
		values = {}
		loose = {}
		for name, value in keywords.items():
			if name in component.fields:
				values[name] = value
			else:
				loose[name] = value

		if loose:
			if "attributes" not in component.fields:
				raise TypeError(
					f"{component.__name__} got unexpected keywords: {", ".join(loose)}"
				)
			if "attributes" in values:
				raise TypeError(
					f"{component.__name__} takes either attributes= "
					"or attribute keywords, not both"
				)
			values["attributes"] = Attributes.from_html_names(
				{html_name(name): value for name, value in loose.items()}
			)

		missing = [
			name
			for name, default in component.fields.items()
			if name not in values and default is MISSING
		]
		if missing:
			raise TypeError(
				f"{component.__name__} is missing fields: {", ".join(missing)}"
			)

		for name, default in component.fields.items():
			setattr(self, name, values.get(name, default))

		if "attributes" in component.fields:
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
		for name in type(self).fields:
			values[name] = getattr(self, name)
		values["component"] = self
		return Markup(engine.render(self.template, values))

	def __str__(self) -> str:
		return str(self.__html__())

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={getattr(self, name)!r}" for name in type(self).fields
		)
		return f"{type(self).__name__}({values})"


def is_class_variable(annotation: Any) -> bool:
	return annotation is ClassVar or get_origin(annotation) is ClassVar


def check_component(component: type[Component]):
	name = component.__name__
	for field_name, default in component.fields.items():
		if field_name == "component":
			raise ValueError(f'Component {name} has a field named "component"')
		if field_name in vars(Component) or field_name in get_annotations(Component):
			raise ValueError(
				f'Component {name} has a field named "{field_name}", '
				"which Component uses"
			)
		if default is not MISSING and default.__hash__ is None:
			raise ValueError(
				f'Component {name} has a mutable default for "{field_name}"'
			)
		if html_name(field_name) in component.accepts:
			raise ValueError(
				f'Component {name} accepts "{html_name(field_name)}", '
				"which is also a field"
			)
	if component.accepts and "attributes" not in component.fields:
		raise ValueError(
			f"Component {name} declares accepts but has no attributes field"
		)
