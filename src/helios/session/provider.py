from datetime import UTC, datetime
from uuid import UUID, uuid4

from helios.app import Application, Container, Context, Next, Provider
from helios.http import Request, Response
from helios.persist.files import Files, Persistence

from .config import Config
from .store import Format, MAX_AGE, Session


class Provider(Provider):
	def __init__(self, config: Config, files: Files):
		self.secure = config.secure
		self.file = files.json(config.store_file, Format())

	def register(self, container: Container):
		container.scoped(Session, self.session)

	def boot(self, application: Application):
		application.use(self.middleware)

	def session(self, context: Context) -> Session:
		request = context.get(Request)
		persistence = context.get(Persistence)
		sessions = persistence.open(self.file).load()
		sessions.purge()
		if "session_id" in request.cookies:
			try:
				id = UUID(request.cookies["session_id"].val)
			except ValueError:
				id = None
			if id is not None and id in sessions:
				session = sessions.get(id)
				if not session.is_expired():
					session.touch()
					return session
				sessions.remove(id)
		return Session(uuid4())

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		session = context.resolved(Session)
		if session is None:
			return response
		persistence = context.get(Persistence)
		handle = persistence.open(self.file)
		sessions = handle.load()

		if session.invalidated:
			self.expire_cookie(response)
		elif session.items:
			if session.sessions is None:
				session.touch()
				sessions.put(session)
			self.set_cookie(response, session)
		elif session.sessions is not None:
			sessions.remove(session.id)
			self.expire_cookie(response)

		if sessions.is_dirty():
			handle.save(sessions)
		return response

	def set_cookie(self, response: Response, session: Session):
		response.cookies["session_id"] = str(session.id)
		response.cookies["session_id"].expires = datetime.now(UTC) + MAX_AGE
		response.cookies["session_id"].http_only = True
		response.cookies["session_id"].secure = self.secure
		response.cookies["session_id"].same_site = "Lax"

	def expire_cookie(self, response: Response):
		response.cookies["session_id"] = ""
		response.cookies["session_id"].expires = datetime(1970, 1, 1, tzinfo=UTC)
		response.cookies["session_id"].http_only = True
		response.cookies["session_id"].secure = self.secure
		response.cookies["session_id"].same_site = "Lax"
