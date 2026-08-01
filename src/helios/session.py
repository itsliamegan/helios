from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any
from uuid import uuid4, UUID

from helios.app import Component, Context
from helios.http import Request, Response

class Component(Component):
	def __init__(self, file: Path):
		self.file = file
		self.sessions = None

	def before(self, req: Request, ctx: Context):
		self.sessions = load(self.file)
		if "session_id" in req.cookies:
			id = UUID(req.cookies["session_id"].val)
			if id in self.sessions:
				ctx.session = self.sessions.get(id)
			else:
				session = Session(id)
				self.sessions.put(session)
				ctx.session = session
		else:
			session = Session(uuid4())
			self.sessions.put(session)
			ctx.session = session

	def after(self, res: Response, ctx: Context):
		res.cookies["session_id"] = str(ctx.session.id)
		res.cookies["session_id"].expires = datetime.now() + timedelta(days = 30)
		res.cookies["session_id"].http_only = True
		save(self.file, self.sessions)

class Session:
	def __init__(self, id: UUID, items: dict[str, Any] | None = None):
		if items is None:
			items = {}
		self.id = id
		self.items = items

	def __getitem__(self, key: str) -> Any:
		return self.items[key]

	def __setitem__(self, key: str, val: Any):
		self.items[key] = val

	def __delitem__(self, key: str):
		del self.items[key]

	def clear(self):
		self.items = {}

	def __contains__(self, key: str) -> bool:
		return key in self.items

	def __repr__(self) -> str:
		return f"Session({repr(self.id)}, {repr(self.items)})"

class Sessions:
	def __init__(self, sessions: dict[UUID, Session] | None = None):
		if sessions is None:
			sessions = {}
		self.sessions = sessions

	def get(self, id: UUID) -> Session:
		return self.sessions[id]

	def put(self, session: Session):
		self.sessions[session.id] = session

	def __contains__(self, id: UUID) -> bool:
		return id in self.sessions

	def __repr__(self) -> str:
		return f"Sessions({repr(self.sessions)})"

def save(path: Path, sessions: Sessions):
	with open(path, "w") as file:
		data = encode(sessions)
		json.dump(data, file)

def load(path: Path) -> Sessions:
	with open(path, "r") as file:
		data = json.load(file)
		sessions = decode(data)
		return sessions

def encode(sessions: Sessions) -> dict[str, Any]:
	data = {}
	for id in sessions.sessions:
		data[str(id)] = sessions.sessions[id].items
	return data

def decode(data: dict[str, Any]) -> Sessions:
	sessions = {}
	for raw_id in data:
		id = UUID(raw_id)
		sessions[id] = Session(id, data[raw_id])
	return Sessions(sessions)
