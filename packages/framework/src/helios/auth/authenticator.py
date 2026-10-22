from helios.database import Model
from helios.session.session import Session
from helios.session.sessions import Sessions

from .error import AuthenticationError

SESSION_KEY = "_user_id"


class Authenticator[U: Model]:
	def __init__(self, session: Session, sessions: Sessions, user: U | None = None):
		self.session = session
		self.sessions = sessions
		self._user = user

	@property
	def user(self) -> U:
		if self._user is None:
			raise AuthenticationError("no user is signed in")
		return self._user

	def sign_in(self, user: U):
		self.sessions.rotate(self.session)
		self.session[SESSION_KEY] = str(user.id)
		self._user = user

	def sign_out(self):
		if SESSION_KEY in self.session:
			del self.session[SESSION_KEY]
		self.sessions.rotate(self.session)
		self._user = None

	def is_signed_in(self) -> bool:
		return self._user is not None

	def __repr__(self) -> str:
		return f"Authenticator({self._user})"
