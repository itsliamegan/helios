from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from helios.persist.files import JSONValue


class Session:
	def __init__(self, id: UUID, items: dict[str, Any] | None = None):
		if items is None:
			items = {}
		self.id = id
		self.items = items
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
		return cast(JSONValue, encode(sessions))

	def decode(self, value: JSONValue) -> Sessions:
		return decode(cast(dict[str, Any], value))


def encode(sessions: Sessions) -> dict[str, Any]:
	data = {}
	for id in sessions.sessions:
		data[str(id)] = sessions.sessions[id].items
	return data


def decode(data: dict[str, Any]) -> Sessions:
	sessions = {}
	for raw_id, session_data in data.items():
		id = UUID(raw_id)
		sessions[id] = Session(id, session_data)
	return Sessions(sessions)
