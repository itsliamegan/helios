from abc import ABC, abstractmethod
import re
from typing import Any, NewType, get_args, get_origin
import uuid

from helios import http

Untrimmed = NewType("Untrimmed", str)


class ParseError(ValueError):
	def __init__(self, message: str, item: bool = False):
		super().__init__(message)
		self.message = message
		self.item = item


class Parser[T](ABC):
	@classmethod
	def for_type(cls, annotation: object) -> Parser[Any] | None:
		if get_origin(annotation) is not list:
			return scalar(annotation)

		(item,) = get_args(annotation)
		item_parser = scalar(item)
		if item_parser is None:
			return None
		else:
			return List(item_parser)

	@abstractmethod
	def parse(self, values: list[str]) -> T: ...


class Scalar[T](Parser[T]):
	def single(self, values: list[str]) -> str:
		if len(values) != 1:
			raise ParseError("must be a single value")
		else:
			return values[0]


class Str(Scalar[str]):
	def parse(self, values: list[str]) -> str:
		return self.single(values)


class Int(Scalar[int]):
	def parse(self, values: list[str]) -> int:
		raw = self.single(values).strip()
		if re.fullmatch(r"-?[0-9]+", raw) is None:
			raise ParseError("must be a whole number")
		else:
			return int(raw)


class UUID(Scalar[uuid.UUID]):
	def parse(self, values: list[str]) -> uuid.UUID:
		raw = self.single(values).strip()
		try:
			return uuid.UUID(raw)
		except ValueError as err:
			raise ParseError("must be a valid UUID") from err


class URL(Scalar[http.URL]):
	def parse(self, values: list[str]) -> http.URL:
		raw = self.single(values).strip()
		try:
			return http.URL.parse(raw)
		except ValueError as err:
			raise ParseError("must be a valid URL") from err


class Bool(Parser[bool]):
	def parse(self, values: list[str]) -> bool:
		if len(values) == 1 and values[0].strip() == "on":
			return True
		else:
			raise ParseError('must be "on" or omitted')


class List[T](Parser[list[T]]):
	def __init__(self, parser: Parser[T]):
		self.parser = parser

	def parse(self, values: list[str]) -> list[T]:
		try:
			return [self.parser.parse([item]) for item in values]
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


def is_trimmed(annotation: Any) -> bool:
	if get_origin(annotation) is list:
		(item,) = get_args(annotation)
		return item is str
	else:
		return annotation is str


def scalar(annotation: object) -> Parser[Any] | None:
	try:
		return SCALARS.get(annotation)
	except TypeError:
		return None
