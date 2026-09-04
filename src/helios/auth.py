from uuid import UUID

from helios.app import Component, Context
from helios.http import Request
from helios.session import Session
from helios.store import Model, NotFoundError

SESSION_KEY = "_user_id"

class Component(Component):
	def __init__(self, user_type: type[Model], key: str = SESSION_KEY):
		self.user_type = user_type
		self.key = key

	def before(self, req: Request, ctx: Context):
		if self.key in ctx.session:
			try:
				id = UUID(ctx.session[self.key])
			except ValueError:
				id = None
			if id is not None:
				try:
					user = ctx.store.find_one(self.user_type, id)
				except NotFoundError:
					user = None
			else:
				user = None
		else:
			user = None
		ctx.auth = Authenticator(ctx.session, user, self.key)

class Authenticator:
	def __init__(self, session: Session, user: Model | None = None, key: str = SESSION_KEY):
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
