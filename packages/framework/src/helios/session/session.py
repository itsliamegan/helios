from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


@dataclass(init=False)
class Session:
	"""A set of items kept for one visitor between requests.

	A session is identified by an ID. Changing a session's items or its activity
	date marks it as dirty.
	"""

	id: UUID
	items: dict[str, Any]
	last_active_at: datetime | None
	dirty: bool

	def __init__(
		self,
		id: UUID,
		items: Mapping[str, Any] | None = None,
		last_active_at: datetime | None = None,
	):
		self.id = id
		self.items = dict(items or {})
		self.last_active_at = last_active_at
		self.dirty = False
		self.closed = False

	def close(self):
		self.closed = True

	def __getitem__(self, key: str) -> Any:
		return self.items[key]

	def __setitem__(self, key: str, value: Any):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.items[key] = value
		self.dirty = True

	def __delitem__(self, key: str):
		if self.closed:
			raise RuntimeError("the session is closed")

		del self.items[key]
		self.dirty = True

	def clear(self):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.items = {}
		self.dirty = True

	def __contains__(self, key: object) -> bool:
		return key in self.items

	def touch(self):
		if self.closed:
			raise RuntimeError("the session is closed")

		self.last_active_at = datetime.now(UTC)
		self.dirty = True

	def is_expired(self, maximum_age: timedelta) -> bool:
		return (
			self.last_active_at is not None
			and self.last_active_at + maximum_age < datetime.now(UTC)
		)
