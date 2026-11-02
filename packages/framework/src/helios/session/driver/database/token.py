from dataclasses import dataclass
import hashlib
from typing import Self

from helios.database import Codec, Scalar


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
