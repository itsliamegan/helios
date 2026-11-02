from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Self

from helios.database import Codec, Model, Scalar, Store

from .driver import Driver
from .session import Session

SCHEMA = """\
CREATE TABLE sessions (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	token TEXT NOT NULL UNIQUE,
	items TEXT NOT NULL,
	last_active_at TEXT NOT NULL
) STRICT;

CREATE INDEX sessions_last_active_at ON sessions (last_active_at);
"""


class Driver(Driver):
	"""Stores each session as a row through a request's store.

	Every change runs in the store's transaction, so it commits or rolls back
	with the other writes of the same request.
	"""

	def __init__(self, store: Store):
		self.store = store

	def read(self, token: str) -> Session | None:
		record = self.find(token)
		if record is None:
			return None
		else:
			return Session(
				token,
				record.items.contents,
				record.last_active_at,
				stored=True,
			)

	def write(self, session: Session):
		record = self.find(session.token)
		if record is None:
			self.store.create(
				Record,
				token=Token.from_plaintext(session.token),
				items=Items(session.items),
				last_active_at=session.last_active_at,
			)
		else:
			self.store.update(
				record,
				items=Items(session.items),
				last_active_at=session.last_active_at,
			)

	def destroy(self, token: str):
		record = self.find(token)
		if record is not None:
			self.store.delete(record)

	def purge(self, cutoff: datetime):
		# The store has no bulk delete, so each expired row is deleted alone.
		expired = self.store.query(Record).where({"last_active_at <": cutoff}).all()
		for record in expired:
			self.store.delete(record)

	def find(self, token: str) -> Record | None:
		return (
			self.store.query(Record)
			.where({"token": Token.from_plaintext(token)})
			.first()
		)


@dataclass
class Config:
	pass


class Record(Model):
	table = "sessions"

	token: Token
	items: Items
	last_active_at: datetime


@dataclass
class Token:
	"""A session token stored only as its SHA-256 digest."""

	digest: str

	@classmethod
	def from_plaintext(cls, plaintext: str) -> Self:
		return cls(hashlib.sha256(plaintext.encode()).hexdigest())

	class Codec(Codec):
		def check(self, value: object):
			if not isinstance(value, Token):
				raise TypeError(f"expected a Token, got {type(value).__name__}")

		def encode(self, value: Token) -> Scalar:
			self.check(value)
			return value.digest

		def decode(self, value: Scalar) -> Token:
			if not isinstance(value, str):
				raise TypeError(f"expected a string, got {type(value).__name__}")
			return Token(value)


@dataclass
class Items:
	"""A session's items, stored as a JSON object."""

	contents: dict[str, Any]

	class Codec(Codec):
		def check(self, value: object):
			if not isinstance(value, Items):
				raise TypeError(f"expected Items, got {type(value).__name__}")

		def encode(self, value: Items) -> Scalar:
			self.check(value)
			return json.dumps(value.contents)

		def decode(self, value: Scalar) -> Items:
			if not isinstance(value, str):
				raise TypeError(f"expected a string, got {type(value).__name__}")
			contents = json.loads(value)
			if not isinstance(contents, dict):
				raise TypeError(
					f"expected a JSON object, got {type(contents).__name__}"
				)
			return Items(contents)
