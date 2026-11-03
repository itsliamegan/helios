from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar, TypeAliasType
import uuid

from helios import url

type Scalar = int | float | str | bytes


class Codec[T](ABC):
	"""Converts the values of the attributes its `converts` selects.

	A codec converts between Python and SQLite. `converts` selects every attribute whose annotation, without `| None`, has it
	as its outer type: the annotation itself, or its origin when it has one. The
	match is exact, so a subclass of a converted type does not select the codec.

	The column checks a value's outer type before encoding it. A codec raises
	`ValueError` for a value of that type that it cannot store.
	"""

	converts: ClassVar[type[Any] | TypeAliasType]

	@classmethod
	def for_type(cls, annotation: object) -> Codec[Any] | None:
		try:
			found = CODECS.get(annotation)
		except TypeError:
			found = None

		if found is None and isinstance(annotation, type):
			declared = vars(annotation).get("Codec")
			if isinstance(declared, type) and issubclass(declared, Codec):
				return declared()
		return found

	@abstractmethod
	def encode(self, value: T) -> Scalar: ...

	@abstractmethod
	def decode(self, value: Scalar) -> T: ...


def encode[T](codec: Codec[T], value: T) -> Scalar:
	"""Encode a value, refusing a result that SQLite cannot store as a scalar."""

	encoded = codec.encode(value)
	if isinstance(encoded, bool) or not isinstance(encoded, int | float | str | bytes):
		raise TypeError(f"expected a SQLite scalar, got {type(encoded).__name__}")
	return encoded


class Text[T](Codec[T]):
	def text(self, value: Scalar) -> str:
		if isinstance(value, str):
			return value
		else:
			raise TypeError(f"expected a string, got {type(value).__name__}")


class Str(Text[str]):
	converts = str

	def encode(self, value: str) -> Scalar:
		return value

	def decode(self, value: Scalar) -> str:
		return self.text(value)


class Bool(Codec[bool]):
	converts = bool

	def encode(self, value: bool) -> Scalar:
		return 1 if value else 0

	def decode(self, value: Scalar) -> bool:
		if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
			raise TypeError("expected the integer 0 or 1")
		return bool(value)


class Int(Codec[int]):
	converts = int

	def encode(self, value: int) -> Scalar:
		return value

	def decode(self, value: Scalar) -> int:
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")
		return value


class UUID(Text[uuid.UUID]):
	"""Stores a UUID as canonical text, so equal UUIDs compare equal in SQL."""

	converts = uuid.UUID

	def encode(self, value: uuid.UUID) -> Scalar:
		return str(value)

	def decode(self, value: Scalar) -> uuid.UUID:
		text = self.text(value)
		decoded = uuid.UUID(text)
		if str(decoded) != text:
			raise ValueError("expected a canonical UUID string")
		return decoded


class Date(Text[datetime]):
	"""Stores an aware datetime as canonical UTC text, so text order is time order."""

	converts = datetime

	FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

	def encode(self, value: datetime) -> Scalar:
		if value.tzinfo is None or value.utcoffset() is None:
			raise ValueError("expected an aware datetime")

		return value.astimezone(UTC).strftime(self.FORMAT)

	def decode(self, value: Scalar) -> datetime:
		text = self.text(value)
		decoded = datetime.strptime(text, self.FORMAT).replace(tzinfo=UTC)
		if decoded.strftime(self.FORMAT) != text:
			raise ValueError("expected a canonical UTC datetime string")
		return decoded


class URL(Text[url.URL]):
	converts = url.URL

	def encode(self, value: url.URL) -> Scalar:
		return str(value)

	def decode(self, value: Scalar) -> url.URL:
		return url.URL.parse(self.text(value))


CODECS: dict[object, Codec[Any]] = {}
for codec in [Str(), Bool(), Int(), UUID(), Date(), URL()]:
	CODECS[codec.converts] = codec
