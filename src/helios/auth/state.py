from helios.data.model import Model
from helios.session.store import Session

SESSION_KEY = "_user_id"


class Authenticator:
	def __init__(self, session: Session, user: Model | None = None):
		self.session = session
		self.user = user

	def sign_in(self, user: Model):
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

	def __repr__(self) -> str:
		return f"Authenticator({self.user})"
