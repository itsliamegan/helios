from abc import ABC, abstractmethod
from datetime import UTC, datetime
import json
from typing import Any, ClassVar, TypeAliasType
import uuid

from helios import url

type Scalar = int | float | str | bytes

type JSON[T] = T


class Codec[T](ABC):
	"""Converts one column's values between Python and SQLite.

	A codec converts the values of any attribute annotated with the type named
	by `converts`. It matches this type exactly, so a subclass of the specified
	type does not use the codec.

	The model's column checks the type of an attribute before attempting to
	encode it. After this check, a codec may raise a `ValueError` for a value
	that it cannot store.
	"""

	converts: ClassVar[type[Any] | TypeAliasType]

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


class JSONText(Text[Any]):
	"""Encodes a JSON value as JSON text.

	Follows Python's normal lossy rules of round-tripping values through JSON,
	e.g. a tuple comes back as a list.
	"""

	converts = JSON

	def encode(self, value: Any) -> Scalar:
		try:
			return json.dumps(value)
		except TypeError as error:
			raise ValueError(str(error)) from error

	def decode(self, value: Scalar) -> Any:
		return json.loads(self.text(value))


CODECS: list[Codec[Any]] = [Str(), Bool(), Int(), UUID(), Date(), URL(), JSONText()]
