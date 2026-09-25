from dataclasses import dataclass
from datetime import datetime
from typing import Any, TYPE_CHECKING, cast
from uuid import UUID

from helios.declaration import DeclarationError, Declared, MISSING, split_nullable
from helios.http import URL

from . import types
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model


@dataclass
class Attribute:
	name: str | None
	type: types.Type[object]
	default: object
	required: bool
	nullable: bool
	init: bool

	def __init__(
		self,
		type: types.Type[object],
		default: object,
		nullable: bool,
		init: bool,
	):
		self.name = None
		self.type = type
		self.default = None if default is MISSING else default
		self.required = default is MISSING
		self.nullable = nullable
		self.init = init

	def __set_name__(self, _owner: type, name: str):
		self.name = name

	def __get__(self, instance: Model | None, owner: type) -> object:
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

	def decode(self, raw: types.Scalar | None, model_type: type) -> object:
		value = None if raw is None else self.type.decode(raw)
		self.check(value, model_type)
		return value

	def __set__(self, instance: Model, value: object):
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		self.check(value, type(instance))
		instance.values[self.name] = value
		instance._changes.mark(self.name)


@dataclass(init=False)
class Declaration:
	default: object
	init: bool
	type: types.Type[object] | None

	def __init__(
		self,
		default: object,
		init: bool,
		type: types.Type[object] | None,
	):
		self.default = default
		self.init = init
		self.type = type


def attribute(
	default: object = MISSING,
	init: bool = True,
	type: types.Type[object] | None = None,
) -> Any:
	return Declaration(default, init, type)


def declare(entry: Declared) -> Attribute:
	if isinstance(entry.default, Declaration):
		declaration = entry.default
	else:
		declaration = Declaration(entry.default, True, None)
	value_type, nullable = split_nullable(entry.name, entry.annotation)
	if declaration.type is None:
		codec = resolve_type(entry.name, value_type)
	else:
		codec = declaration.type
	return Attribute(
		codec,
		declaration.default,
		nullable,
		declaration.init,
	)


def resolve_type[T](name: str, typ: type[T] | types.Type[T]) -> types.Type[T]:
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
	raise DeclarationError(name, f"unsupported attribute type: {typ!r}")
