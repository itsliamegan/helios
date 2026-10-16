from copy import copy
from typing import Any, get_args, get_origin

from luna.cli.conversion import Conversion, check_default, scalar
from luna.declarative import Declaration, DeclarationError, MISSING, split_nullable


class Option:
	name: str
	declaration: Declaration[Conversion]

	def __init__(
		self,
		default: object = MISSING,
		short: str | None = None,
		help: str | None = None,
	):
		self.default = default
		self.short = short
		self.help = help

	def bind(self, declaration: Declaration[Conversion]):
		self.name = declaration.name
		self.declaration = declaration

	def settle(self, declaration: Declaration[Conversion]) -> Conversion:
		value_type, nullable = split_nullable(declaration.name, declaration.annotation)
		if not accepts(value_type, nullable):
			raise DeclarationError(
				declaration.name,
				f"unsupported option type: {declaration.annotation!r}",
			)

		if self.default is MISSING and (
			value_type is bool or get_origin(value_type) is list
		):
			raise DeclarationError(
				declaration.name,
				f"option requires a declared default: {declaration.annotation!r}",
			)

		conversion = Conversion(value_type, nullable)
		check_default(declaration, conversion, self.default)
		return conversion

	@property
	def type(self) -> Any:
		return self.declaration.resolve().type

	@property
	def flag(self) -> bool:
		return self.type is bool

	@property
	def repeated(self) -> bool:
		return get_origin(self.type) is list

	@property
	def item_type(self) -> Any:
		if self.repeated:
			return get_args(self.type)[0]
		else:
			return self.type

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)


def option(
	*,
	default: object = MISSING,
	short: str | None = None,
	help: str | None = None,
) -> Any:
	return Option(default, short, help)


def accepts(value_type: object, nullable: bool) -> bool:
	if scalar(value_type):
		return True
	if nullable:
		return False
	if value_type is bool:
		return True

	arguments = get_args(value_type)
	return (
		get_origin(value_type) is list and len(arguments) == 1 and scalar(arguments[0])
	)
