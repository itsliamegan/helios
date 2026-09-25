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

from .parser import Parser, RawValue, for_type, is_verbatim
from .rule import Required, Rule, RuleError

if TYPE_CHECKING:
	from .form import Form


class Failure(ValueError):
	def __init__(self, rule: str, message: str):
		super().__init__(message)
		self.rule = rule
		self.message = message


@dataclass
class Field:
	name: str
	parser: Parser[Any]
	default: object
	verbatim: bool
	extra_rules: list[Rule[Any, Any]]

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)

	@property
	def rules(self) -> list[Rule[Any, Any]]:
		if self.required:
			return [Required(), self.parser, *self.extra_rules]
		else:
			return [self.parser, *self.extra_rules]

	def raw(self, input: Input) -> RawValue | None:
		if self.name not in input:
			return None

		value = input[self.name]
		if self.verbatim:
			return value
		else:
			return trim(value)

	def validate(self, input: Input) -> object:
		value = self.raw(input)
		if value is None and not self.required:
			return self.initial

		for rule in self.rules:
			try:
				value = rule.check(value)
			except RuleError as error:
				raise Failure(rule.name, error.message or rule.message) from error
		return value

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
		is_verbatim(annotation),
		[],
	)


def trim(value: RawValue) -> RawValue | None:
	if isinstance(value, str):
		return value.strip() or None
	else:
		items = [item.strip() for item in value]
		return [item for item in items if item] or None
