from collections.abc import Iterator, Mapping
from typing import Any, TYPE_CHECKING

from helios.declarative import Declaration, DeclarationError, MISSING, split_nullable

from .codec import Codec, Scalar, encode
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model


class Column:
	name: str
	declaration: Declaration
	_codec: Codec[object]
	_nullable: bool

	def __init__(self, init: bool = True):
		self.init = init
		self.resolved = False

	def bind(self, declaration: Declaration):
		self.name = declaration.name
		self.declaration = declaration

	def resolve(self):
		if self.resolved:
			return
		try:
			annotation, nullable = split_nullable(
				self.name,
				self.declaration.resolve(),
			)
			codec = Codec.for_type(annotation)
			if codec is None:
				raise DeclarationError(
					self.name,
					f"unsupported column type: {annotation!r}",
				)
		except DeclarationError as error:
			raise self.declaration.reject(error) from error
		self._codec = codec
		self._nullable = nullable
		self.resolved = True

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
		self.resolve()
		return self._codec

	@property
	def nullable(self) -> bool:
		self.resolve()
		return self._nullable

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


class Columns(Mapping[str, Column]):
	def __init__(self, declared: dict[str, Column]):
		self.declared = declared

	def __getitem__(self, name: str) -> Column:
		column = self.declared[name]
		column.resolve()
		return column

	def __contains__(self, name: object) -> bool:
		return name in self.declared

	def __iter__(self) -> Iterator[str]:
		return iter(self.declared)

	def __len__(self) -> int:
		return len(self.declared)


def generated(init: bool = False) -> Any:
	return Column(init)
