from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable, Sized
from dataclasses import dataclass
from typing import Any, ClassVar

from luna.inflect import count

from .key import Key


class RuleError(ValueError):
	def __init__(self, message: str, key: Key | None = None):
		super().__init__(message)
		self.message = message
		self.key = key


class Rule[T](ABC):
	name: ClassVar[str]

	@abstractmethod
	def check(self, value: T): ...


@dataclass(init=False)
class Length(Rule[Sized]):
	name = "length"
	exactly: int | None
	minimum: int | None
	maximum: int | None

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


@dataclass(init=False)
class Only(Rule[Iterable[Any]]):
	name = "only"
	allowed: frozenset[Hashable]

	def __init__(self, allowed: Iterable[Hashable]):
		self.allowed = frozenset(allowed)

	def check(self, value: Iterable[Any]):
		if any(element not in self.allowed for element in value):
			if isinstance(value, str):
				raise RuleError("must only contain allowed characters")
			else:
				raise RuleError("must only contain allowed items")


@dataclass
class Distinct(Rule[list[Any]]):
	name = "distinct"

	def check(self, value: list[Any]):
		if len(set(value)) != len(value):
			raise RuleError("must not repeat a value")
