from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.declaration import Declaration, DeclarationError, MISSING, split_nullable

from .codec import Codec, Scalar, encode, for_type
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model


@dataclass
class Column:
	codec: Codec[object]
	nullable: bool


class Attribute:
	name: str
	declaration: Declaration[Column]

	def __init__(self, init: bool = True):
		self.init = init

	def bind(self, declaration: Declaration[Column]):
		self.name = declaration.name
		self.declaration = declaration

	@property
	def default(self) -> object:
		if self.declaration.default is self:
			return MISSING
		else:
			return self.declaration.default

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def codec(self) -> Codec[object]:
		return self.declaration.resolve().codec

	@property
	def nullable(self) -> bool:
		return self.declaration.resolve().nullable

	def __get__(self, instance: Model | None, owner: type) -> object:
		if instance is None:
			return self
		try:
			return instance.values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def check(self, value: object, model_type: type):
		if value is None:
			if self.nullable:
				return
			raise ModelError(f"{model_type.__name__}.{self.name}: cannot be null")
		try:
			self.codec.check(value)
		except (TypeError, ValueError) as error:
			raise ModelError(f"{model_type.__name__}.{self.name}: {error}") from error

	def encode(self, value: object, model_type: type) -> Scalar | None:
		self.check(value, model_type)
		if value is None:
			return None
		return encode(self.codec, value)

	def decode(self, raw: Scalar | None, model_type: type) -> object:
		value = None if raw is None else self.codec.decode(raw)
		self.check(value, model_type)
		return value

	def __set__(self, instance: Model, value: object):
		self.check(value, type(instance))
		instance.values[self.name] = value
		instance._changes.mark(self.name)


def generated(init: bool = False) -> Any:
	return Attribute(init)


def declare(declaration: Declaration[Column]) -> Column:
	value_type, nullable = split_nullable(declaration.name, declaration.annotation)
	codec = for_type(value_type)
	if codec is None:
		raise DeclarationError(
			declaration.name,
			f"unsupported attribute type: {value_type!r}",
		)
	return Column(codec, nullable)
