from datetime import UTC, datetime
from uuid import UUID, uuid4

from helios.app import Application, Container, Context, Next
from helios.app import Provider as ApplicationProvider
from helios.http import Cookie, Request, Response

from .config import Config
from .file import Driver
from .store import Session, Store

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class Provider(ApplicationProvider):
	def __init__(self, config: Config, driver: Driver):
		self.config = config
		self.driver = driver

	def register(self, container: Container):
		container.scoped(Store, self.store)
		container.scoped(Session, self.session)

	def boot(self, application: Application):
		application.use(self.middleware)

	def store(self, context: Context) -> Store:
		store = context.enter(self.driver.open())
		store.purge(self.config.maximum_age)
		return store

	def session(self, context: Context) -> Session:
		request = context.get(Request)
		store = context.get(Store)
		if "session_id" in request.cookies:
			try:
				id = UUID(request.cookies["session_id"].value)
			except ValueError:
				id = None
			if id is not None and id in store:
				session = store.get(id)
				if not session.is_expired(self.config.maximum_age):
					session.touch()
					return session
				store.remove(id)
		return Session(uuid4())

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		session = context.resolved(Session)
		if session is None:
			return response
		store = context.get(Store)

		if session.invalidated:
			response.cookies["session_id"] = self.cookie("", EPOCH)
		elif session.items:
			if session.store is None:
				session.touch()
				store.put(session)
			expires = datetime.now(UTC) + self.config.maximum_age
			response.cookies["session_id"] = self.cookie(str(session.id), expires)
		elif session.store is not None:
			store.remove(session.id)
			response.cookies["session_id"] = self.cookie("", EPOCH)

		if store.is_dirty():
			self.driver.save(store)
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
