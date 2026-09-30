from annotationlib import Format, get_annotations
from datetime import datetime
from typing import Any, ClassVar, dataclass_transform
from uuid import UUID, uuid4

from helios.declarative import check_init_keywords, check_single_base, declarations

from .attribute import Attribute, declare, generated
from .error import ModelError


class ResolvedAttributes:
	def __get__(self, instance: object, owner: type[Model]) -> dict[str, Attribute]:
		for declared_attribute in owner._attributes.values():
			declared_attribute.declaration.resolve()
		return owner._attributes


@dataclass_transform(
	kw_only_default=True,
	eq_default=False,
	field_specifiers=(generated,),
)
class Model:
	table: ClassVar[str] = ""
	_attributes: ClassVar[dict[str, Attribute]] = {}
	attributes = ResolvedAttributes()

	id: UUID = generated()
	created_at: datetime = generated()

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Model, ModelError)
		annotations = get_annotations(cls, format=Format.FORWARDREF)
		for name in METADATA:
			if name in vars(cls) or name in annotations:
				raise ModelError(f"{cls.__name__}.{name} is model metadata")
		declare_attributes(cls, dict(Model._attributes))

	def __init__(self, **attributes: Any):
		self._values = type(self).initialize(attributes)
		self._values["id"] = uuid4()

	@classmethod
	def hydrate(cls, values: dict[str, Any]) -> Model:
		model = cls.__new__(cls)
		model._values = {name: values[name] for name in cls.attributes}
		return model

	@classmethod
	def attribute(cls, name: str) -> Attribute:
		try:
			return cls.attributes[name]
		except KeyError:
			raise ModelError(f"{cls.__name__} has no attribute {name!r}") from None

	@classmethod
	def initialize(cls, raw_attributes: dict[str, Any]) -> dict[str, Any]:
		initialized = {
			name: definition
			for name, definition in cls.attributes.items()
			if definition.init
		}
		check_init_keywords(
			cls,
			"attributes",
			raw_attributes,
			initialized,
			[name for name, definition in initialized.items() if definition.required],
		)

		values = {}
		for name, definition in initialized.items():
			value = raw_attributes.get(name, definition.default)
			try:
				definition.check(value)
			except (TypeError, ValueError) as error:
				raise ModelError(f"{cls.__name__}.{name}: {error}") from error
			values[name] = value
		return values

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"


def declare_attributes(model_type: type[Model], attributes: dict[str, Attribute]):
	name = model_type.__name__
	own_attributes = {}
	for declaration in declarations(model_type, declare, ModelError):
		default = declaration.default
		declared_attribute = default if isinstance(default, Attribute) else Attribute()
		declared_attribute.bind(declaration)
		own_attributes[declaration.name] = declared_attribute

	for attribute_name, value in vars(model_type).items():
		if isinstance(value, Attribute) and attribute_name not in own_attributes:
			raise ModelError(f"'{name}.{attribute_name}' has no annotation")

	for attribute_name in [*vars(model_type), *own_attributes]:
		if attribute_name in attributes:
			raise ModelError(f"'{name}.{attribute_name}' is a reserved attribute")

	for attribute_name, declared_attribute in own_attributes.items():
		setattr(model_type, attribute_name, declared_attribute)
		attributes[attribute_name] = declared_attribute
	model_type._attributes = attributes


METADATA = {"attributes"}

declare_attributes(Model, {})
