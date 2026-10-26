from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from helios.http import Status
from helios.http.error import HTTPError


class RateLimitedError(HTTPError):
	"""Raised when a key has made more requests than its limit in one window."""

	status = Status.TOO_MANY_REQUESTS


class RateLimiter:
	"""Counts requests per key, raising `RateLimitedError` past the limit.

	A key's window starts at its first request and lasts `window`. Counts are
	kept in memory, so each process limits separately and forgets its counts
	when it restarts.
	"""

	def __init__(self, limit: int, window: timedelta):
		self.limit = limit
		self.window = window
		self.entries: dict[str, Entry] = {}

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
	"""A key's request count within its current window."""

	started: datetime
	count: int
