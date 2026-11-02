from abc import ABC, abstractmethod
from datetime import datetime

from .session import Session


class Driver(ABC):
	"""Stores sessions by their tokens.

	A driver reads a session whatever its age. Destroying a token with no
	session succeeds.
	"""

	@abstractmethod
	def read(self, token: str) -> Session | None: ...

	@abstractmethod
	def write(self, session: Session):
		"""Insert the session, or replace its stored items and activity time."""

	@abstractmethod
	def destroy(self, token: str): ...

	@abstractmethod
	def purge(self, cutoff: datetime):
		"""Remove the sessions last active before the cutoff."""
