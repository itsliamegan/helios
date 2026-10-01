from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.declarative import Declaration, DeclarationError, MISSING, split_nullable

from .codec import Codec, Scalar, encode
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model


@dataclass
class Encoding:
	codec: Codec[object]
	nullable: bool


class Column:
	name: str
	declaration: Declaration[object]

	def __init__(self, init: bool = True):
		self.init = init

	def bind(self, declaration: Declaration[object]):
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
	def encoding(self) -> Encoding:
		encoding = self.declaration.resolve()
		assert isinstance(encoding, Encoding)
		return encoding

	@property
	def codec(self) -> Codec[object]:
		return self.encoding.codec

	@property
	def nullable(self) -> bool:
		return self.encoding.nullable

	def __get__(self, instance: Model | None, owner: type) -> object:
		if instance is None:
			return self
		try:
			return instance._values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def check(self, value: object):
		if value is None:
			if self.nullable:
				return
			else:
				raise ValueError("cannot be null")
		self.codec.check(value)

	def encode(self, value: object, model_type: type) -> Scalar | None:
		try:
			self.check(value)
		except (TypeError, ValueError) as error:
			raise ModelError(f"{model_type.__name__}.{self.name}: {error}") from error
		if value is None:
			return None
		return encode(self.codec, value)

	def decode(self, raw: Scalar | None) -> object:
		value = None if raw is None else self.codec.decode(raw)
		self.check(value)
		return value

	def __set__(self, instance: Model, value: object):
		raise AttributeError(
			f"{type(instance).__name__}.{self.name} is read-only; use store.update"
		)


def generated(init: bool = False) -> Any:
	return Column(init)


def declare(declaration: Declaration[object]) -> Encoding:
	annotation, nullable = split_nullable(declaration.name, declaration.annotation)
	codec = Codec.for_type(annotation)
	if codec is None:
		raise DeclarationError(
			declaration.name,
			f"unsupported column type: {annotation!r}",
		)
	return Encoding(codec, nullable)
