from datetime import datetime
from typing import Any, ClassVar, Literal, cast, overload
from uuid import UUID, uuid4

from helios.http import URL

from . import types


class ModelError(RuntimeError):
	pass


MISSING: Any = object()


class Attribute[StoredT, ValueT = StoredT]:
	def __init__(
		self,
		typ: types.Type[StoredT],
		*,
		default: ValueT,
		nullable: bool,
		init: bool,
	):
		self.name: str | None = None
		self.owner: type[Model] | None = None
		self.type = typ
		self.default = None if default is MISSING else default
		self.required = default is MISSING
		self.nullable = nullable
		self.init = init

	def __set_name__(self, owner: type[Model], name: str):
		self.owner = owner
		self.name = name

	@overload
	def __get__(
		self, instance: None, owner: type[Model]
	) -> Attribute[StoredT, ValueT]: ...

	@overload
	def __get__(self, instance: Model, owner: type[Model]) -> ValueT: ...

	def __get__(
		self, instance: Model | None, owner: type[Model]
	) -> Attribute[StoredT, ValueT] | ValueT:
		if instance is None:
			return self
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		try:
			return instance.values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def check(self, value: object, model_type: type):
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		if value is None:
			if self.nullable:
				return
			raise ModelError(f"{model_type.__name__}.{self.name}: cannot be null")
		try:
			self.type.check(value)
		except (TypeError, ValueError) as error:
			raise ModelError(f"{model_type.__name__}.{self.name}: {error}") from error

	def __set__(self, instance: Model, value: ValueT):
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		self.check(value, type(instance))
		instance.values[self.name] = value
		if instance.tracking:
			instance.dirty_names.add(self.name)
			instance.change_counts[self.name] = (
				instance.change_counts.get(self.name, 0) + 1
			)

	def __repr__(self) -> str:
		return f"Attribute({self.name!r}, {self.type!r}, default={self.default!r}, nullable={self.nullable!r})"


@overload
def attr[T](
	typ: type[T] | types.Type[T],
	*,
	default: T = MISSING,
	nullable: Literal[False] = False,
	init: bool = True,
) -> Attribute[T]: ...


@overload
def attr[T](
	typ: type[T] | types.Type[T],
	*,
	default: T | None = MISSING,
	nullable: Literal[True],
	init: bool = True,
) -> Attribute[T, T | None]: ...


def attr(
	typ: type[Any] | types.Type[Any],
	*,
	default: Any = MISSING,
	nullable: bool = False,
	init: bool = True,
) -> Attribute[Any, Any]:
	return Attribute(
		resolve_type(typ),
		default=default,
		nullable=nullable,
		init=init,
	)


def resolve_type[T](typ: type[T] | types.Type[T]) -> types.Type[T]:
	if typ is str:
		return cast(types.Type[T], types.Str())
	if typ is bool:
		return cast(types.Type[T], types.Bool())
	if typ is int:
		return cast(types.Type[T], types.Int())
	if typ is UUID:
		return cast(types.Type[T], types.UUID())
	if typ is datetime:
		return cast(types.Type[T], types.Date())
	if typ is URL:
		return cast(types.Type[T], types.URL())
	if isinstance(typ, types.Type):
		return typ
	raise TypeError(f"unsupported attribute type: {typ!r}")


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
		self.dirty_names: set[str] = set()
		self.change_counts: dict[str, int] = {}
		self.state: Literal["new", "persisted", "deleted"] = "new"
		self.tracking = True

	@classmethod
	def hydrate(cls, values: dict[str, Any]) -> Model:
		model = cls.__new__(cls)
		model.values = dict(values)
		model.dirty_names = set()
		model.change_counts = {}
		model.state = "persisted"
		model.tracking = True
		return model

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
