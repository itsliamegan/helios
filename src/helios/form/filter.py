from abc import ABC, abstractmethod
from dataclasses import dataclass


class Filter[T](ABC):
	@abstractmethod
	def apply(self, value: T) -> T: ...


@dataclass
class Trim(Filter[str]):
	def apply(self, value: str) -> str:
		return value.strip()


@dataclass
class Upcase(Filter[str]):
	def apply(self, value: str) -> str:
		return value.upper()


@dataclass
class Unspace(Filter[str]):
	def apply(self, value: str) -> str:
		return "".join(value.split())


@dataclass
class Compact(Filter[list[str]]):
	def apply(self, value: list[str]) -> list[str]:
		return [item for item in value if not blank(item)]


def blank(value: str) -> bool:
	return value.strip() == ""
