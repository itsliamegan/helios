from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from .session import Session


@dataclass(init=False)
class Sessions:
	"""A set of sessions keyed by their IDs.

	Adding, removing, or rotating a stored session marks the set as dirty. The
	set is also dirty when any of its sessions are dirty. Purging removes every
	session that has expired.
	"""

	items: dict[UUID, Session]
	dirty: bool

	def __init__(self, items: Mapping[UUID, Session] | None = None):
		self.items = dict(items or {})
		self.dirty = False
		self.closed = False

	def close(self):
		self.closed = True
		for session in self.items.values():
			session.close()

	def get(self, id: UUID) -> Session:
		return self.items[id]

	def put(self, session: Session):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		self.items[session.id] = session
		self.dirty = True

	def remove(self, id: UUID):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		if self.items.pop(id, None) is not None:
			self.dirty = True

	def purge(self, maximum_age: timedelta):
		for id, session in list(self.items.items()):
			if session.is_expired(maximum_age):
				self.remove(id)

	def rotate(self, session: Session):
		if self.closed:
			raise RuntimeError("the sessions are closed")

		if session.closed:
			raise RuntimeError("the session is closed")

		stored = self.items.get(session.id)
		if stored is not None and stored is not session:
			raise RuntimeError("another session is stored under this ID")

		id = uuid4()
		while id in self.items:
			id = uuid4()
		if stored is not None:
			del self.items[session.id]
			self.items[id] = session
			self.dirty = True
		session.id = id
		session.dirty = True

	def is_dirty(self) -> bool:
		return self.dirty or any(session.dirty for session in self.items.values())

	def __contains__(self, id: object) -> bool:
		return id in self.items
