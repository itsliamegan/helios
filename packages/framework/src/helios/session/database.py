from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Self

from helios.database import Codec, Model, Scalar

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


class Record(Model):
	table = "sessions"

	token: Token
	items: Items
	last_active_at: datetime


@dataclass
class Token:
	"""A session token stored only as its SHA-256 digest.

	The digest has no salt, so the same token always has the same digest, and a
	row can be found by it.
	"""

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
