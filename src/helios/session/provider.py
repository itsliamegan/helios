from datetime import UTC, datetime
from uuid import UUID, uuid4

from helios.app import Application, Container, Context, Next
from helios.app import Provider as ApplicationProvider
from helios.http import Request, Response

from .config import Config
from .file import Driver
from .store import Session, Store


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
				id = UUID(request.cookies["session_id"].val)
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
			self.expire_cookie(response)
		elif session.items:
			if session.store is None:
				session.touch()
				store.put(session)
			self.set_cookie(response, session)
		elif session.store is not None:
			store.remove(session.id)
			self.expire_cookie(response)

		if store.is_dirty():
			self.driver.save(store)
		return response

	def set_cookie(self, response: Response, session: Session):
		response.cookies["session_id"] = str(session.id)
		response.cookies["session_id"].expires = (
			datetime.now(UTC) + self.config.maximum_age
		)
		response.cookies["session_id"].http_only = True
		response.cookies["session_id"].secure = self.config.secure
		response.cookies["session_id"].same_site = "Lax"

	def expire_cookie(self, response: Response):
		response.cookies["session_id"] = ""
		response.cookies["session_id"].expires = datetime(1970, 1, 1, tzinfo=UTC)
		response.cookies["session_id"].http_only = True
		response.cookies["session_id"].secure = self.config.secure
		response.cookies["session_id"].same_site = "Lax"
