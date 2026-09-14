from datetime import UTC, datetime
from uuid import UUID, uuid4

from helios.app import Component, Context
from helios.http import Request, Response
from helios.persist.files import Files, Persistence

from .config import Config
from .store import Format, MAX_AGE, Session


class Component(Component[Session]):
	provides = Session
	requires = (Request, Persistence)

	def __init__(self, config: Config, files: Files):
		self.secure = config.secure
		self.file = files.json(config.store_file, Format())

	def provide(self, ctx: Context) -> Session:
		req = ctx.get(Request)
		persistence = ctx.get(Persistence)

		sessions = persistence.open(self.file).load()
		sessions.purge()
		if "session_id" in req.cookies:
			try:
				id = UUID(req.cookies["session_id"].val)
			except ValueError:
				id = None
			if id is not None and id in sessions:
				session = sessions.get(id)
				if not session.is_expired():
					session.touch()
					return session
				sessions.remove(id)

		return Session(uuid4())

	def finish(self, res: Response, ctx: Context):
		session = ctx.get(Session)
		persistence = ctx.get(Persistence)
		handle = persistence.open(self.file)
		sessions = handle.load()

		if session.invalidated:
			self.expire_cookie(res)
		elif session.items:
			if session.sessions is None:
				session.touch()
				sessions.put(session)
			self.set_cookie(res, session)
		elif session.sessions is not None:
			sessions.remove(session.id)
			self.expire_cookie(res)

		if sessions.is_dirty():
			handle.save(sessions)

	def set_cookie(self, res: Response, session: Session):
		res.cookies["session_id"] = str(session.id)
		res.cookies["session_id"].expires = datetime.now(UTC) + MAX_AGE
		res.cookies["session_id"].http_only = True
		res.cookies["session_id"].secure = self.secure
		res.cookies["session_id"].same_site = "Lax"

	def expire_cookie(self, res: Response):
		res.cookies["session_id"] = ""
		res.cookies["session_id"].expires = datetime(1970, 1, 1, tzinfo=UTC)
		res.cookies["session_id"].http_only = True
		res.cookies["session_id"].secure = self.secure
		res.cookies["session_id"].same_site = "Lax"
