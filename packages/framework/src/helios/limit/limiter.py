from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from helios.http import Status
from helios.http.error import HTTPError


class RateLimitedError(HTTPError):
	status = Status.TOO_MANY_REQUESTS


@dataclass(init=False)
class RateLimiter:
	limit: int
	window: timedelta
	entries: dict[str, Entry]

	def __init__(self, limit: int, window: timedelta):
		self.limit = limit
		self.window = window
		self.entries = {}

	def hit(self, key: str):
		now = datetime.now(UTC)
		entry = self.entries.get(key)
		if entry is not None and now - entry.started < self.window:
			entry.count += 1
			if entry.count > self.limit:
				raise RateLimitedError
		else:
			self.entries[key] = Entry(started=now, count=1)


@dataclass
class Entry:
	started: datetime
	count: int
