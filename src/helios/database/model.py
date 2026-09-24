from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, ClassVar, cast
from uuid import UUID, uuid4

from .attribute import Attribute, attr
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
	attrs: dict[str, Attribute[Any, Any]]

	def __new__(
		metaclass,
		name: str,
		bases: tuple[type, ...],
		namespace: dict[str, Any],
	):
		if bases and "attrs" in namespace:
			raise ModelError(
				f"{name}.attrs is model metadata; declare named attributes instead"
			)

		model_bases = [base for base in bases if isinstance(base, ModelMeta)]
		if len(model_bases) > 1:
			raise ModelError(f"{name} cannot inherit from multiple model classes")

		attrs = dict(model_bases[0].attrs) if model_bases else {}
		for attr_name, value in namespace.items():
			if attr_name in attrs:
				if not attrs[attr_name].init:
					raise ModelError(f"'{name}.{attr_name}' is a reserved attr")
				if not isinstance(value, Attribute):
					raise ModelError(
						f"'{name}.{attr_name}' replaces an inherited attr with a non-Attribute"
					)
			if isinstance(value, Attribute):
				attrs[attr_name] = value

		model_type = super().__new__(metaclass, name, bases, namespace)
		model_type.attrs = attrs
		return model_type


class Model(metaclass=ModelMeta):
	table: ClassVar[str] = ""
	attrs: ClassVar[dict[str, Attribute[Any, Any]]]

	id = attr(UUID, init=False)
	created_at = cast(Attribute[datetime, datetime | None], attr(datetime, init=False))

	def __init__(self, **attrs: Any):
		self.values = type(self).initialize(attrs)
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
	def attribute(cls, name: str) -> Attribute[Any, Any]:
		try:
			return cls.attrs[name]
		except KeyError:
			raise ModelError(f"{cls.__name__} has no attribute {name!r}") from None

	@classmethod
	def initialize(cls, raw_attrs: dict[str, Any]) -> dict[str, Any]:
		for name in raw_attrs:
			attribute = cls.attrs.get(name)
			if attribute is None or not attribute.init:
				raise ModelError(f"extra attr '{name}'")

		values = {}
		for name, attribute in cls.attrs.items():
			if not attribute.init:
				continue
			if name in raw_attrs:
				value = raw_attrs[name]
			elif not attribute.required:
				value = attribute.default
			elif attribute.nullable:
				value = None
			else:
				raise ModelError(f"missing attr '{name}'")
			attribute.check(value, cls)
			values[name] = value
		return values

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"
