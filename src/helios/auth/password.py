from __future__ import annotations

from typing import Self

from werkzeug.security import check_password_hash, generate_password_hash


class Password:
	def __init__(self, digest: Digest):
		self.digest = digest

	@classmethod
	def from_plaintext(cls, plaintext: str) -> Self:
		return cls(Digest.generate(plaintext))

	def matches(self, candidate: str) -> bool:
		return self.digest.matches(candidate)

	@classmethod
	def check(cls, value: object):
		if not isinstance(value, cls):
			raise TypeError(f"expected a Password, got {type(value).__name__}")

	@classmethod
	def encode(cls, value: Password) -> str:
		cls.check(value)
		return value.digest.encode()

	@classmethod
	def decode(cls, encoded: object) -> Self:
		return cls(Digest.decode(encoded))

	def __repr__(self) -> str:
		return "Password(<redacted>)"


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
