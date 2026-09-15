from datetime import datetime
from typing import Protocol, runtime_checkable
import uuid

from helios import http
from helios.persist.files import JSONValue


@runtime_checkable
class Type[T](Protocol):
	def check(self, value: object, /): ...
	def encode(self, value: T, /) -> JSONValue: ...
	def decode(self, value: JSONValue, /) -> T: ...


class Str:
	def check(self, value: object):
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")

	def encode(self, value: str) -> JSONValue:
		self.check(value)
		return value

	def decode(self, value: JSONValue) -> str:
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")
		return value


class Bool:
	def check(self, value: object):
		if not isinstance(value, bool):
			raise TypeError(f"expected a boolean, got {type(value).__name__}")

	def encode(self, value: bool) -> JSONValue:
		self.check(value)
		return value

	def decode(self, value: JSONValue) -> bool:
		if not isinstance(value, bool):
			raise TypeError(f"expected a boolean, got {type(value).__name__}")
		return value


class Int:
	def check(self, value: object):
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")

	def encode(self, value: int) -> JSONValue:
		self.check(value)
		return value

	def decode(self, value: JSONValue) -> int:
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")
		return value


class UUID:
	def check(self, value: object):
		if not isinstance(value, uuid.UUID):
			raise TypeError(f"expected a UUID, got {type(value).__name__}")

	def encode(self, value: uuid.UUID) -> JSONValue:
		self.check(value)
		return str(value)

	def decode(self, value: JSONValue) -> uuid.UUID:
		if not isinstance(value, str):
			raise TypeError(f"expected a UUID string, got {type(value).__name__}")
		return uuid.UUID(value)


class Date:
	def check(self, value: object):
		if (
			not isinstance(value, datetime)
			or value.tzinfo is None
			or value.utcoffset() is None
		):
			raise TypeError(f"expected an aware datetime, got {type(value).__name__}")

	def encode(self, value: datetime) -> JSONValue:
		self.check(value)
		return value.isoformat()

	def decode(self, value: JSONValue) -> datetime:
		if not isinstance(value, str):
			raise TypeError(f"expected a datetime string, got {type(value).__name__}")
		decoded = datetime.fromisoformat(value)
		if decoded.tzinfo is None or decoded.utcoffset() is None:
			raise ValueError("expected an aware datetime")
		return decoded


class URL:
	def check(self, value: object):
		if not isinstance(value, http.URL):
			raise TypeError(f"expected a URL, got {type(value).__name__}")

	def encode(self, value: http.URL) -> JSONValue:
		self.check(value)
		return str(value)

	def decode(self, value: JSONValue) -> http.URL:
		if not isinstance(value, str):
			raise TypeError(f"expected a URL string, got {type(value).__name__}")
		return http.URL(value)
