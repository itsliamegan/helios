from collections.abc import Callable
from types import FunctionType
from typing import Protocol


class RuleError(ValueError):
	def __init__(self, message: str | None = None):
		super().__init__(message)
		self.message = message


class Rule[In, Out](Protocol):
	@property
	def name(self) -> str: ...

	@property
	def message(self) -> str: ...

	def check(self, value: In, /) -> Out: ...


class FunctionRule[T]:
	def __init__(self, name: str, message: str, function: Callable[[T], T]):
		self.name = name
		self.message = message
		self.function = function

	def check(self, value: T, /) -> T:
		return self.function(value)


def rule[T](message: str) -> Callable[[Callable[[T], T]], FunctionRule[T]]:
	def decorate(function: Callable[[T], T]) -> FunctionRule[T]:
		if not isinstance(function, FunctionType):
			raise TypeError("rule decorates functions; write a class for other rules")

		return FunctionRule(function.__name__, message, function)

	return decorate


class Required:
	name = "required"
	message = "must be provided"

	def check[T](self, value: T | None, /) -> T:
		if value is None:
			raise RuleError()
		else:
			return value
