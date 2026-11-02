from collections.abc import Iterable
from enum import Enum, auto
from typing import Any

from .sqlite import Connection, Cursor


class Transaction:
	"""A unit of work on one connection that commits or rolls back as a whole.

	The transaction takes the database's write lock on its first statement. Once
	it commits or rolls back, it refuses every statement, commit, and rollback
	with `RuntimeError`.
	"""

	def __init__(self, connection: Connection):
		self.connection = connection
		self.state = State.PENDING

	def execute(
		self,
		sql: str,
		parameters: Iterable[Any] = (),
	) -> Cursor:
		match self.state:
			case State.PENDING:
				self.connection.begin()
				self.state = State.BEGUN
			case State.BEGUN:
				pass
			case State.ENDED:
				raise RuntimeError("the transaction has ended")

		return self.connection.execute(sql, parameters)

	def commit(self):
		match self.state:
			case State.PENDING:
				self.state = State.ENDED
			case State.BEGUN:
				try:
					self.connection.commit()
				finally:
					self.state = State.ENDED
			case State.ENDED:
				raise RuntimeError("the transaction has ended")

	def rollback(self):
		match self.state:
			case State.PENDING:
				self.state = State.ENDED
			case State.BEGUN:
				try:
					self.connection.rollback()
				finally:
					self.state = State.ENDED
			case State.ENDED:
				raise RuntimeError("the transaction has ended")

	@property
	def parameter_limit(self) -> int:
		return self.connection.parameter_limit


class State(Enum):
	# No statement has run, so the transaction holds no lock.
	PENDING = auto()
	# The transaction holds the write lock.
	BEGUN = auto()
	# The transaction committed or rolled back.
	ENDED = auto()
