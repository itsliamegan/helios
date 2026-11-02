from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from pathlib import Path

from .registry import Registry
from .sqlite import Connection
from .store import Store
from .transaction import Transaction

# Each thread under WSGI, and each task under ASGI, has its own context, so
# concurrent requests do not refuse each other.
TRANSACTIONS: ContextVar[frozenset[Database]] = ContextVar(
	"transactions",
	default=frozenset(),
)


class Database:
	"""A handle to a potential SQLite database opened through connections.

	A transaction takes the database's write lock on its first statement. While
	one is open in the current context, opening another connection to the same
	database raises `RuntimeError`, because that connection would wait on the
	transaction's lock until the busy timeout.
	"""

	def __init__(
		self,
		path: Path,
		registry: Registry,
		busy_timeout: timedelta = timedelta(seconds=30),
	):
		self.path = path
		self.registry = registry
		self.busy_timeout = busy_timeout

	@contextmanager
	def connection(self, read_only: bool = False) -> Generator[Connection]:
		"""Open a connection that commits each statement as it runs."""

		if self in TRANSACTIONS.get():
			raise RuntimeError("the database has a transaction open in this context")

		with Connection.open(
			self.path,
			self.busy_timeout,
			read_only=read_only,
		) as connection:
			yield connection

	@contextmanager
	def transaction(self) -> Generator[Transaction]:
		"""Open a transaction that commits when the block ends.

		The transaction rolls back when the block raises.
		"""

		with self.connection() as connection:
			transaction = Transaction(connection)
			token = TRANSACTIONS.set(TRANSACTIONS.get() | {self})
			try:
				yield transaction
			except BaseException:
				transaction.rollback()
				raise
			else:
				transaction.commit()
			finally:
				TRANSACTIONS.reset(token)

	@contextmanager
	def store(self) -> Generator[Store]:
		"""Open a store over a transaction that commits when the block ends."""

		with self.transaction() as transaction:
			yield Store(transaction, self.registry)
