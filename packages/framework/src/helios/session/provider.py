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
	"""Provides each request's sessions, its visitor's session, and its flash.

	A request's sessions are loaded under the driver's lock, which is held until
	the request ends. They are saved only when the request succeeds and changed
	them. The visitor's session comes from the `session_id` cookie, and it is
	stored once it holds items. Each response renews the cookie, and a session
	emptied of items is removed along with its cookie.

	The flash is read from the session and written back to it only when the
	request succeeds. Once a response passes the session middleware, the flash
	and session are closed, so outer middleware and streamed bodies cannot
	change them.
	"""

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
			try:
				yield sessions
				if sessions.is_dirty():
					self.driver.save(sessions)
			finally:
				sessions.close()

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

		flash = context.resolved(Flash)
		if flash is not None:
			if context.failure is None and flash.is_dirty():
				context.get(Session)["_flash"] = flash.dirty()
			flash.close()

		session = context.resolved(Session)
		if session is None:
			return response
		if context.failure is not None:
			session.close()
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
		session.close()
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
