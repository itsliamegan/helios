import re
from typing import Any, NewType, Protocol, get_args, get_origin
import uuid

from helios import http

Untrimmed = NewType("Untrimmed", str)

type RawValue = str | list[str]


class ParseError(ValueError):
	def __init__(self, message: str, item: bool = False):
		super().__init__(message)
		self.message = message
		self.item = item


class Parser[T](Protocol):
	def parse(self, value: RawValue) -> T: ...


class Scalar:
	def single(self, value: RawValue) -> str:
		if isinstance(value, list):
			raise ParseError("must be a single value")
		else:
			return value


class Str(Scalar):
	def parse(self, value: RawValue) -> str:
		return self.single(value)


class Int(Scalar):
	def parse(self, value: RawValue) -> int:
		raw = self.single(value).strip()
		if re.fullmatch(r"-?[0-9]+", raw) is None:
			raise ParseError("must be a whole number")
		else:
			return int(raw)


class UUID(Scalar):
	def parse(self, value: RawValue) -> uuid.UUID:
		raw = self.single(value).strip()
		try:
			return uuid.UUID(raw)
		except ValueError as err:
			raise ParseError("must be a valid UUID") from err


class URL(Scalar):
	def parse(self, value: RawValue) -> http.URL:
		raw = self.single(value).strip()
		try:
			return http.URL(raw)
		except ValueError as err:
			raise ParseError("must be a valid URL") from err


class Bool:
	def parse(self, value: RawValue) -> bool:
		if isinstance(value, str) and value.strip() == "on":
			return True
		else:
			raise ParseError('must be "on" or omitted')


class List[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, value: RawValue) -> list[T]:
		if isinstance(value, str):
			values = [value]
		else:
			values = value

		try:
			return [self.parser.parse(item) for item in values]
		except ParseError as error:
			raise ParseError(error.message, item=True) from error


SCALARS: dict[Any, Parser[Any]] = {
	str: Str(),
	Untrimmed: Str(),
	bool: Bool(),
	int: Int(),
	uuid.UUID: UUID(),
	http.URL: URL(),
}


def for_type(annotation: object) -> Parser[Any] | None:
	if get_origin(annotation) is not list:
		return scalar(annotation)

	(item,) = get_args(annotation)
	item_parser = scalar(item)
	if item_parser is None:
		return None
	else:
		return List(item_parser)


def is_untrimmed(annotation: Any) -> bool:
	if get_origin(annotation) is list:
		(item,) = get_args(annotation)
		return item is Untrimmed
	else:
		return annotation is Untrimmed


def scalar(annotation: object) -> Parser[Any] | None:
	try:
		return SCALARS.get(annotation)
	except TypeError:
		return None
