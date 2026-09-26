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

from .filter import Filter, Trim, blank
from .parser import List, ParseError, Parser, for_type, is_untrimmed
from .rule import Rule, RuleError

if TYPE_CHECKING:
	from .form import Form

INVALID = "invalid"
REQUIRED = "required"


class Failure(ValueError):
	def __init__(self, key: str, message: str, item: bool = False):
		super().__init__(message)
		self.key = key
		self.item = item
		self.message = message


@dataclass(init=False)
class Field:
	name: str
	parser: Parser[Any]
	default: object
	untrimmed: bool
	item_filters: list[Filter[Any]]
	filters: list[Filter[Any]]
	item_rules: list[Rule[Any]]
	rules: list[Rule[Any]]

	def __init__(
		self,
		name: str,
		parser: Parser[Any],
		default: object = MISSING,
		untrimmed: bool = False,
		item_filters: list[Filter[Any]] | None = None,
		filters: list[Filter[Any]] | None = None,
		item_rules: list[Rule[Any]] | None = None,
		rules: list[Rule[Any]] | None = None,
	):
		self.name = name
		self.parser = parser
		self.default = default
		self.untrimmed = untrimmed
		self.item_filters = item_filters or []
		self.filters = filters or []
		self.item_rules = item_rules or []
		self.rules = rules or []

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)

	@property
	def is_list(self) -> bool:
		return isinstance(self.parser, List)

	def validate(self, input: Input) -> object:
		if self.missing(input):
			if self.required:
				raise Failure(REQUIRED, "must be provided")
			else:
				return self.initial

		value = self.parse(input[self.name])
		value = self.filter(value)
		self.check(value)
		return value

	def missing(self, input: Input) -> bool:
		if self.name not in input:
			return True

		value = input[self.name]
		if self.is_list:
			return value == []
		else:
			return isinstance(value, str) and blank(value)

	def parse(self, value: str | list[str]) -> object:
		try:
			return self.parser.parse(value)
		except ParseError as error:
			raise Failure(INVALID, error.message, error.item) from error

	def filter(self, value: object) -> object:
		if isinstance(value, list):
			value = [self.filter_item(item) for item in value]
		else:
			value = self.trim(value)

		for field_filter in self.filters:
			value = field_filter.apply(value)
		return value

	def filter_item(self, item: object) -> object:
		item = self.trim(item)
		for item_filter in self.item_filters:
			item = item_filter.apply(item)
		return item

	def trim(self, value: object) -> object:
		if isinstance(value, str) and not self.untrimmed:
			return Trim().apply(value)
		else:
			return value

	def check(self, value: object):
		if isinstance(value, list):
			for item in value:
				for item_rule in self.item_rules:
					run(item_rule, item, True)

		for field_rule in self.rules:
			run(field_rule, value, False)

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


def run(rule: Rule[Any], value: object, item: bool):
	try:
		rule.check(value)
	except RuleError as error:
		raise Failure(rule.name, error.message, item) from error


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
		is_untrimmed(annotation),
	)
