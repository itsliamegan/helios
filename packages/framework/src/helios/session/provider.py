from datetime import UTC, datetime

from helios.app import Application, Container, Context, Handler, Provider
from helios.database import Database, Store
from helios.http import Cookie, Request, Response
from helios.view import View
from helios.view.composer import Composers

from . import database, memory
from .config import Config
from .driver import Driver
from .flash import Flash
from .session import Session
from .sessions import Sessions

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class Provider(Provider):
	"""Provides each request's sessions, its visitor's session, and its flash.

	The visitor's session comes from the `session_id` cookie, or is a fresh
	session when the cookie names no live session. Finding a session touches it.
	When the request succeeds, a session with items is saved and its cookie
	renewed, and an emptied session is destroyed along with its cookie. A
	request that saves or destroys a session also purges the expired ones. A
	failed request saves nothing.

	The memory driver keeps its sessions for the life of the application. The
	database driver writes through the request's store, so session changes
	commit or roll back with the request's other writes.

	The flash is read from the session and written back to it only when the
	request succeeds. Once a response passes the session middleware, the flash,
	session, and sessions are closed, so outer middleware and streamed bodies
	cannot change them.
	"""

	def __init__(self, config: Config):
		self.config = config

	def register(self, container: Container):
		container.instance(Config, self.config)
		match self.config.driver:
			case database.Config():
				container.scoped(Driver, self.database_driver)
			case memory.Config():
				container.instance(Driver, memory.Driver())
		container.scoped(Sessions, self.sessions)
		container.scoped(Session, self.session)
		container.scoped(Flash, self.flash)

	def boot(self, application: Application):
		if isinstance(self.config.driver, database.Config):
			application.container.get(Database).registry.get(database.Record)
		application.use(self.middleware)
		if application.container.bound(Composers):
			application.container.get(Composers).add(self.compose)

	def database_driver(self, context: Context) -> Driver:
		return database.Driver(context.get(Store))

	def sessions(self, context: Context) -> Sessions:
		return Sessions(context.get(Driver), self.config.maximum_age)

	def session(self, context: Context) -> Session:
		request = context.get(Request)
		if "session_id" in request.cookies:
			token = request.cookies["session_id"].value
			session = context.get(Sessions).find(token)
			if session is not None:
				session.touch()
				return session
		return Session(Session.generate_token())

	def flash(self, context: Context) -> Flash:
		session = context.get(Session)
		if "_flash" in session:
			flash = Flash(session["_flash"])
			del session["_flash"]
			return flash
		return Flash()

	def compose(self, view: View, context: Context):
		view.share("flash", context.get(Flash))

	def middleware(self, request: Request, context: Context, next: Handler) -> Response:
		response = next(request, context)

		flash = context.resolved(Flash)
		if flash is not None:
			if context.failure is None and flash.is_dirty():
				context.get(Session)["_flash"] = flash.dirty()
			flash.close()

		session = context.resolved(Session)
		if session is not None:
			if context.failure is None:
				self.persist(session, request, response, context)
			session.close()

		sessions = context.resolved(Sessions)
		if sessions is not None:
			sessions.close()
		return response

	def persist(
		self,
		session: Session,
		request: Request,
		response: Response,
		context: Context,
	):
		# Purging runs only beside a write, so a request that writes no session
		# takes no database lock for it.
		if session.items:
			sessions = context.get(Sessions)
			sessions.save(session)
			sessions.purge()
			expires = datetime.now(UTC) + self.config.maximum_age
			response.cookies["session_id"] = self.cookie(session.token, expires)
		elif session.stored:
			sessions = context.get(Sessions)
			sessions.destroy(session)
			sessions.purge()
			response.cookies["session_id"] = self.cookie("", EPOCH)
		elif "session_id" in request.cookies:
			# The cookie names a session that was rotated away, has expired, or
			# never existed, so the visitor's browser drops it.
			response.cookies["session_id"] = self.cookie("", EPOCH)

	def cookie(self, value: str, expires: datetime) -> Cookie:
		return Cookie(
			"session_id",
			value,
			expires=expires,
			http_only=True,
			secure=self.config.secure,
			same_site="Lax",
		)
