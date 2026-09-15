from typing import Any, Protocol
import uuid

from helios import http

type RawValue = str | list[str] | None


class ParseError(ValueError):
	pass


class Parser[T](Protocol):
	def parse(self, value: RawValue) -> T: ...


class Scalar:
	def parse(self, value: RawValue) -> Any:
		if isinstance(value, list):
			raise ParseError("must be a single value")
		return value


class Str(Scalar):
	def parse(self, value: RawValue) -> str:
		return super().parse(value)


class UUID(Scalar):
	def parse(self, value: RawValue) -> uuid.UUID:
		raw = super().parse(value)
		try:
			return uuid.UUID(raw)
		except ValueError as err:
			raise ParseError("must be a valid UUID") from err


class URL(Scalar):
	def parse(self, value: RawValue) -> http.URL:
		raw = super().parse(value)
		try:
			return http.URL(raw)
		except ValueError as err:
			raise ParseError("must be a valid URL") from err


class Required[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, value: RawValue) -> T:
		if value is None:
			raise ParseError("must be provided")
		if value == "" or value == []:
			raise ParseError("must not be empty")
		return self.parser.parse(value)


class Optional[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, value: RawValue) -> T | None:
		if value is None or value == "":
			return None
		return self.parser.parse(value)


class Bool:
	def parse(self, value: RawValue) -> bool:
		if value is None:
			return False
		if value == "on":
			return True
		raise ParseError('must be "on" or omitted')


class List[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, value: RawValue) -> list[T]:
		if value is None:
			return []
		if isinstance(value, str):
			values = [value]
		else:
			values = value
		return [self.parser.parse(item) for item in values]
