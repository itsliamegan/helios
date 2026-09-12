from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from helios.persist.files import JSONValue

MAX_AGE = timedelta(days=30)


class Session:
	def __init__(
		self,
		id: UUID,
		items: dict[str, Any] | None = None,
		last_active_at: datetime | None = None,
	):
		if items is None:
			items = {}
		self.id = id
		self.items = items
		self.last_active_at = last_active_at
		self.dirty = False
		self.sessions: Sessions | None = None

	def __getitem__(self, key: str) -> Any:
		return self.items[key]

	def __setitem__(self, key: str, val: Any):
		self.items[key] = val
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

	def is_expired(self) -> bool:
		return (
			self.last_active_at is not None
			and self.last_active_at + MAX_AGE < datetime.now(UTC)
		)

	def invalidate(self):
		if self.sessions is not None:
			self.sessions.remove(self.id)

	def rotate(self):
		old_id = self.id
		if self.sessions is None:
			self.id = uuid4()
		else:
			self.sessions.rotate(self, old_id)
			if self.id == old_id:
				return
		self.dirty = True

	def __repr__(self) -> str:
		return f"Session({self.id!r}, {self.items!r})"


class Sessions:
	def __init__(self, sessions: dict[UUID, Session] | None = None):
		if sessions is None:
			sessions = {}
		self.sessions = sessions
		for session in self.sessions.values():
			session.sessions = self
		self.dirty = False

	def get(self, id: UUID) -> Session:
		return self.sessions[id]

	def put(self, session: Session):
		self.sessions[session.id] = session
		session.sessions = self
		self.dirty = True

	def remove(self, id: UUID):
		session = self.sessions.pop(id, None)
		if session is None:
			return
		session.sessions = None
		self.dirty = True

	def purge(self):
		for id, session in list(self.sessions.items()):
			if session.is_expired():
				self.remove(id)

	def rotate(self, session: Session, old_id: UUID):
		if old_id not in self.sessions:
			return
		if self.sessions[old_id] is not session:
			raise RuntimeError("session does not belong to this collection")
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
		return f"Sessions({self.sessions!r})"


class Format:
	def encode(self, sessions: Sessions) -> JSONValue:
		data = {}
		for id, session in sessions.sessions.items():
			data[str(id)] = {
				"items": session.items,
				"last_active_at": (
					session.last_active_at.isoformat()
					if session.last_active_at is not None
					else None
				),
			}
		return cast(JSONValue, data)

	def decode(self, value: JSONValue) -> Sessions:
		data = cast(dict[str, Any], value)
		sessions = {}
		for raw_id, session_data in data.items():
			id = UUID(raw_id)
			raw_last_active_at = session_data["last_active_at"]
			last_active_at = (
				datetime.fromisoformat(raw_last_active_at)
				if raw_last_active_at is not None
				else None
			)
			sessions[id] = Session(id, session_data["items"], last_active_at)
		return Sessions(sessions)
