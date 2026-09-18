from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4


class Session:
	def __init__(
		self,
		id: UUID,
		items: dict[str, Any] | None = None,
		last_active_at: datetime | None = None,
	):
		self.id = id
		self.items = items if items is not None else {}
		self.last_active_at = last_active_at
		self.dirty = False
		self.invalidated = False
		self.store: Store | None = None

	def __getitem__(self, key: str) -> Any:
		return self.items[key]

	def __setitem__(self, key: str, value: Any):
		self.items[key] = value
		self.dirty = True

	def __delitem__(self, key: str):
		del self.items[key]
		self.dirty = True

	def clear(self):
		self.items = {}
		self.dirty = True

	def __contains__(self, key: str) -> bool:
		return key in self.items

	def touch(self):
		self.last_active_at = datetime.now(UTC)
		self.dirty = True

	def is_expired(self, maximum_age: timedelta) -> bool:
		return (
			self.last_active_at is not None
			and self.last_active_at + maximum_age < datetime.now(UTC)
		)

	def invalidate(self):
		self.invalidated = True
		if self.store is not None:
			self.store.remove(self.id)

	def rotate(self):
		old_id = self.id
		if self.store is None:
			self.id = uuid4()
		else:
			self.store.rotate(self, old_id)
			if self.id == old_id:
				return
		self.dirty = True

	def __repr__(self) -> str:
		return f"Session({self.id!r}, {self.items!r})"


class Store:
	def __init__(self, sessions: dict[UUID, Session] | None = None):
		self.sessions = sessions if sessions is not None else {}
		for session in self.sessions.values():
			session.store = self
		self.dirty = False

	def get(self, id: UUID) -> Session:
		return self.sessions[id]

	def put(self, session: Session):
		self.sessions[session.id] = session
		session.invalidated = False
		session.store = self
		self.dirty = True

	def remove(self, id: UUID):
		session = self.sessions.pop(id, None)
		if session is None:
			return
		session.store = None
		self.dirty = True

	def purge(self, maximum_age: timedelta):
		for id, session in list(self.sessions.items()):
			if session.is_expired(maximum_age):
				self.remove(id)

	def rotate(self, session: Session, old_id: UUID):
		if old_id not in self.sessions:
			return
		if self.sessions[old_id] is not session:
			raise RuntimeError("session does not belong to this store")
		new_id = uuid4()
		while new_id in self.sessions:
			new_id = uuid4()
		del self.sessions[old_id]
		session.id = new_id
		self.sessions[new_id] = session
		self.dirty = True

	def is_dirty(self) -> bool:
		return self.dirty or any(session.dirty for session in self.sessions.values())

	def __contains__(self, id: UUID) -> bool:
		return id in self.sessions

	def __repr__(self) -> str:
		return f"Store({self.sessions!r})"
