import re
from typing import Any, ClassVar, NewType, Protocol, get_args, get_origin
import uuid

from helios import http

Verbatim = NewType("Verbatim", str)

type RawValue = str | list[str]


class ParseError(ValueError):
	def __init__(self, rule: str, message: str):
		super().__init__(message)
		self.rule = rule


class Parser[T](Protocol):
	def parse(self, value: RawValue) -> T: ...


class Scalar:
	rule: ClassVar[str] = "string"

	def single(self, value: RawValue) -> str:
		if isinstance(value, list):
			raise ParseError(self.rule, "must be a single value")
		else:
			return value


class Str(Scalar):
	def parse(self, value: RawValue) -> str:
		return self.single(value)


class Int(Scalar):
	rule = "integer"

	def parse(self, value: RawValue) -> int:
		raw = self.single(value)
		if re.fullmatch(r"-?[0-9]+", raw) is None:
			raise ParseError(self.rule, "must be a whole number")
		return int(raw)


class UUID(Scalar):
	rule = "uuid"

	def parse(self, value: RawValue) -> uuid.UUID:
		raw = self.single(value)
		try:
			return uuid.UUID(raw)
		except ValueError as err:
			raise ParseError(self.rule, "must be a valid UUID") from err


class URL(Scalar):
	rule = "url"

	def parse(self, value: RawValue) -> http.URL:
		raw = self.single(value)
		try:
			return http.URL(raw)
		except ValueError as err:
			raise ParseError(self.rule, "must be a valid URL") from err


class Bool:
	rule: ClassVar[str] = "boolean"

	def parse(self, value: RawValue) -> bool:
		if value == "on":
			return True
		else:
			raise ParseError(self.rule, 'must be "on" or omitted')


class List[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, value: RawValue) -> list[T]:
		if isinstance(value, str):
			values = [value]
		else:
			values = value
		return [self.parser.parse(item) for item in values]


SCALARS: dict[Any, Parser[Any]] = {
	str: Str(),
	Verbatim: Str(),
	bool: Bool(),
	int: Int(),
	uuid.UUID: UUID(),
	http.URL: URL(),
}


def resolve(annotation: Any) -> Parser[Any]:
	if get_origin(annotation) is list:
		(item,) = get_args(annotation)
		return List(scalar(item))
	else:
		return scalar(annotation)


def is_verbatim(annotation: Any) -> bool:
	if get_origin(annotation) is list:
		(item,) = get_args(annotation)
		return item is Verbatim
	else:
		return annotation is Verbatim


def scalar(annotation: Any) -> Parser[Any]:
	try:
		return SCALARS[annotation]
	except KeyError, TypeError:
		raise TypeError(f"unsupported field type: {annotation!r}") from None
