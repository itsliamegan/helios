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
		view.assign("current_user", context.get(Authenticator).user)

	def authenticator(self, context: Context) -> Authenticator:
		session = context.get(Session)
		store = context.get(Store)

		if SESSION_KEY in session:
			raw_id = session[SESSION_KEY]
			if isinstance(raw_id, str):
				try:
					id = UUID(raw_id)
				except ValueError:
					id = None
			else:
				id = None
			if id is not None:
				try:
					user = store.find_one(self.user_type, id)
				except NotFoundError:
					user = None
			else:
				user = None
			if user is None:
				del session[SESSION_KEY]
		else:
			user = None
		return Authenticator(session, user)
