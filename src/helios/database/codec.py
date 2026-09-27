from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
import uuid

from helios import http

type Stored = int | float | str | bytes


class Codec[T](ABC):
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
	def check(self, value: object): ...

	@abstractmethod
	def encode(self, value: T) -> Stored: ...

	@abstractmethod
	def decode(self, value: Stored) -> T: ...


def encode[T](codec: Codec[T], value: T) -> Stored:
	encoded = codec.encode(value)
	if isinstance(encoded, bool) or not isinstance(encoded, int | float | str | bytes):
		raise TypeError(
			f"expected a value SQLite can store, got {type(encoded).__name__}"
		)
	return encoded


class Text[T](Codec[T]):
	def text(self, value: Stored) -> str:
		if isinstance(value, str):
			return value
		else:
			raise TypeError(f"expected a string, got {type(value).__name__}")


class Str(Text[str]):
	def check(self, value: object):
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")

	def encode(self, value: str) -> Stored:
		self.check(value)
		return value

	def decode(self, value: Stored) -> str:
		return self.text(value)


class Bool(Codec[bool]):
	def check(self, value: object):
		if not isinstance(value, bool):
			raise TypeError(f"expected a boolean, got {type(value).__name__}")

	def encode(self, value: bool) -> Stored:
		self.check(value)
		return 1 if value else 0

	def decode(self, value: Stored) -> bool:
		if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
			raise TypeError("expected the integer 0 or 1")
		return bool(value)


class Int(Codec[int]):
	def check(self, value: object):
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")

	def encode(self, value: int) -> Stored:
		self.check(value)
		return value

	def decode(self, value: Stored) -> int:
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")
		return value


class UUID(Text[uuid.UUID]):
	def check(self, value: object):
		if not isinstance(value, uuid.UUID):
			raise TypeError(f"expected a UUID, got {type(value).__name__}")

	def encode(self, value: uuid.UUID) -> Stored:
		self.check(value)
		return str(value)

	def decode(self, value: Stored) -> uuid.UUID:
		text = self.text(value)
		decoded = uuid.UUID(text)
		if str(decoded) != text:
			raise ValueError("expected a canonical UUID string")
		return decoded


class Date(Text[datetime]):
	FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

	def check(self, value: object):
		if (
			not isinstance(value, datetime)
			or value.tzinfo is None
			or value.utcoffset() is None
		):
			raise TypeError(f"expected an aware datetime, got {type(value).__name__}")

	def encode(self, value: datetime) -> Stored:
		self.check(value)
		return value.astimezone(UTC).strftime(self.FORMAT)

	def decode(self, value: Stored) -> datetime:
		text = self.text(value)
		decoded = datetime.strptime(text, self.FORMAT).replace(tzinfo=UTC)
		if decoded.strftime(self.FORMAT) != text:
			raise ValueError("expected a canonical UTC datetime string")
		return decoded


class URL(Text[http.URL]):
	def check(self, value: object):
		if not isinstance(value, http.URL):
			raise TypeError(f"expected a URL, got {type(value).__name__}")

	def encode(self, value: http.URL) -> Stored:
		self.check(value)
		return str(value)

	def decode(self, value: Stored) -> http.URL:
		return http.URL(self.text(value))


CODECS: dict[object, Codec[Any]] = {
	str: Str(),
	bool: Bool(),
	int: Int(),
	uuid.UUID: UUID(),
	datetime: Date(),
	http.URL: URL(),
}
