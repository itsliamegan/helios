from datetime import datetime

from helios.database import Store

from ...session import Session
from ...token import Token
from ..driver import Driver
from .record import Record


class Driver(Driver):
	"""Stores each session as a row in the database.

	Every change runs in the store's transaction, so it commits or rolls back
	with the other writes of the same request.
	"""

	def __init__(self, store: Store):
		self.store = store

	def read(self, token: Token) -> Session | None:
		record = self.find(token)
		if record is None:
			return None
		else:
			return Session(
				token,
				record.items,
				record.last_active_at,
				stored=True,
			)

	def write(self, session: Session):
		record = self.find(session.token)
		if record is None:
			self.store.create(
				Record,
				token=session.token,
				items=session.items,
				last_active_at=session.last_active_at,
			)
		else:
			self.store.update(
				record,
				items=session.items,
				last_active_at=session.last_active_at,
			)

	def destroy(self, token: Token):
		record = self.find(token)
		if record is not None:
			self.store.delete(record)

	def purge(self, cutoff: datetime):
		expired = self.store.query(Record).where({"last_active_at <": cutoff}).all()
		for record in expired:
			self.store.delete(record)

	def find(self, token: Token) -> Record | None:
		return self.store.query(Record).where({"token": token}).first()
