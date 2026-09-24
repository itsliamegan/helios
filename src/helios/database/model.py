from annotationlib import get_annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, ClassVar, dataclass_transform, get_origin
from uuid import UUID, uuid4

from .attribute import Attribute, Declaration, MISSING, attribute, declare
from .error import ModelError


class Status(Enum):
	NEW = auto()
	PERSISTED = auto()
	DELETED = auto()


@dataclass
class Changes:
	revisions: dict[str, int]

	def __init__(self):
		self.revisions = {}

	def mark(self, name: str):
		self.revisions[name] = self.revisions.get(name, 0) + 1

	def snapshot(self) -> dict[str, int]:
		return dict(self.revisions)

	def accept(self, snapshot: dict[str, int]):
		for name, revision in snapshot.items():
			if self.revisions.get(name) == revision:
				del self.revisions[name]


class ModelMeta(type):
	attributes: dict[str, Attribute]

	def __new__(
		metaclass,
		name: str,
		bases: tuple[type, ...],
		namespace: dict[str, Any],
	):
		if bases and "attributes" in namespace:
			raise ModelError(
				f"{name}.attributes is model metadata; declare named attributes instead"
			)

		model_bases = [base for base in bases if isinstance(base, ModelMeta)]
		if len(model_bases) > 1:
			raise ModelError(f"{name} cannot inherit from multiple model classes")

		model_type = super().__new__(metaclass, name, bases, namespace)
		attributes = dict(model_bases[0].attributes) if model_bases else {}
		declared = declare_attributes(model_type)
		for attribute_name, value in namespace.items():
			if isinstance(value, Declaration) and attribute_name not in declared:
				raise ModelError(f"'{name}.{attribute_name}' has no annotation")
			if attribute_name in attributes and attribute_name not in declared:
				raise ModelError(
					f"'{name}.{attribute_name}' replaces an inherited attribute "
					"without an annotation"
				)
		for attribute_name, declared_attribute in declared.items():
			if attribute_name in attributes and not attributes[attribute_name].init:
				raise ModelError(f"'{name}.{attribute_name}' is a reserved attribute")
			declared_attribute.__set_name__(model_type, attribute_name)
			setattr(model_type, attribute_name, declared_attribute)
			attributes[attribute_name] = declared_attribute

		model_type.attributes = attributes
		return model_type


def declare_attributes(model_type: type) -> dict[str, Attribute]:
	try:
		annotations = get_annotations(model_type, eval_str=True)
	except NameError as error:
		raise ModelError(
			f"{model_type.__name__} has an unresolved annotation: {error}"
		) from error

	declared = {}
	for name, annotation in annotations.items():
		if annotation is ClassVar or get_origin(annotation) is ClassVar:
			continue
		try:
			declared[name] = declare(annotation, vars(model_type).get(name, MISSING))
		except TypeError as error:
			raise ModelError(f"{model_type.__name__}.{name}: {error}") from error
	return declared


@dataclass_transform(
	kw_only_default=True,
	eq_default=False,
	field_specifiers=(attribute,),
)
class Model(metaclass=ModelMeta):
	table: ClassVar[str] = ""
	attributes: ClassVar[dict[str, Attribute]]

	id: UUID = attribute(init=False)
	created_at: datetime | None = attribute(init=False)

	def __init__(self, **attributes: Any):
		self.values = type(self).initialize(attributes)
		self.values["id"] = uuid4()
		self.values["created_at"] = None
		self._changes = Changes()
		self._status = Status.NEW

	@classmethod
	def hydrate(cls, values: dict[str, Any]) -> Model:
		model = cls.__new__(cls)
		model.values = dict(values)
		model._changes = Changes()
		model._status = Status.PERSISTED
		return model

	@classmethod
	def attribute(cls, name: str) -> Attribute:
		try:
			return cls.attributes[name]
		except KeyError:
			raise ModelError(f"{cls.__name__} has no attribute {name!r}") from None

	@classmethod
	def initialize(cls, raw_attributes: dict[str, Any]) -> dict[str, Any]:
		for name in raw_attributes:
			attribute = cls.attributes.get(name)
			if attribute is None or not attribute.init:
				raise ModelError(f"extra attribute '{name}'")

		values = {}
		for name, attribute in cls.attributes.items():
			if not attribute.init:
				continue
			if name in raw_attributes:
				value = raw_attributes[name]
			elif not attribute.required:
				value = attribute.default
			else:
				raise ModelError(f"missing attribute '{name}'")
			attribute.check(value, cls)
			values[name] = value
		return values

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"
