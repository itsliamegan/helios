from datetime import datetime
from typing import Protocol, runtime_checkable
import uuid

from helios.persist.files import JSONValue


@runtime_checkable
class Type[T](Protocol):
	def check(self, val: object, /): ...
	def encode(self, val: T, /) -> JSONValue: ...
	def decode(self, val: JSONValue, /) -> T: ...


class Str:
	def check(self, val: object):
		if not isinstance(val, str):
			raise TypeError(f"expected a string, got {type(val).__name__}")

	def encode(self, val: str) -> JSONValue:
		self.check(val)
		return val

	def decode(self, val: JSONValue) -> str:
		if not isinstance(val, str):
			raise TypeError(f"expected a string, got {type(val).__name__}")
		return val


class Bool:
	def check(self, val: object):
		if not isinstance(val, bool):
			raise TypeError(f"expected a boolean, got {type(val).__name__}")

	def encode(self, val: bool) -> JSONValue:
		self.check(val)
		return val

	def decode(self, val: JSONValue) -> bool:
		if not isinstance(val, bool):
			raise TypeError(f"expected a boolean, got {type(val).__name__}")
		return val


class Int:
	def check(self, val: object):
		if not isinstance(val, int) or isinstance(val, bool):
			raise TypeError(f"expected an integer, got {type(val).__name__}")

	def encode(self, val: int) -> JSONValue:
		self.check(val)
		return val

	def decode(self, val: JSONValue) -> int:
		if not isinstance(val, int) or isinstance(val, bool):
			raise TypeError(f"expected an integer, got {type(val).__name__}")
		return val


class UUID:
	def check(self, val: object):
		if not isinstance(val, uuid.UUID):
			raise TypeError(f"expected a UUID, got {type(val).__name__}")

	def encode(self, val: uuid.UUID) -> JSONValue:
		self.check(val)
		return str(val)

	def decode(self, val: JSONValue) -> uuid.UUID:
		if not isinstance(val, str):
			raise TypeError(f"expected a UUID string, got {type(val).__name__}")
		return uuid.UUID(val)


class Date:
	def check(self, val: object):
		if (
			not isinstance(val, datetime)
			or val.tzinfo is None
			or val.utcoffset() is None
		):
			raise TypeError(f"expected an aware datetime, got {type(val).__name__}")

	def encode(self, val: datetime) -> JSONValue:
		self.check(val)
		return val.isoformat()

	def decode(self, val: JSONValue) -> datetime:
		if not isinstance(val, str):
			raise TypeError(f"expected a datetime string, got {type(val).__name__}")
		decoded = datetime.fromisoformat(val)
		if decoded.tzinfo is None or decoded.utcoffset() is None:
			raise ValueError("expected an aware datetime")
		return decoded
