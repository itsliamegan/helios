from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
import uuid

from helios import http

type Scalar = int | float | str | bytes


@runtime_checkable
class Type[T](Protocol):
	def check(self, value: object): ...
	def encode(self, value: T) -> Scalar: ...
	def decode(self, value: Scalar) -> T: ...


def check_scalar(value: object) -> Scalar:
	if isinstance(value, bool) or not isinstance(value, int | float | str | bytes):
		raise TypeError(f"expected a SQLite scalar, got {type(value).__name__}")
	return value


def encode[T](codec: Type[T], value: T) -> Scalar:
	return check_scalar(codec.encode(value))


class Str:
	def check(self, value: object):
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")

	def encode(self, value: str) -> Scalar:
		self.check(value)
		return check_scalar(value)

	def decode(self, value: Scalar) -> str:
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")
		return value


class Bool:
	def check(self, value: object):
		if not isinstance(value, bool):
			raise TypeError(f"expected a boolean, got {type(value).__name__}")

	def encode(self, value: bool) -> Scalar:
		self.check(value)
		return 1 if value else 0

	def decode(self, value: Scalar) -> bool:
		if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
			raise TypeError("expected the integer 0 or 1")
		return bool(value)


class Int:
	def check(self, value: object):
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")

	def encode(self, value: int) -> Scalar:
		self.check(value)
		return check_scalar(value)

	def decode(self, value: Scalar) -> int:
		if not isinstance(value, int) or isinstance(value, bool):
			raise TypeError(f"expected an integer, got {type(value).__name__}")
		return value


class UUID:
	def check(self, value: object):
		if not isinstance(value, uuid.UUID):
			raise TypeError(f"expected a UUID, got {type(value).__name__}")

	def encode(self, value: uuid.UUID) -> Scalar:
		self.check(value)
		return check_scalar(str(value))

	def decode(self, value: Scalar) -> uuid.UUID:
		if not isinstance(value, str):
			raise TypeError(f"expected a UUID string, got {type(value).__name__}")
		decoded = uuid.UUID(value)
		if str(decoded) != value:
			raise ValueError("expected a canonical UUID string")
		return decoded


class Date:
	format = "%Y-%m-%dT%H:%M:%S.%fZ"

	def check(self, value: object):
		if (
			not isinstance(value, datetime)
			or value.tzinfo is None
			or value.utcoffset() is None
		):
			raise TypeError(f"expected an aware datetime, got {type(value).__name__}")

	def encode(self, value: datetime) -> Scalar:
		self.check(value)
		return check_scalar(value.astimezone(UTC).strftime(self.format))

	def decode(self, value: Scalar) -> datetime:
		if not isinstance(value, str):
			raise TypeError(f"expected a datetime string, got {type(value).__name__}")
		decoded = datetime.strptime(value, self.format).replace(tzinfo=UTC)
		if decoded.strftime(self.format) != value:
			raise ValueError("expected a canonical UTC datetime string")
		return decoded


class URL:
	def check(self, value: object):
		if not isinstance(value, http.URL):
			raise TypeError(f"expected a URL, got {type(value).__name__}")

	def encode(self, value: http.URL) -> Scalar:
		self.check(value)
		return check_scalar(str(value))

	def decode(self, value: Scalar) -> http.URL:
		if not isinstance(value, str):
			raise TypeError(f"expected a URL string, got {type(value).__name__}")
		return http.URL(value)
