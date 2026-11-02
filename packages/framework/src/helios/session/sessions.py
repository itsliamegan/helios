from datetime import UTC, datetime, timedelta

from .driver import Driver
from .session import Session


class Sessions:
	"""A request's access to the stored sessions.

	A session inactive for longer than the maximum age has expired, and `find`
	treats it as absent. Once closed, it refuses changes with `RuntimeError`.
	"""

	def __init__(self, driver: Driver, maximum_age: timedelta):
		self.driver = driver
		self.maximum_age = maximum_age
		self.closed = False

	def find(self, token: str) -> Session | None:
		session = self.driver.read(token)
		if session is None or session.is_expired(self.maximum_age):
			return None
		else:
			return session

	def save(self, session: Session):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		self.driver.write(session)
		session.stored = True

	def destroy(self, session: Session):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		self.driver.destroy(session.token)
		session.stored = False

	def rotate(self, session: Session):
		"""Give a session a new token, so its old token stops identifying it.

		The session is stored again under its new token only when it is saved.
		"""

		if self.closed:
			raise RuntimeError("the sessions are closed")

		if session.closed:
			raise RuntimeError("the session is closed")

		if session.stored:
			self.driver.destroy(session.token)
		session.token = Session.generate_token()
		session.stored = False
		session.dirty = True

	def purge(self):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		self.driver.purge(datetime.now(UTC) - self.maximum_age)

	def close(self):
		self.closed = True
