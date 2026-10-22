from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from helios.app import Application, Container, Context, Next, Provider
from helios.http import Cookie, Request, Response
from helios.view import View
from helios.view.composer import Composers

from .config import Config
from .file import Driver
from .flash import Flash
from .session import Session
from .sessions import Sessions

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class Provider(Provider):
	def __init__(self, config: Config, driver: Driver):
		self.config = config
		self.driver = driver

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.scoped(Sessions, self.sessions)
		container.scoped(Session, self.session)
		container.scoped(Flash, self.flash)

	def boot(self, application: Application):
		application.use(self.middleware)
		if application.container.bound(Composers):
			application.container.get(Composers).add(self.compose)

	def sessions(self, context: Context) -> Generator[Sessions]:
		with self.driver.open() as sessions:
			sessions.purge(self.config.maximum_age)
			yield sessions
			if sessions.is_dirty():
				self.driver.save(sessions)

	def session(self, context: Context) -> Session:
		request = context.get(Request)
		sessions = context.get(Sessions)
		if "session_id" in request.cookies:
			try:
				id = UUID(request.cookies["session_id"].value)
			except ValueError:
				id = None
			if id is not None and id in sessions:
				session = sessions.get(id)
				if not session.is_expired(self.config.maximum_age):
					session.touch()
					return session
				sessions.remove(id)
		return Session(uuid4())

	def flash(self, context: Context) -> Flash:
		session = context.get(Session)
		if "_flash" in session:
			flash = Flash(session["_flash"])
			del session["_flash"]
			return flash
		return Flash()

	def compose(self, view: View, context: Context):
		view.share("flash", context.get(Flash))

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		if context.failure is not None:
			return response

		flash = context.resolved(Flash)
		if flash is not None and flash.is_dirty():
			context.get(Session)["_flash"] = flash.dirty()

		session = context.resolved(Session)
		if session is None:
			return response
		sessions = context.get(Sessions)

		if session.items:
			if session.id not in sessions:
				session.touch()
				sessions.put(session)
			expires = datetime.now(UTC) + self.config.maximum_age
			response.cookies["session_id"] = self.cookie(str(session.id), expires)
		elif session.id in sessions:
			sessions.remove(session.id)
			response.cookies["session_id"] = self.cookie("", EPOCH)
		return response

	def cookie(self, value: str, expires: datetime) -> Cookie:
		return Cookie(
			"session_id",
			value,
			expires=expires,
			http_only=True,
			secure=self.config.secure,
			same_site="Lax",
		)
