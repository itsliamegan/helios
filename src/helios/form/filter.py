from typing import Protocol


class Filter[T](Protocol):
	def apply(self, value: T) -> T: ...


class Trim:
	def apply(self, value: str) -> str:
		return value.strip()


class Upcase:
	def apply(self, value: str) -> str:
		return value.upper()


class Unspace:
	def apply(self, value: str) -> str:
		return "".join(value.split())


class Compact:
	def apply(self, value: list[str]) -> list[str]:
		return [item for item in value if not blank(item)]


def blank(value: str) -> bool:
	return not value.strip()
