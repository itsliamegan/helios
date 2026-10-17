from copy import copy
from typing import Any

from luna.cli.conversion import Conversion, check_default, scalar
from luna.declarative import Declaration, DeclarationError, MISSING, split_nullable


class Argument:
	name: str
	declaration: Declaration
	_conversion: Conversion

	def __init__(self, default: object = MISSING, help: str | None = None):
		self.default = default
		self.help = help
		self.resolved = False

	def bind(self, declaration: Declaration):
		self.name = declaration.name
		self.declaration = declaration

	def resolve(self):
		if self.resolved:
			return
		try:
			value_type, nullable = split_nullable(
				self.name,
				self.declaration.resolve(),
			)
			if not scalar(value_type):
				raise DeclarationError(
					self.name,
					f"unsupported argument type: {self.declaration.annotation!r}",
				)

			conversion = Conversion(value_type, nullable)
			check_default(self.declaration, conversion, self.default)
		except DeclarationError as error:
			raise self.declaration.reject(error) from error
		self._conversion = conversion
		self.resolved = True

	@property
	def type(self) -> Any:
		self.resolve()
		return self._conversion.type

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)


def argument(*, default: object = MISSING, help: str | None = None) -> Any:
	return Argument(default, help)
