from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self


@dataclass(init=False)
class Helpers:
	filters: dict[str, Callable[..., Any]]
	globals: dict[str, Any]

	def __init__(
		self,
		filters: Mapping[str, Callable[..., Any]] | None = None,
		globals: Mapping[str, Any] | None = None,
	):
		filters = filters or {}
		globals = globals or {}
		self.filters = dict(filters)
		self.globals = dict(globals)

	@classmethod
	def defaults(cls) -> Self:
		return cls(filters={"date": date})

	def update(self, other: Helpers):
		self.filters.update(other.filters)
		self.globals.update(other.globals)


def date(date: datetime, format: str = "%b %-d, %Y") -> str:
	return date.strftime(format)
