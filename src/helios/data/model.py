from datetime import datetime
from typing import Any, ClassVar, Literal, cast, overload
from uuid import UUID, uuid4

from . import types


class ModelError(RuntimeError):
	pass


_MISSING: Any = object()


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
		self.default = None if default is _MISSING else default
		self.required = default is _MISSING
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
			return instance._values[self.name]
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
		except TypeError as error:
			raise ModelError(f"{model_type.__name__}.{self.name}: {error}") from error

	def __set__(self, instance: Model, value: ValueT):
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		self.check(value, type(instance))
		if self.name in instance._values and self.name not in instance._old_values:
			instance._old_values[self.name] = instance._values[self.name]
		instance._values[self.name] = value

	def __repr__(self) -> str:
		return f"Attribute({self.name!r}, {self.type!r}, default={self.default!r}, nullable={self.nullable!r})"


@overload
def attr[T](
	typ: type[T] | types.Type[T],
	*,
	default: T = _MISSING,
	nullable: Literal[False] = False,
	init: bool = True,
) -> Attribute[T]: ...


@overload
def attr[T](
	typ: type[T] | types.Type[T],
	*,
	default: T | None = _MISSING,
	nullable: Literal[True],
	init: bool = True,
) -> Attribute[T, T | None]: ...


def attr(
	typ: type[Any] | types.Type[Any],
	*,
	default: Any = _MISSING,
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
	if isinstance(typ, types.Type):
		return typ
	raise TypeError(f"unsupported attribute type: {typ!r}")


class _ModelMeta(type):
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

		model_bases = [base for base in bases if isinstance(base, _ModelMeta)]
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


class Model(metaclass=_ModelMeta):
	attrs: ClassVar[dict[str, Attribute[Any, Any]]]

	id = attr(UUID, init=False)
	created_at = cast(Attribute[datetime, datetime | None], attr(datetime, init=False))

	def __init__(self, **attrs: Any):
		self._values = type(self)._initialize(attrs)
		self._old_values: dict[str, Any] = {}
		self.id = uuid4()
		self._values["created_at"] = None

	@classmethod
	def _hydrate(cls, values: dict[str, Any]) -> Model:
		model = cls.__new__(cls)
		model._values = dict(values)
		model._old_values = {}
		return model

	@classmethod
	def _initialize(cls, raw_attrs: dict[str, Any]) -> dict[str, Any]:
		for name in raw_attrs:
			attr = cls.attrs.get(name)
			if attr is None or not attr.init:
				raise ModelError(f"extra attr '{name}'")

		values = {}
		for name, attr in cls.attrs.items():
			if not attr.init:
				continue

			if name in raw_attrs:
				value = raw_attrs[name]
			elif not attr.required:
				value = attr.default
			elif attr.nullable:
				value = None
			else:
				raise ModelError(f"missing attr '{name}'")
			attr.check(value, cls)
			values[name] = value
		return values

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"
