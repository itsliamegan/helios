from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TYPE_CHECKING, cast, overload
from uuid import UUID

from helios.http import URL

from . import types
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model

MISSING: Any = object()


@dataclass
class Attribute[StoredT, ValueT = StoredT]:
	name: str | None
	owner: type[Model] | None
	type: types.Type[StoredT]
	default: ValueT | None
	required: bool
	nullable: bool
	init: bool

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

	def encode(self, value: object, model_type: type) -> types.Scalar | None:
		self.check(value, model_type)
		if value is None:
			return None
		return types.encode(self.type, value)

	def decode(self, raw: types.Scalar | None, model_type: type) -> StoredT | None:
		value = None if raw is None else self.type.decode(raw)
		self.check(value, model_type)
		return value

	def __set__(self, instance: Model, value: ValueT):
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		self.check(value, type(instance))
		instance.values[self.name] = value
		instance._changes.mark(self.name)


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
