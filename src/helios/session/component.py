from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from helios.app import Component, Context
from helios.http import Request, Response
from helios.persist.files import Files, Persistence

from .config import Config
from .store import Format, Session


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
