from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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
		return cls(filters={"date": date, "elapsed": elapsed})

	def update(self, other: Helpers):
		self.filters.update(other.filters)
		self.globals.update(other.globals)


def date(date: datetime) -> str:
	return date.strftime("%b %-d, %Y")


def elapsed(then: datetime, now: datetime | None = None) -> str:
	if now is None:
		now = datetime.now(UTC)
	diff = now - then
	if diff.days == 0:
		minutes = diff.seconds / 60
		hours = diff.seconds / (60 * 60)
		if minutes < 1:
			return "less than a minute ago"
		elif hours < 1:
			return f"{round(minutes)} {pluralize("minute", round(minutes))} ago"
		else:
			return f"{round(hours)} {pluralize("hour", round(hours))} ago"
	elif diff.days < 7:
		return f"{diff.days} {pluralize("day", diff.days)} ago"
	else:
		return date(then)


def pluralize(noun: str, count: int) -> str:
	if count == 1:
		return noun
	else:
		return noun + "s"
