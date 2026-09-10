from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from helios.app import Component, Context
from helios.http import Request, Response
from helios.persist import Files, JSONValue, Persistence


class Config:
	def __init__(self, store_file: Path):
		self.store_file = store_file


class Session:
	def __init__(self, id: UUID, items: dict[str, Any] | None = None):
		if items is None:
			items = {}
		self.id = id
		self.items = items
		self.dirty = False

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

	def __repr__(self) -> str:
		return f"Session({self.id!r}, {self.items!r})"


class Sessions:
	def __init__(self, sessions: dict[UUID, Session] | None = None):
		if sessions is None:
			sessions = {}
		self.sessions = sessions
		self.dirty = False

	def get(self, id: UUID) -> Session:
		return self.sessions[id]

	def put(self, session: Session):
		self.sessions[session.id] = session
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


class Component(Component[Session]):
	provides = Session
	requires = (Persistence,)

	def __init__(self, config: Config, files: Files):
		self.file = files.json(config.store_file, Format())

	def provide(self, req: Request, ctx: Context) -> Session:
		persistence = ctx.get(Persistence)

		sessions = persistence.open(self.file).load()
		if "session_id" in req.cookies:
			id = UUID(req.cookies["session_id"].val)
			if id in sessions:
				return sessions.get(id)
			session = Session(id)
			sessions.put(session)
			return session

		session = Session(uuid4())
		sessions.put(session)
		return session

	def finish(self, res: Response, ctx: Context):
		session = ctx.get(Session)
		persistence = ctx.get(Persistence)

		res.cookies["session_id"] = str(session.id)
		res.cookies["session_id"].expires = datetime.now(UTC) + timedelta(days=30)
		res.cookies["session_id"].http_only = True
		handle = persistence.open(self.file)
		sessions = handle.load()
		if sessions.is_dirty():
			handle.save(sessions)
