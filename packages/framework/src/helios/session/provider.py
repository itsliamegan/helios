from datetime import UTC, datetime

from helios.app import Application, Container, Context, Handler, Provider
from helios.database import Registry, Store
from helios.http import Cookie, Request, Response
from helios.view import View
from helios.view.composer import Composers

from .config import Config
from .driver import Driver, database, memory
from .driver.database import token
from .flash import Flash
from .session import Session
from .sessions import Sessions
from .token import Token

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class Provider(Provider):
	"""Provides each request's sessions, its visitor's session, and its flash.

	The visitor's session comes from the `session_id` cookie, or is a fresh
	session when the cookie names no live session. Finding a session touches it.
	When the request succeeds, a session with items is saved and its cookie
	renewed, and an emptied session is destroyed along with its cookie. A
	request that saves or destroys a session also purges the expired ones. A
	failed request saves nothing.

	The flash is read from the session and written back to it only when the
	request succeeds. Once a response passes the session middleware, the flash,
	session, and sessions are closed, so outer middleware and streamed bodies
	cannot change them.
	"""

	def __init__(self, config: Config):
		self.config = config
		self.memory_driver: memory.Driver | None = None

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.scoped(Sessions, self.sessions)
		container.scoped(Session, self.session)
		container.scoped(Flash, self.flash)

	def boot(self, application: Application):
		if isinstance(self.config.driver, database.Config):
			registry = application.container.get(Registry)
			namespace = registry.namespace("session")
			namespace.model(database.Record)
			namespace.codec(token.Codec())
		application.use(self.middleware)
		if application.container.bound(Composers):
			composers = application.container.get(Composers)
			composers.add(self.compose)

	def sessions(self, context: Context) -> Sessions:
		return Sessions(self.driver(context), self.config.maximum_age)

	def driver(self, context: Context) -> Driver:
		match self.config.driver:
			case database.Config():
				store = context.get(Store)
				return database.Driver(store)
			case memory.Config():
				# One memory driver serves every request, so its sessions outlive
				# the request that saved them.
				if self.memory_driver is None:
					self.memory_driver = memory.Driver()
				return self.memory_driver

	def session(self, context: Context) -> Session:
		request = context.get(Request)
		if "session_id" in request.cookies:
			plaintext = request.cookies["session_id"].value
			sessions = context.get(Sessions)
			session = sessions.find(Token.from_plaintext(plaintext))
			if session is not None:
				session.touch()
				return session
		return Session(Token.generate())

	def flash(self, context: Context) -> Flash:
		session = context.get(Session)
		if "_flash" in session:
			flash = Flash(session["_flash"])
			del session["_flash"]
			return flash
		return Flash()

	def compose(self, view: View, context: Context):
		flash = context.get(Flash)
		view.share("flash", flash)

	def middleware(self, request: Request, context: Context, next: Handler) -> Response:
		response = next(request, context)

		flash = context.resolved(Flash)
		if flash is not None:
			if context.failure is None and flash.is_dirty():
				session = context.get(Session)
				session["_flash"] = flash.dirty()
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
			response.cookies["session_id"] = self.cookie(
				session.token.plaintext,
				expires,
			)
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
