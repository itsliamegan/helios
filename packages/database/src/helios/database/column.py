from typing import Any, TYPE_CHECKING

from luna.declarative import Declaration, DeclarationError, MISSING, split_nullable

from .codec import Codec, Scalar, encode
from .error import ModelError

if TYPE_CHECKING:
	from .model import Model


def generated(init: bool = False) -> Any:
	"""Declare a column whose value is generated, such as `id`.

	The column is not a constructor parameter unless `init` is true.
	"""

	return Column(init)


class Column:
	"""One column of a model, stored through the codec its annotation chooses.

	`X | None` makes the column nullable. The annotation resolves on first use.
	"""

	name: str
	declaration: Declaration
	_annotation: type[Any]
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
			if codec is None or not isinstance(annotation, type):
				raise DeclarationError(
					self.name,
					f"unsupported column type: {annotation!r}",
				)
		except DeclarationError as error:
			raise self.declaration.reject(error) from error
		self._annotation = annotation
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
	def annotation(self) -> type[Any]:
		"""Return the column's type, without `| None`."""

		self.resolve()
		return self._annotation

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

		expected = self.annotation
		if not isinstance(value, expected):
			raise TypeError(f"expected {expected.__name__}, got {type(value).__name__}")
		elif isinstance(value, bool) and expected is int:
			# `bool` subclasses `int`, but a boolean is not an integer.
			raise TypeError("expected int, got bool")

	def encode(self, value: object, model_type: type) -> Scalar | None:
		try:
			self.check(value)
			if value is None:
				return None
			else:
				return encode(self.codec, value)
		except (TypeError, ValueError) as error:
			raise ModelError(f"{model_type.__name__}.{self.name}: {error}") from error

	def decode(self, raw: Scalar | None) -> object:
		value = None if raw is None else self.codec.decode(raw)
		self.check(value)
		return value

	def __set__(self, instance: Model, value: object):
		raise AttributeError(
			f"{type(instance).__name__}.{self.name} is read-only; use store.update"
		)
