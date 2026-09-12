from uuid import UUID

from helios.app import Component, Context
from helios.data.model import Model
from helios.data.store import NotFoundError, Store
from helios.session.store import Session

from .state import Authenticator, SESSION_KEY


class Component(Component[Authenticator]):
	provides = Authenticator
	requires = (Session, Store)

	def __init__(self, user_type: type[Model]):
		self.user_type = user_type

	def provide(self, ctx: Context) -> Authenticator:
		session = ctx.get(Session)
		store = ctx.get(Store)

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
