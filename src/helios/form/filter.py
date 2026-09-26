from dataclasses import dataclass
from typing import Protocol


class Filter[T](Protocol):
	def apply(self, value: T) -> T: ...


@dataclass
class Trim:
	def apply(self, value: str) -> str:
		return value.strip()


@dataclass
class Upcase:
	def apply(self, value: str) -> str:
		return value.upper()


@dataclass
class Unspace:
	def apply(self, value: str) -> str:
		return "".join(value.split())


@dataclass
class Compact:
	def apply(self, value: list[str]) -> list[str]:
		return [item for item in value if not blank(item)]


def blank(value: str) -> bool:
	return value.strip() == ""
