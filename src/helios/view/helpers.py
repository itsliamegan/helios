from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from markupsafe import Markup, escape

from helios.http import URL


@dataclass(init=False)
class Helpers:
	filters: dict[str, Callable[..., Any]]
	globals: dict[str, Any]

	def __init__(
		self,
		filters: dict[str, Callable[..., Any]] | None = None,
		globals: dict[str, Any] | None = None,
	):
		self.filters = filters or {}
		self.globals = globals or {}

	@classmethod
	def defaults(cls) -> Helpers:
		return cls(filters={"date": date, "url": url, "elapsed": elapsed})

	def update(self, other: Helpers):
		self.filters.update(other.filters)
		self.globals.update(other.globals)


def date(date: datetime) -> str:
	return date.strftime("%b %-d, %Y")


def url(url: URL) -> str:
	# escape returns a Markup object which will always escape further
	# transformations. Convert it to a str to add unescaped line break
	# suggestions, then mark it as escaped.
	escaped = str(escape(url))
	broken = escaped.replace("/", "/<wbr>")
	return Markup(broken)


def elapsed(then: datetime, now: datetime | None = None) -> str:
	if now is None:
		now = datetime.now(UTC)
	diff = now - then
	if diff.days == 0:
		mins = diff.seconds / 60
		hours = diff.seconds / (60 * 60)
		if mins < 1:
			return "less than a minute ago"
		elif hours < 1:
			return f"{round(mins)} {pluralize("minute", round(mins))} ago"
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
