from helios.database import Model
from helios.session.store import Session

from .error import AuthenticationError

SESSION_KEY = "_user_id"


class Authenticator[U: Model]:
	def __init__(self, session: Session, user: U | None = None):
		self.session = session
		self.user = user

	def sign_in(self, user: U):
		self.session.rotate()
		self.session[SESSION_KEY] = str(user.id)
		self.user = user

	def sign_out(self):
		if SESSION_KEY in self.session:
			del self.session[SESSION_KEY]
		self.session.rotate()
		self.user = None

	def is_signed_in(self) -> bool:
		return self.user is not None

	def current(self) -> U:
		if self.user is None:
			raise AuthenticationError("no user is signed in")
		return self.user

	def __repr__(self) -> str:
		return f"Authenticator({self.user})"
