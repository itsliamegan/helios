from copy import copy
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.declarative import (
	Declaration,
	DeclarationError,
	MISSING,
	split_nullable,
)
from helios.http import Input

from .filter import blank
from .parser import List, Parser, for_type, is_trimmed

if TYPE_CHECKING:
	from .form import Form


@dataclass(init=False)
class Field:
	name: str
	parser: Parser[Any]
	default: object
	trimmed: bool

	def __init__(
		self,
		name: str,
		parser: Parser[Any],
		default: object = MISSING,
		trimmed: bool = False,
	):
		self.name = name
		self.parser = parser
		self.default = default
		self.trimmed = trimmed

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)

	@property
	def is_list(self) -> bool:
		return isinstance(self.parser, List)

	def missing(self, input: Input) -> bool:
		if self.name not in input:
			return True

		value = input[self.name]
		if self.is_list:
			return value == []
		else:
			return isinstance(value, str) and blank(value)

	def parse(self, input: Input) -> Any:
		return self.parser.parse(input[self.name])

	def __get__(self, form: Form | None, owner: type) -> Any:
		if form is None:
			return self

		try:
			return form.values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def __set__(self, form: Form, value: object):
		form.values[self.name] = value


def declare(declaration: Declaration[Field]) -> Field:
	annotation, _ = split_nullable(declaration.name, declaration.annotation)
	parser = for_type(annotation)
	if parser is None:
		raise DeclarationError(
			declaration.name,
			f"unsupported field type: {annotation!r}",
		)
	return Field(
		declaration.name,
		parser,
		declaration.default,
		is_trimmed(annotation),
	)
