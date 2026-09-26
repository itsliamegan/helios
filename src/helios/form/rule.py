from collections.abc import Hashable, Iterable, Sized
from typing import Any, Protocol


class RuleError(ValueError):
	def __init__(self, message: str):
		super().__init__(message)
		self.message = message


class Rule[T](Protocol):
	@property
	def name(self) -> str: ...

	def check(self, value: T): ...


class Length:
	name = "length"

	def __init__(
		self,
		*,
		exactly: int | None = None,
		minimum: int | None = None,
		maximum: int | None = None,
	):
		if exactly is None and minimum is None and maximum is None:
			raise TypeError("Length needs exactly, minimum or maximum")
		if exactly is not None and (minimum is not None or maximum is not None):
			raise TypeError("Length takes exactly or bounds, not both")
		if minimum is not None and maximum is not None and minimum > maximum:
			raise TypeError("Length minimum must not be greater than its maximum")

		self.exactly = exactly
		self.minimum = minimum
		self.maximum = maximum

	def check(self, value: Sized):
		if not self.fits(len(value)):
			if isinstance(value, str):
				raise RuleError(f"must be {self.limit("character")}")
			else:
				raise RuleError(f"must have {self.limit("item")}")

	def fits(self, size: int) -> bool:
		if self.exactly is not None:
			return size == self.exactly
		else:
			above = self.minimum is None or size >= self.minimum
			below = self.maximum is None or size <= self.maximum
			return above and below

	def limit(self, unit: str) -> str:
		match self.exactly, self.minimum, self.maximum:
			case int(exactly), _, _:
				return count(exactly, unit)
			case None, int(minimum), None:
				return f"at least {count(minimum, unit)}"
			case None, None, int(maximum):
				return f"at most {count(maximum, unit)}"
			case _, minimum, maximum:
				return f"between {minimum} and {maximum} {unit}s"


class Only:
	name = "only"

	def __init__(self, allowed: Iterable[Hashable]):
		self.allowed = frozenset(allowed)

	def check(self, value: Iterable[Any]):
		if any(element not in self.allowed for element in value):
			if isinstance(value, str):
				raise RuleError("must only contain allowed characters")
			else:
				raise RuleError("must only contain allowed items")


class Distinct:
	name = "distinct"

	def check(self, value: list[Any]):
		if len(set(value)) != len(value):
			raise RuleError("must not repeat a value")


def count(number: int, unit: str) -> str:
	if number == 1:
		return f"1 {unit}"
	else:
		return f"{number} {unit}s"
