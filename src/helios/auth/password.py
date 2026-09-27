from __future__ import annotations

from typing import Self

from werkzeug.security import check_password_hash, generate_password_hash

from helios.database import Codec, Stored


class Password:
	def __init__(self, digest: Digest):
		self.digest = digest

	@classmethod
	def from_plaintext(cls, plaintext: str) -> Self:
		return cls(Digest.generate(plaintext))

	def matches(self, candidate: str) -> bool:
		return self.digest.matches(candidate)

	def __repr__(self) -> str:
		return "Password(<redacted>)"

	class Codec(Codec):
		def check(self, value: object):
			if not isinstance(value, Password):
				raise TypeError(f"expected a Password, got {type(value).__name__}")

		def encode(self, value: Password) -> Stored:
			self.check(value)
			return value.digest.encode()

		def decode(self, value: Stored) -> Password:
			return Password(Digest.decode(value))


class Digest:
	method: str = "scrypt"

	def __init__(self, encoded: str):
		self.encoded = encoded

	@classmethod
	def generate(cls, plaintext: str) -> Self:
		return cls(generate_password_hash(plaintext, method=cls.method))

	def matches(self, candidate: str) -> bool:
		return check_password_hash(self.encoded, candidate)

	def encode(self) -> str:
		return self.encoded

	@classmethod
	def decode(cls, encoded: object) -> Self:
		if not isinstance(encoded, str):
			raise TypeError(f"expected a string, got {type(encoded).__name__}")
		return cls(encoded)

	def __repr__(self) -> str:
		return "Digest(<redacted>)"
