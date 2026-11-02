from collections.abc import Iterable
from typing import Any

from .sqlite import Connection, Cursor


class Transaction:
	"""A unit of work on one connection that commits or rolls back as a whole.

	The transaction takes the database's write lock on its first statement. Once
	it commits or rolls back, it refuses every statement with `RuntimeError`.
	"""

	def __init__(self, connection: Connection):
		self.connection = connection
		self.begun = False
		self.ended = False

	def execute(
		self,
		sql: str,
		parameters: Iterable[Any] = (),
	) -> Cursor:
		if self.ended:
			raise RuntimeError("the transaction has ended")

		if not self.begun:
			self.connection.begin()
			self.begun = True
		return self.connection.execute(sql, parameters)

	def commit(self):
		if self.ended:
			return

		# A commit that fails rolls back and raises, so mark the transaction ended
		# before committing.
		self.ended = True
		if self.begun:
			self.connection.commit()

	def rollback(self):
		if self.ended:
			return

		self.ended = True
		if self.begun:
			self.connection.rollback()

	@property
	def parameter_limit(self) -> int:
		return self.connection.parameter_limit
