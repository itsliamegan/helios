from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .token import Token


@dataclass(init=False)
class Session:
	"""A set of items kept for one visitor between requests.

	A session is identified by the token its visitor's cookie carries, and it
	starts active at the time it is built. Once closed, it refuses changes with
	`RuntimeError`, but its items can still be read.
	"""

	token: Token
	items: dict[str, Any]
	last_active_at: datetime
	stored: bool

	def __init__(
		self,
		token: Token,
		items: Mapping[str, Any] | None = None,
		last_active_at: datetime | None = None,
		stored: bool = False,
	):
		self.token = token
		self.items = dict(items or {})
		self.last_active_at = last_active_at or datetime.now(UTC)
		self.stored = stored
		self.closed = False

	def __getitem__(self, key: str) -> Any:
		return self.items[key]

	def __setitem__(self, key: str, value: Any):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.items[key] = value

	def __delitem__(self, key: str):
		if self.closed:
			raise RuntimeError("the session is closed")

		del self.items[key]

	def clear(self):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.items = {}

	def __contains__(self, key: object) -> bool:
		return key in self.items

	def touch(self):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.last_active_at = datetime.now(UTC)

	def is_expired(self, maximum_age: timedelta) -> bool:
		return self.last_active_at + maximum_age < datetime.now(UTC)

	def close(self):
		self.closed = True
