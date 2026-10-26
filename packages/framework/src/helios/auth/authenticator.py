from typing import Self
from uuid import UUID

from helios.database import Model, NotFoundError, Store
from helios.session.session import Session
from helios.session.sessions import Sessions

from .error import AuthenticationError

SESSION_KEY = "_user_id"


class Authenticator[U: Model]:
	"""Provides access to the signed-in user for the request from the session.

	Signing in or out gives the session a new ID. Signing out keeps the session's
	other items.
	"""

	def __init__(self, session: Session, sessions: Sessions, user: U | None = None):
		self.session = session
		self.sessions = sessions
		self._user = user

	@classmethod
	def read(
		cls,
		session: Session,
		sessions: Sessions,
		store: Store,
		user_type: type[U],
	) -> Self:
		"""Read the signed-in user from the session.

		A user ID that is malformed or names no user is removed from the session,
		so the visitor is signed out.
		"""

		id = None
		if SESSION_KEY in session and isinstance(session[SESSION_KEY], str):
			try:
				id = UUID(session[SESSION_KEY])
			except ValueError:
				id = None

		user = None
		if id is not None:
			try:
				user = store.find_one(user_type, id)
			except NotFoundError:
				user = None

		if user is None and SESSION_KEY in session:
			del session[SESSION_KEY]
		return cls(session, sessions, user)

	@property
	def user(self) -> U:
		"""The signed-in user, or `AuthenticationError` when no one is signed in."""

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
