from __future__ import annotations

from uuid import UUID

from helios.app import Component, Context
from helios.data.model import Model
from helios.data.store import NotFoundError, Store
from helios.http import Request
from helios.session.store import Session

SESSION_KEY = "_user_id"


class Authenticator:
	def __init__(
		self, session: Session, user: Model | None = None, key: str = SESSION_KEY
	):
		self.session = session
		self.user = user
		self.key = key

	def sign_in(self, user: Model):
		self.session[self.key] = str(user.id)
		self.user = user

	def sign_out(self):
		if self.key in self.session:
			del self.session[self.key]
		self.user = None

	def is_signed_in(self) -> bool:
		return self.user is not None

	def __repr__(self) -> str:
		return f"Authenticator({self.user})"


class Component(Component[Authenticator]):
	provides = Authenticator
	requires = (Session, Store)

	def __init__(self, user_type: type[Model], key: str = SESSION_KEY):
		self.user_type = user_type
		self.key = key

	def provide(self, req: Request, ctx: Context) -> Authenticator:
		session = ctx.get(Session)
		store = ctx.get(Store)

		if self.key in session:
			try:
				id = UUID(session[self.key])
			except ValueError:
				id = None
			if id is not None:
				try:
					user = store.find_one(self.user_type, id)
				except NotFoundError:
					user = None
			else:
				user = None
		else:
			user = None
		return Authenticator(session, user, self.key)
