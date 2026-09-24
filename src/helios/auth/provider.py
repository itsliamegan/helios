from uuid import UUID

from helios.app import Application, Container, Context, Provider
from helios.database import Model, NotFoundError, Store
from helios.session.store import Session
from helios.view import Engine, View

from .state import Authenticator, SESSION_KEY


class Provider(Provider):
	def __init__(self, user_type: type[Model]):
		self.user_type = user_type

	def register(self, container: Container):
		container.scoped(Authenticator, self.authenticator)

	def boot(self, application: Application):
		if application.container.bound(Engine):
			application.container.get(Engine).composer(self.compose)

	def compose(self, view: View, context: Context):
		view.assign("auth", context.get(Authenticator))

	def authenticator(self, context: Context) -> Authenticator:
		session = context.get(Session)
		user = self.user(session, context.get(Store))
		if user is None and SESSION_KEY in session:
			del session[SESSION_KEY]
		return Authenticator(session, user)

	def user(self, session: Session, store: Store) -> Model | None:
		if SESSION_KEY not in session:
			return None
		raw_id = session[SESSION_KEY]
		if not isinstance(raw_id, str):
			return None
		try:
			id = UUID(raw_id)
		except ValueError:
			return None
		try:
			return store.find_one(self.user_type, id)
		except NotFoundError:
			return None
