from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from .driver import Driver
from .session import Session


class Driver(Driver):
	"""Keeps sessions in memory for as long as the driver lives.

	Each read and write copies the session, so a change reaches the driver only
	when it is written.
	"""

	def __init__(self):
		self.sessions: dict[str, Session] = {}

	def read(self, token: str) -> Session | None:
		session = self.sessions.get(token)
		if session is None:
			return None
		else:
			return Session(
				token,
				deepcopy(session.items),
				session.last_active_at,
				stored=True,
			)

	def write(self, session: Session):
		self.sessions[session.token] = Session(
			session.token,
			deepcopy(session.items),
			session.last_active_at,
		)

	def destroy(self, token: str):
		self.sessions.pop(token, None)

	def purge(self, cutoff: datetime):
		for token, session in list(self.sessions.items()):
			if session.last_active_at < cutoff:
				self.sessions.pop(token, None)


@dataclass
class Config:
	pass
