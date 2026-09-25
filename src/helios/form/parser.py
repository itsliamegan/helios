import re
from typing import Any, NewType, get_args, get_origin
import uuid

from helios import http

from .rule import Rule, RuleError

Verbatim = NewType("Verbatim", str)

type RawValue = str | list[str]

type Parser[T] = Rule[RawValue, T]


class Scalar:
	name = "string"
	message = "must be a single value"

	def single(self, value: RawValue) -> str:
		if isinstance(value, list):
			raise RuleError("must be a single value")
		else:
			return value


class Str(Scalar):
	def check(self, value: RawValue) -> str:
		return self.single(value)


class Int(Scalar):
	name = "integer"
	message = "must be a whole number"

	def check(self, value: RawValue) -> int:
		raw = self.single(value)
		if re.fullmatch(r"-?[0-9]+", raw) is None:
			raise RuleError()
		else:
			return int(raw)


class UUID(Scalar):
	name = "uuid"
	message = "must be a valid UUID"

	def check(self, value: RawValue) -> uuid.UUID:
		raw = self.single(value)
		try:
			return uuid.UUID(raw)
		except ValueError as err:
			raise RuleError() from err


class URL(Scalar):
	name = "url"
	message = "must be a valid URL"

	def check(self, value: RawValue) -> http.URL:
		raw = self.single(value)
		try:
			return http.URL(raw)
		except ValueError as err:
			raise RuleError() from err


class Bool:
	name = "boolean"
	message = 'must be "on" or omitted'

	def check(self, value: RawValue) -> bool:
		if value == "on":
			return True
		else:
			raise RuleError()


class List[T]:
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	@property
	def name(self) -> str:
		return self.parser.name

	@property
	def message(self) -> str:
		return self.parser.message

	def check(self, value: RawValue) -> list[T]:
		if isinstance(value, str):
			values = [value]
		else:
			values = value
		return [self.parser.check(item) for item in values]


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
